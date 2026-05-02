from pathlib import Path
import polars as pl
from uuid import uuid4
from fastapi import UploadFile

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"

async def process_and_save_dataset(file: UploadFile, case_id_column: str, event_name_column: str, timestamp_column: str):
    # Проверка директорий
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Проверка размера файла
    file_content = await file.read()
    if len(file_content) == 0:
        raise ValueError("File is empty")

    # Генерация уникального ID для датасета
    dataset_id = str(uuid4())
    filename = file.filename
    file_extension = filename.split(".")[-1].lower()

    if file_extension not in ["csv", "xlsx"]:
        raise ValueError("Unsupported file format. Only CSV and Excel are allowed.")

    # Сохранение файла
    raw_file_path = RAW_DATA_DIR / f"{dataset_id}.{file_extension}"
    with open(raw_file_path, "wb") as f:
        f.write(file_content)

    # Чтение файла через Polars
    try:
        if file_extension == "csv":
            df = pl.read_csv(raw_file_path)
        elif file_extension == "xlsx":
            df = pl.read_excel(raw_file_path)
    except Exception as e:
        raise ValueError(f"Error reading file: {str(e)}")

    rows_count_raw = df.shape[0]

    # Проверка наличия колонок
    required_columns = [case_id_column, event_name_column, timestamp_column]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    # Нормализация
    try:
        # Привести timestamp к datetime
        df = df.with_columns(
            pl.col(timestamp_column).str.to_datetime().alias(timestamp_column)
        )

        # Удалить строки с пустыми значениями
        df = df.filter(
            pl.col(case_id_column).is_not_null() &
            pl.col(event_name_column).is_not_null() &
            pl.col(timestamp_column).is_not_null()
        )

        # Отсортировать по case_id и timestamp
        df = df.sort([case_id_column, timestamp_column])

        # Привести ключевые колонки к стандартным именам
        df = df.rename({
            case_id_column: "case_id",
            event_name_column: "event_name",
            timestamp_column: "timestamp",
        })
    except Exception as e:
        raise ValueError(f"Error during normalization: {str(e)}")

    rows_count_processed = df.shape[0]

    # Сохранить нормализованные данные
    processed_path = PROCESSED_DATA_DIR / f"{dataset_id}.parquet"
    df.write_parquet(processed_path)

    # Возврат информации о датасете
    return {
        "dataset_id": dataset_id,
        "filename": filename,
        "rows_count_raw": rows_count_raw,
        "rows_count_processed": rows_count_processed,
        "columns": df.columns,
        "case_id_column": case_id_column,
        "event_name_column": event_name_column,
        "timestamp_column": timestamp_column,
        "processed_path": str(processed_path),
    }