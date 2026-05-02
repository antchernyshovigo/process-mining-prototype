from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from app.services.dataset_service import process_and_save_dataset
from app.services.dfg_service import get_dfg_graph, get_variants, get_bottlenecks

router = APIRouter()

@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    case_id_column: str = Form(...),
    event_name_column: str = Form(...),
    timestamp_column: str = Form(...)
):
    try:
        result = await process_and_save_dataset(file, case_id_column, event_name_column, timestamp_column)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{dataset_id}/graph")
async def get_dataset_graph(dataset_id: str):
    try:
        return get_dfg_graph(dataset_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{dataset_id}/variants")
async def get_dataset_variants(dataset_id: str):
    try:
        return get_variants(dataset_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{dataset_id}/bottlenecks")
async def get_dataset_bottlenecks(dataset_id: str):
    try:
        return get_bottlenecks(dataset_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
