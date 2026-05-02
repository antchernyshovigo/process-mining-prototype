from fastapi import APIRouter, HTTPException, UploadFile, File
from app.services.dataset_service import process_and_save_dataset

router = APIRouter()

@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    try:
        result = await process_and_save_dataset(file)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")