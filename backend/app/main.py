from fastapi import FastAPI
from app.api.datasets import router as datasets_router
from app.api.uploads import router as uploads_router

app = FastAPI()

app.include_router(datasets_router, prefix="/datasets", tags=["datasets"])
app.include_router(uploads_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}