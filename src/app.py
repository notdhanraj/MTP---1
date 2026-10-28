import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from src.models import WasteManagementDossier
from src.services import lookup_chemical
import src.services as services

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

app = FastAPI(
    title="Hazardous Waste Management Platform (D2S-MTP)",
    description="Wet laboratory hazardous waste classification and physical segregation planning.",
    version="1.0.0",
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class LookupRequest(BaseModel):
    chemical: str


@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/lookup", response_model=WasteManagementDossier)
async def api_lookup_chemical(payload: LookupRequest):
    chemical = payload.chemical.strip()
    if not chemical:
        raise HTTPException(status_code=422, detail="Chemical name cannot be empty.")
    return services.lookup_chemical(chemical)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.app:app", host="127.0.0.1", port=8000, reload=True)
