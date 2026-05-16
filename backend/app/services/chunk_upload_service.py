from pathlib import Path
import json
from uuid import uuid4
from app.services.dataset_service import process_and_save_dataset_from_path, RAW_DATA_DIR
from fastapi import UploadFile

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOADS_DIR = BASE_DIR / "data" / "uploads"
METADATA_FILENAME = "metadata.json"
CHUNK_PREFIX = "chunk_"
CHUNK_SUFFIX = ".part"


def _upload_folder(upload_id: str) -> Path:
    return UPLOADS_DIR / upload_id


def _chunks_folder(upload_id: str) -> Path:
    return _upload_folder(upload_id) / "chunks"


def _metadata_path(upload_id: str) -> Path:
    return _upload_folder(upload_id) / METADATA_FILENAME


def _load_metadata(upload_id: str) -> dict:
    metadata_path = _metadata_path(upload_id)
    if not metadata_path.exists():
        raise FileNotFoundError(f"Upload {upload_id} not found")
    with open(metadata_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_metadata(upload_id: str, metadata: dict) -> None:
    metadata_path = _metadata_path(upload_id)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f)


def _chunk_path(upload_id: str, chunk_index: int) -> Path:
    return _chunks_folder(upload_id) / f"{CHUNK_PREFIX}{chunk_index:06d}{CHUNK_SUFFIX}"


def _list_chunk_files(upload_id: str) -> list[Path]:
    folder = _chunks_folder(upload_id)
    if not folder.exists():
        return []
    return sorted(folder.glob(f"{CHUNK_PREFIX}*{CHUNK_SUFFIX}"))


async def initialize_chunk_upload(
    filename: str,
    file_size: int,
    case_id_column: str,
    event_name_column: str,
    timestamp_column: str,
    delimiter: str | None = None,
) -> dict:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    upload_id = str(uuid4())
    _chunks_folder(upload_id).mkdir(parents=True, exist_ok=True)

    metadata = {
        "upload_id": upload_id,
        "filename": filename,
        "file_size": file_size,
        "case_id_column": case_id_column,
        "event_name_column": event_name_column,
        "timestamp_column": timestamp_column,
        "delimiter": delimiter or "auto",
        "status": "uploading",
        "received_chunks": 0,
        "total_chunks": None,
    }
    _save_metadata(upload_id, metadata)
    return metadata


async def save_chunk(
    upload_id: str,
    chunk_index: int,
    total_chunks: int,
    chunk: UploadFile,
) -> dict:
    metadata = _load_metadata(upload_id)
    if metadata.get("status") == "ready":
        raise ValueError("Upload already completed")

    if total_chunks is not None:
        metadata["total_chunks"] = total_chunks

    destination = _chunk_path(upload_id, chunk_index)
    content = await chunk.read()
    with open(destination, "wb") as f:
        f.write(content)

    chunk_files = _list_chunk_files(upload_id)
    metadata["received_chunks"] = len(chunk_files)
    metadata["status"] = "uploading"
    _save_metadata(upload_id, metadata)
    return metadata


def _validate_chunk_assembly(metadata: dict, chunk_files: list[Path]) -> None:
    total_chunks = metadata.get("total_chunks")
    if total_chunks is not None:
        if len(chunk_files) != total_chunks:
            missing = total_chunks - len(chunk_files)
            raise ValueError(f"Expected {total_chunks} chunks, but received {len(chunk_files)} ({missing} missing)")
        expected_names = {f"{CHUNK_PREFIX}{i:06d}{CHUNK_SUFFIX}" for i in range(1, total_chunks + 1)}
        found_names = {chunk.name for chunk in chunk_files}
        missing_names = sorted(expected_names - found_names)
        if missing_names:
            raise ValueError(f"Missing chunk files: {', '.join(missing_names)}")
    if not chunk_files:
        raise ValueError("No chunks uploaded for this upload_id")


async def complete_chunk_upload(upload_id: str) -> dict:
    metadata = _load_metadata(upload_id)
    if metadata.get("status") == "ready":
        return {
            "upload_id": upload_id,
            "status": "ready",
            "message": "Upload already completed",
        }

    metadata["status"] = "assembling"
    _save_metadata(upload_id, metadata)

    chunk_files = _list_chunk_files(upload_id)
    _validate_chunk_assembly(metadata, chunk_files)

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    assembled_path = RAW_DATA_DIR / f"{upload_id}.csv"
    with open(assembled_path, "wb") as output_file:
        for chunk_file in chunk_files:
            with open(chunk_file, "rb") as part_file:
                output_file.write(part_file.read())

    metadata["status"] = "processing"
    _save_metadata(upload_id, metadata)

    try:
        result = process_and_save_dataset_from_path(
            upload_id,
            assembled_path,
            metadata["case_id_column"],
            metadata["event_name_column"],
            metadata["timestamp_column"],
            metadata.get("delimiter"),
        )
        metadata["status"] = "ready"
        metadata["processed_dataset_id"] = result["dataset_id"]
        _save_metadata(upload_id, metadata)
        return result
    except Exception as error:
        metadata["status"] = "failed"
        metadata["error"] = str(error)
        _save_metadata(upload_id, metadata)
        raise


async def get_upload_status(upload_id: str) -> dict:
    metadata = _load_metadata(upload_id)
    chunk_files = _list_chunk_files(upload_id)
    total_chunks = metadata.get("total_chunks")
    received_chunks = len(chunk_files)
    progress_percent = 0
    if total_chunks:
        progress_percent = int((received_chunks / total_chunks) * 100)
    elif metadata.get("status") == "ready":
        progress_percent = 100

    return {
        "upload_id": upload_id,
        "status": metadata.get("status", "uploading"),
        "received_chunks": received_chunks,
        "total_chunks": total_chunks,
        "progress_percent": progress_percent,
    }
