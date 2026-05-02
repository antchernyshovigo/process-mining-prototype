import os
import polars as pl
from uuid import uuid4
from fastapi import UploadFile

DATA_DIR = "../../data/raw"

async def process_and_save_dataset(file: UploadFile):
    # Проверка директории
    os.makedirs(DATA_DIR, exist_ok=True)

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
    file_path = os.path.join(DATA_DIR, f"{dataset_id}.{file_extension}")
    with open(file_path, "wb") as f:
        f.write(file_content)

    # Чтение файла через Polars
    try:
        if file_extension == "csv":
            df = pl.read_csv(file_path)
            file_type = "csv"
        elif file_extension == "xlsx":
            df = pl.read_excel(file_path)
            file_type = "excel"
    except Exception as e:
        raise ValueError(f"Error reading file: {str(e)}")

    # Возврат информации о датасете
    return {
        "dataset_id": dataset_id,
        "filename": filename,
        "rows_count": df.shape[0],
        "columns": df.columns,
        "file_type": file_type,
    }