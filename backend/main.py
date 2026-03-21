from fastapi import FastAPI
from typing import Dict
from dotenv import load_dotenv

# Load .env before anything else
load_dotenv()

from backend.routers.whatsapp import router as whatsapp_router

app = FastAPI(title="Daycare AI Platform API")

# Include routers
app.include_router(whatsapp_router)


@app.get("/")
async def root() -> Dict[str, str]:
    return {"status": "ok", "message": "Daycare AI Platform API is running"}


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "healthy"}
