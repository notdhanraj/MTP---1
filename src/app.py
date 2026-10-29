import json
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from src.models import (
    BatchQueuedResponse,
    BatchRunResponse,
    RetryItemRequest,
    RetryItemResponse,
    RunSummaryResponse,
    WasteManagementDossier,
)
import src.services as services

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

app = FastAPI(
    title="Hazardous Waste Management Platform (D2S-MTP)",
    description="Wet laboratory hazardous waste classification and physical segregation planning.",
    version="1.0.0",
)
app.state.client = None

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


@app.post("/api/upload")
async def upload_excel_batch(
    file: UploadFile = File(...),
    pause_after_classification: bool = Form(False),
    sync: bool = Query(False),
):
    filename = file.filename or "uploaded_waste.xlsx"
    clean_name = filename.lower()
    if not (clean_name.endswith(".xlsx") or clean_name.endswith(".xls")):
        raise HTTPException(
            status_code=422,
            detail="Only .xlsx and .xls Excel files are accepted."
        )

    try:
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=422,
                detail="The uploaded file is empty. Please provide a valid Excel workbook."
            )
        if sync:
            client = getattr(app.state, "client", None)
            if client is not None:
                return services.process_excel_batch(content, filename, client=client)
            return services.process_excel_batch(content, filename)
        else:
            return services.initialize_batch_run(
                content,
                filename,
                pause_after_classification=pause_after_classification,
            )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected server error processing workbook: {e}"
        )


@app.get("/api/runs/{run_id}/stream")
async def stream_run_events(
    run_id: str,
    stage: str | None = Query(None),
):
    run_dir = services.DEFAULT_RUNS_DIR / run_id
    meta_path = run_dir / "meta.json"
    if not meta_path.exists():
        alt_path = Path("data/runs") / run_id / "meta.json"
        if alt_path.exists():
            meta_path = alt_path
        else:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    def event_generator():
        try:
            client = getattr(app.state, "client", None)
            for event in services.stream_batch_events(run_id=run_id, stage=stage, client=client):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            err_payload = {"type": "stream_error", "error": str(e)}
            yield f"data: {json.dumps(err_payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/runs/{run_id}/retry", response_model=RetryItemResponse)
async def api_retry_chemical_item(run_id: str, payload: RetryItemRequest):
    """
    Remediates an ambiguous or failed chemical in a batch run by re-evaluating with
    a refined or retried chemical name, atomically updating run metadata and bin counts.
    """
    orig_name = payload.original_name.strip()
    new_name = payload.new_name.strip()

    if not orig_name or not new_name:
        raise HTTPException(status_code=422, detail="Chemical names cannot be empty.")

    try:
        dossier, bin_counts = services.remediate_batch_item(
            run_id=run_id,
            original_name=orig_name,
            new_name=new_name,
            client=app.state.client
        )
        return RetryItemResponse(
            status="success",
            chemical=dossier.chemical,
            original_name=orig_name,
            dossier=dossier,
            bin_counts=bin_counts
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error retrying chemical '{new_name}': {str(e)}"
        )


@app.get("/api/runs", response_model=list[RunSummaryResponse])
async def get_runs_history():
    return services.list_runs()


@app.get("/api/runs/{run_id}", response_model=BatchRunResponse)
async def get_run(run_id: str):
    try:
        return services.get_run_details(run_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")


@app.get("/api/runs/{run_id}/export")
async def export_run_excel(run_id: str):
    try:
        excel_path = services.generate_batch_excel(run_id)
        return FileResponse(
            path=excel_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"hazardous_waste_management_plan_{run_id}.xlsx",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.app:app", host="127.0.0.1", port=8000, reload=True)
