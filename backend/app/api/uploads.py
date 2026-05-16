from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.services.chunk_upload_service import (
    initialize_chunk_upload,
    save_chunk,
    complete_chunk_upload,
    get_upload_status,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadStartRequest(BaseModel):
    filename: str
    file_size: int
    case_id_column: str
    event_name_column: str
    timestamp_column: str
    delimiter: str | None = None


@router.post("/start")
async def start_upload(request: UploadStartRequest):
    try:
        metadata = await initialize_chunk_upload(
            request.filename,
            request.file_size,
            request.case_id_column,
            request.event_name_column,
            request.timestamp_column,
            request.delimiter,
        )
        return metadata
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{upload_id}/chunk")
async def upload_chunk(
    upload_id: str,
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    chunk: UploadFile = File(...),
):
    try:
        metadata = await save_chunk(upload_id, chunk_index, total_chunks, chunk)
        return metadata
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{upload_id}/complete")
async def complete_upload(upload_id: str):
    try:
        result = await complete_chunk_upload(upload_id)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{upload_id}/status")
async def upload_status(upload_id: str):
    try:
        return await get_upload_status(upload_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
