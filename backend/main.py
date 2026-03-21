from fastapi import FastAPI
from typing import Dict

app = FastAPI(title="Daycare AI Platform API")

@app.get("/")
async def root() -> Dict[str, str]:
    return {"status": "ok", "message": "Daycare AI Platform API is running"}

@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "healthy"}
