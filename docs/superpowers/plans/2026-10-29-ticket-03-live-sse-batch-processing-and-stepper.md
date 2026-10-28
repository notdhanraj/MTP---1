# Ticket 03: Live SSE Batch Processing & Progress Stepper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement real-time Server-Sent Events (SSE) streaming during Excel batch ingestion with an animated multi-stage progress stepper banner, progressive grid card hydration, and an EHS Classification Review pause-and-resume workflow.

**Architecture:** Decouple file upload from streaming execution: `POST /api/upload` initializes the batch run directory (`data/runs/<run_id>/input.xlsx` and `meta.json`) and returns queued run metadata. The browser then connects via native HTML5 `EventSource` to `GET /api/runs/{run_id}/stream`, which yields typed JSON SSE events (`stage_start`, `item_progress`, `stage_complete`, `stage_paused`, `complete`, `item_error`). The frontend displays a sticky 4-step progress stepper (0% → 100%), progressively hydrates cards into the 3-column segregation grid, supports an optional pause after classification for badge inspection, and resumes plan synthesis via `GET /api/runs/{run_id}/stream?stage=planning`.

**Tech Stack:** FastAPI, Starlette `StreamingResponse`, Pydantic, Alpine.js (CDN), Tailwind CSS (CDN), Python standard library `unittest`.

**Spec:** [.scratch/frontend/spec.md](file:///C:/Users/stars/AI-ML/D2S-MTP/.scratch/frontend/spec.md) and [.scratch/frontend/issues/03-live-sse-batch-processing-and-stepper.md](file:///C:/Users/stars/AI-ML/D2S-MTP/.scratch/frontend/issues/03-live-sse-batch-processing-and-stepper.md)

## Global Constraints

- **Python Runtime**: Strictly target dedicated Conda environment `C:\Users\stars\miniconda3\envs\d2s-mtp` (`python.exe`). Zero packages in base.
- **Frontend Stack**: Server-rendered HTML with Tailwind CSS CDN and Alpine.js CDN. No Node.js build chain; zero npm packages.
- **Testing Standard**: Python standard library `unittest` ONLY (`unittest.TestCase`). Do NOT use `pytest`. Run tests via `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest`.
- **Git Config**: Author Aryan Das <starsnipe407@gmail.com>. Windows PowerShell syntax (use `;` instead of `&&`).
- **Domain Language**: Adhere strictly to [CONTEXT.md](file:///C:/Users/stars/AI-ML/D2S-MTP/CONTEXT.md) terms: `Batch Run`, `Review Queue`, `Classification Review`, `Segregation Bin`, `Waste Management Plan`.

---

## File Structure

- `src/models.py`: Defines `BatchQueuedResponse` model representing initialized batch runs.
- `src/services.py`: Implements `initialize_batch_run` (workbook validation & disk staging) and `stream_batch_events` (two-stage generator yielding typed JSON dictionaries).
- `src/app.py`: Updates `POST /api/upload` to return `BatchQueuedResponse` (preserving `?sync=true` backward compatibility) and adds `GET /api/runs/{run_id}/stream` serving `StreamingResponse`.
- `src/templates/index.html`: Adds review checkpoint checkbox to upload modal, sticky 4-step progress stepper banner, progressive card hydration state, and review pause resumption controls.
- `tests/test_models.py`: Unit tests for `BatchQueuedResponse`.
- `tests/test_services.py`: Unit tests for `initialize_batch_run`, event streaming sequences, pause checkpoint, and planning resumption.
- `tests/test_app.py`: Unit and integration tests for upload endpoint, SSE streaming endpoint, and end-to-end batch processing.

---

### Task 1: Define BatchQueuedResponse Model

**Files:**
- Modify: `src/models.py`
- Modify: `tests/test_models.py`

**Interfaces:**
- Consumes: Pydantic `BaseModel`, `Field`
- Produces: `BatchQueuedResponse(run_id=str, filename=str, total_count=int, chemicals=list[str], pause_after_classification=bool, status=str)`

- [ ] **Step 1: Write the failing unit test**

Add `test_batch_queued_response_schema` to `tests/test_models.py`:

```python
    def test_batch_queued_response_schema(self):
        from src.models import BatchQueuedResponse

        queued = BatchQueuedResponse(
            run_id="2026-10-29_020000_123456",
            filename="lab_inventory.xlsx",
            total_count=3,
            chemicals=["Methanol", "Acetone", "Hydrochloric Acid"],
            pause_after_classification=True,
            status="queued"
        )
        self.assertEqual(queued.run_id, "2026-10-29_020000_123456")
        self.assertEqual(queued.total_count, 3)
        self.assertTrue(queued.pause_after_classification)
        self.assertEqual(queued.status, "queued")

        # Verify defaults
        minimal = BatchQueuedResponse(
            run_id="2026-10-29_020000_999999",
            filename="sample.xlsx",
            total_count=1,
            chemicals=["Toluene"]
        )
        self.assertFalse(minimal.pause_after_classification)
        self.assertEqual(minimal.status, "queued")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_models.py`
Expected: FAIL with `ImportError: cannot import name 'BatchQueuedResponse' from 'src.models'`

- [ ] **Step 3: Implement BatchQueuedResponse in src/models.py**

Add `BatchQueuedResponse` to `src/models.py`:

```python
class BatchQueuedResponse(BaseModel):
    run_id: str
    filename: str
    total_count: int
    chemicals: list[str]
    pause_after_classification: bool = False
    status: str = "queued"
```

Export `BatchQueuedResponse` in `__all__` if applicable.

- [ ] **Step 4: Run tests to verify it passes**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_models.py`
Expected: PASS (all model tests pass)

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat(models): define BatchQueuedResponse schema for decoupled batch runs"
```

---

### Task 2: Implement Batch Initialization & Two-Stage SSE Stream Generator Service

**Files:**
- Modify: `src/services.py`
- Modify: `tests/test_services.py`

**Interfaces:**
- Consumes: `detect_waste_column`, `normalize_chemical_name`, `classify_chemical`, `make_plan`, `assign_segregation_bin`, `create_fallback_dossier`, `BatchQueuedResponse`, `WasteManagementDossier`
- Produces:
  - `initialize_batch_run(file_bytes: bytes, filename: str, pause_after_classification: bool = False, runs_dir: Path | None = None) -> BatchQueuedResponse`
  - `stream_batch_events(run_id: str, stage: str | None = None, runs_dir: Path | None = None, client=None) -> Iterator[dict]`

- [ ] **Step 1: Write the failing unit tests**

Add unit tests in `tests/test_services.py`:
- `test_initialize_batch_run_creates_run_dir_and_meta`
- `test_stream_batch_events_full_flow_straight_through`
- `test_stream_batch_events_pause_and_resumption`
- `test_stream_batch_events_chemical_error_fallback`

```python
    def test_initialize_batch_run_creates_run_dir_and_meta(self):
        excel_bytes = self._create_test_excel('Hazardous Waste', ['Methanol', 'Acetone'])
        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            queued = initialize_batch_run(
                excel_bytes,
                'test.xlsx',
                pause_after_classification=True,
                runs_dir=runs_path
            )
            self.assertEqual(queued.total_count, 2)
            self.assertTrue(queued.pause_after_classification)
            self.assertEqual(queued.status, "queued")

            run_folder = runs_path / queued.run_id
            self.assertTrue(run_folder.exists())
            self.assertTrue((run_folder / 'input.xlsx').exists())
            self.assertTrue((run_folder / 'meta.json').exists())

            with open(run_folder / 'meta.json', 'r', encoding='utf-8') as f:
                meta = json.load(f)
            self.assertEqual(meta['status'], 'queued')
            self.assertEqual(meta['chemicals'], ['Methanol', 'Acetone'])
            self.assertTrue(meta['pause_after_classification'])

    def test_stream_batch_events_full_flow_straight_through(self):
        excel_bytes = self._create_test_excel('Hazardous Waste', ['Methanol'])
        fake_client = FakeClient()
        classification = HazardClassification(
            flammable=True, carcinogenic=False, infectious=False, toxic=False, corrosive=False
        )
        plan = ManagementPlan(
            chemical='Methanol',
            identification_and_characterization='desc',
            segregation_and_incompatibilities='seg',
            recommended_container='can',
            labeling_requirements='lbl',
            storage_requirements='store',
            handling_and_ppe='ppe',
            spill_and_emergency_management='spill',
            treatment_framework='treat',
            final_disposal_framework='disp',
            usepa_framework='epa',
            indian_framework='india',
            prohibited_or_unsafe_actions='prohibited',
            verification_required='ver',
        )
        def side_effect(**kwargs):
            if kwargs['text_format'] is HazardClassification:
                return types.SimpleNamespace(output_parsed=classification)
            return types.SimpleNamespace(output_parsed=plan)
        fake_client.responses.parse = side_effect

        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            queued = initialize_batch_run(
                excel_bytes, 'test.xlsx', pause_after_classification=False, runs_dir=runs_path
            )

            events = list(stream_batch_events(queued.run_id, runs_dir=runs_path, client=fake_client))
            event_types = [e['type'] for e in events]

            # Straight-through sequence: stage_start(classification) -> item_progress -> stage_complete -> stage_start(planning) -> item_progress -> complete
            self.assertIn('stage_start', event_types)
            self.assertIn('stage_complete', event_types)
            self.assertIn('complete', event_types)
            self.assertNotIn('stage_paused', event_types)

            # Check final complete event
            complete_event = [e for e in events if e['type'] == 'complete'][0]
            self.assertEqual(complete_event['total_count'], 1)
            self.assertIn('Flammable Solvents', complete_event['bin_counts'])

    def test_stream_batch_events_pause_and_resumption(self):
        excel_bytes = self._create_test_excel('Hazardous Waste', ['Methanol'])
        fake_client = FakeClient()
        classification = HazardClassification(
            flammable=True, carcinogenic=False, infectious=False, toxic=False, corrosive=False
        )
        plan = ManagementPlan(
            chemical='Methanol',
            identification_and_characterization='desc',
            segregation_and_incompatibilities='seg',
            recommended_container='can',
            labeling_requirements='lbl',
            storage_requirements='store',
            handling_and_ppe='ppe',
            spill_and_emergency_management='spill',
            treatment_framework='treat',
            final_disposal_framework='disp',
            usepa_framework='epa',
            indian_framework='india',
            prohibited_or_unsafe_actions='prohibited',
            verification_required='ver',
        )
        def side_effect(**kwargs):
            if kwargs['text_format'] is HazardClassification:
                return types.SimpleNamespace(output_parsed=classification)
            return types.SimpleNamespace(output_parsed=plan)
        fake_client.responses.parse = side_effect

        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            queued = initialize_batch_run(
                excel_bytes, 'test.xlsx', pause_after_classification=True, runs_dir=runs_path
            )

            # Stream Stage 1 (Classification)
            stage1_events = list(stream_batch_events(queued.run_id, runs_dir=runs_path, client=fake_client))
            stage1_types = [e['type'] for e in stage1_events]
            self.assertIn('stage_paused', stage1_types)
            self.assertNotIn('complete', stage1_types)

            # Check meta.json reflects paused_for_review
            meta_path = runs_path / queued.run_id / 'meta.json'
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            self.assertEqual(meta['status'], 'paused_for_review')
            self.assertIn('Methanol', meta['classifications'])

            # Stream Stage 2 (Planning Resume)
            stage2_events = list(stream_batch_events(queued.run_id, stage='planning', runs_dir=runs_path, client=fake_client))
            stage2_types = [e['type'] for e in stage2_events]
            self.assertIn('stage_start', stage2_types)
            self.assertIn('complete', stage2_types)

            # Verify meta.json updated to completed
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_completed = json.load(f)
            self.assertEqual(meta_completed['status'], 'completed')
            self.assertIn('Methanol', meta_completed['dossiers'])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_services.py`
Expected: FAIL with `NameError: name 'initialize_batch_run' is not defined`

- [ ] **Step 3: Implement initialize_batch_run and stream_batch_events in src/services.py**

Add imports and implementations in `src/services.py`:

```python
from typing import Iterator
from src.models import BatchQueuedResponse, HazardClassification, ManagementPlan, WasteManagementDossier


def initialize_batch_run(
    file_bytes: bytes,
    filename: str,
    pause_after_classification: bool = False,
    runs_dir: Path | None = None
) -> BatchQueuedResponse:
    target_runs_dir = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR

    # 1. Parse Excel
    try:
        df = pd.read_excel(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Invalid Excel workbook format. Please upload a valid .xlsx or .xls file. Error: {e}")

    # 2. Locate column
    waste_col = detect_waste_column(df)

    # 3. Clean and deduplicate chemical names
    raw_series = df[waste_col].dropna().astype(str)
    seen = set()
    unique_chemicals = []
    for raw in raw_series:
        norm = normalize_chemical_name(raw)
        if norm and norm.lower() not in seen:
            seen.add(norm.lower())
            unique_chemicals.append(norm)

    if not unique_chemicals:
        raise ValueError("No valid chemical names found in the uploaded workbook.")

    # 4. Safeguard limit
    if len(unique_chemicals) > MAX_BATCH_SIZE:
        raise ValueError(
            f"Batch size exceeds limit of {MAX_BATCH_SIZE} unique chemicals per upload (found {len(unique_chemicals)}). Please split your workbook."
        )

    # 5. Persist run directory and initial metadata
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
    run_dir = target_runs_dir / timestamp_str
    run_dir.mkdir(parents=True, exist_ok=True)

    input_file_path = run_dir / "input.xlsx"
    with open(input_file_path, "wb") as f:
        f.write(file_bytes)

    meta_payload = {
        "run_id": timestamp_str,
        "filename": filename,
        "timestamp": datetime.datetime.now().isoformat(),
        "total_count": len(unique_chemicals),
        "chemicals": unique_chemicals,
        "pause_after_classification": pause_after_classification,
        "status": "queued",
        "bin_counts": {
            "Flammable Solvents": 0,
            "Inorganic Acids": 0,
            "Inorganic Bases": 0,
            "Carcinogenic & Toxic Organics": 0,
            "Biohazard & Infectious": 0,
            "Review Queue": 0,
        },
        "classifications": {},
        "dossiers": {},
    }

    meta_file_path = run_dir / "meta.json"
    with open(meta_file_path, "w", encoding="utf-8") as f:
        json.dump(meta_payload, f, indent=2)

    return BatchQueuedResponse(
        run_id=timestamp_str,
        filename=filename,
        total_count=len(unique_chemicals),
        chemicals=unique_chemicals,
        pause_after_classification=pause_after_classification,
        status="queued"
    )


def stream_batch_events(
    run_id: str,
    stage: str | None = None,
    runs_dir: Path | None = None,
    client=None
) -> Iterator[dict]:
    target_runs_dir = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR
    run_dir = target_runs_dir / run_id
    meta_path = run_dir / "meta.json"

    if not meta_path.exists():
        raise FileNotFoundError(f"Run {run_id} not found.")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    chemicals: list[str] = meta["chemicals"]
    total = len(chemicals)
    classifications: dict = meta.get("classifications", {})
    dossiers: dict = meta.get("dossiers", {})
    bin_counts: dict = meta.get("bin_counts", {
        "Flammable Solvents": 0,
        "Inorganic Acids": 0,
        "Inorganic Bases": 0,
        "Carcinogenic & Toxic Organics": 0,
        "Biohazard & Infectious": 0,
        "Review Queue": 0,
    })

    execute_classification = (stage is None or stage == "classification") and meta.get("status") in ["queued", "classifying"]
    execute_planning = (stage == "planning") or (stage is None and not meta.get("pause_after_classification", False))

    # --- STAGE 1: CLASSIFICATION ---
    if execute_classification:
        meta["status"] = "classifying"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        yield {"type": "stage_start", "stage": "classification", "total": total}

        for idx, chem in enumerate(chemicals, start=1):
            if chem in classifications:
                clf_dict = classifications[chem]["classification"]
                bin_name = classifications[chem]["bin"]
            else:
                try:
                    clf_obj = classify_chemical(chem, client=client)
                    bin_name = assign_segregation_bin(clf_obj)
                    clf_dict = clf_obj.model_dump()
                except Exception as e:
                    clf_dict = HazardClassification(
                        flammable=False, carcinogenic=False, infectious=False, toxic=False, corrosive=False
                    ).model_dump()
                    bin_name = "Review Queue"

                classifications[chem] = {
                    "classification": clf_dict,
                    "bin": bin_name
                }
                bin_counts[bin_name] = bin_counts.get(bin_name, 0) + 1
                meta["classifications"] = classifications
                meta["bin_counts"] = bin_counts
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)

            yield {
                "type": "item_progress",
                "stage": "classification",
                "index": idx,
                "total": total,
                "chemical": chem,
                "classification": clf_dict,
                "bin": bin_name
            }

        yield {
            "type": "stage_complete",
            "stage": "classification",
            "total": total,
            "bin_counts": bin_counts
        }

        if meta.get("pause_after_classification", False) and stage != "planning":
            meta["status"] = "paused_for_review"
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
            yield {
                "type": "stage_paused",
                "stage": "classification",
                "run_id": run_id,
                "total": total,
                "message": "Classification complete. Paused for review."
            }
            return

    # --- STAGE 2: MANAGEMENT PLANNING ---
    if execute_planning or stage == "planning":
        meta["status"] = "planning"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        yield {"type": "stage_start", "stage": "planning", "total": total}

        for idx, chem in enumerate(chemicals, start=1):
            if chem in dossiers:
                dossier_dict = dossiers[chem]
            else:
                clf_info = classifications.get(chem, {})
                clf_data = clf_info.get("classification", {})
                clf_obj = HazardClassification(**clf_data) if clf_data else HazardClassification(
                    flammable=False, carcinogenic=False, infectious=False, toxic=False, corrosive=False
                )
                bin_name = clf_info.get("bin", assign_segregation_bin(clf_obj))

                active_categories = []
                if clf_obj.flammable: active_categories.append("Flammable")
                if clf_obj.carcinogenic: active_categories.append("Carcinogenic")
                if clf_obj.infectious: active_categories.append("Infectious")
                if clf_obj.toxic: active_categories.append("Toxic")
                if clf_obj.corrosive: active_categories.append("Corrosive")

                try:
                    plan_obj = make_plan(chem, active_categories, client=client)
                    dossier = WasteManagementDossier(
                        chemical=chem,
                        flammable=clf_obj.flammable,
                        carcinogenic=clf_obj.carcinogenic,
                        infectious=clf_obj.infectious,
                        toxic=clf_obj.toxic,
                        corrosive=clf_obj.corrosive,
                        segregation_bin=bin_name,
                        identification=plan_obj.identification_and_characterization,
                        segregation=plan_obj.segregation_and_incompatibilities,
                        container=plan_obj.recommended_container,
                        labeling=plan_obj.labeling_requirements,
                        storage=plan_obj.storage_requirements,
                        ppe=plan_obj.handling_and_ppe,
                        spill=plan_obj.spill_and_emergency_management,
                        prohibited=plan_obj.prohibited_or_unsafe_actions,
                        verification=plan_obj.verification_required,
                        usepa=plan_obj.usepa_framework,
                        india=plan_obj.indian_framework,
                        treatment=plan_obj.treatment_framework,
                        disposal=plan_obj.final_disposal_framework,
                        review_required=(bin_name == "Review Queue"),
                        review_reason=None if bin_name != "Review Queue" else "Classification requires review"
                    )
                except Exception as e:
                    dossier = create_fallback_dossier(chem, reason=f"Plan generation error: {e}")

                dossier_dict = dossier.model_dump()
                dossiers[chem] = dossier_dict
                meta["dossiers"] = dossiers
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)

            yield {
                "type": "item_progress",
                "stage": "planning",
                "index": idx,
                "total": total,
                "chemical": chem,
                "dossier": dossier_dict
            }

        meta["status"] = "completed"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        yield {
            "type": "complete",
            "status": "completed",
            "run_id": run_id,
            "total_count": total,
            "bin_counts": bin_counts,
            "items": [dossiers[c] for c in chemicals if c in dossiers]
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_services.py`
Expected: PASS (all tests in test_services pass)

- [ ] **Step 5: Commit**

```bash
git add src/services.py tests/test_services.py
git commit -m "feat(services): implement initialize_batch_run and stream_batch_events generator"
```

---

### Task 3: Implement GET /api/runs/{run_id}/stream and Update POST /api/upload

**Files:**
- Modify: `src/app.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `initialize_batch_run`, `stream_batch_events`, `BatchQueuedResponse`
- Produces:
  - `POST /api/upload`: returns `BatchQueuedResponse` (when `sync=False`, default) or `BatchRunResponse` (when `sync=True`)
  - `GET /api/runs/{run_id}/stream`: `StreamingResponse(media_type="text/event-stream")`

- [ ] **Step 1: Write the failing unit tests**

Add unit tests in `tests/test_app.py`:
- `test_upload_endpoint_returns_batch_queued_response`
- `test_upload_endpoint_backward_compatible_sync_param`
- `test_stream_endpoint_returns_sse_event_stream`
- `test_stream_endpoint_handles_pause_and_planning_resume`
- `test_stream_endpoint_returns_404_for_unknown_run`

```python
    def test_upload_endpoint_returns_batch_queued_response(self):
        excel_bytes = self._create_test_excel(['Acetone', 'Toluene'])
        response = self.client.post(
            "/api/upload",
            files={"file": ("inventory.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"pause_after_classification": "true"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("run_id", data)
        self.assertEqual(data["total_count"], 2)
        self.assertTrue(data["pause_after_classification"])
        self.assertEqual(data["status"], "queued")

    def test_upload_endpoint_backward_compatible_sync_param(self):
        excel_bytes = self._create_test_excel(['Acetone'])
        # When sync=true, it returns full BatchRunResponse with items
        response = self.client.post(
            "/api/upload?sync=true",
            files={"file": ("inventory.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("items", data)
        self.assertEqual(len(data["items"]), 1)

    def test_stream_endpoint_returns_sse_event_stream(self):
        excel_bytes = self._create_test_excel(['Acetone'])
        upload_resp = self.client.post(
            "/api/upload",
            files={"file": ("inventory.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"pause_after_classification": "false"}
        )
        run_id = upload_resp.json()["run_id"]

        stream_resp = self.client.get(f"/api/runs/{run_id}/stream")
        self.assertEqual(stream_resp.status_code, 200)
        self.assertEqual(stream_resp.headers["content-type"], "text/event-stream; charset=utf-8")
        
        # Verify content has data: {"type": ...} lines
        body_text = stream_resp.text
        self.assertIn("data: {", body_text)
        self.assertIn('"type": "stage_start"', body_text)
        self.assertIn('"type": "complete"', body_text)

    def test_stream_endpoint_handles_pause_and_planning_resume(self):
        excel_bytes = self._create_test_excel(['Acetone'])
        upload_resp = self.client.post(
            "/api/upload",
            files={"file": ("inventory.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"pause_after_classification": "true"}
        )
        run_id = upload_resp.json()["run_id"]

        # 1. First stream stops at stage_paused
        stream1 = self.client.get(f"/api/runs/{run_id}/stream")
        self.assertEqual(stream1.status_code, 200)
        self.assertIn('"type": "stage_paused"', stream1.text)
        self.assertNotIn('"type": "complete"', stream1.text)

        # 2. Resume planning stage
        stream2 = self.client.get(f"/api/runs/{run_id}/stream?stage=planning")
        self.assertEqual(stream2.status_code, 200)
        self.assertIn('"stage": "planning"', stream2.text)
        self.assertIn('"type": "complete"', stream2.text)

    def test_stream_endpoint_returns_404_for_unknown_run(self):
        resp = self.client.get("/api/runs/nonexistent_run_id/stream")
        self.assertEqual(resp.status_code, 404)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: FAIL with missing `/api/runs/{run_id}/stream` route

- [ ] **Step 3: Update src/app.py**

Modify `src/app.py`:
1. Import `BatchQueuedResponse`, `initialize_batch_run`, `stream_batch_events`, `StreamingResponse`, `Form`, `Query`.
2. Update `POST /api/upload`:

```python
@app.post("/api/upload")
async def upload_excel_batch(
    file: UploadFile = File(...),
    pause_after_classification: bool = Form(False),
    sync: bool = Query(False)
):
    """
    Accepts .xlsx or .xls workbook upload.
    If sync=True, processes synchronously and returns full BatchRunResponse (backward compatible).
    If sync=False (default), initializes the batch run and returns BatchQueuedResponse for SSE streaming.
    """
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=422,
            detail="Invalid file format. Please upload an Excel workbook (.xlsx or .xls)."
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=422,
            detail="The uploaded file is empty. Please provide a valid Excel workbook."
        )

    try:
        if sync:
            return process_excel_batch(
                file_bytes=content,
                filename=file.filename,
                client=app.state.client
            )
        else:
            return initialize_batch_run(
                file_bytes=content,
                filename=file.filename,
                pause_after_classification=pause_after_classification
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error processing Excel workbook: {str(e)}"
        )
```

3. Add `GET /api/runs/{run_id}/stream`:

```python
@app.get("/api/runs/{run_id}/stream")
async def stream_run_events(
    run_id: str,
    stage: str | None = Query(None)
):
    """
    Server-Sent Events endpoint streaming real-time batch execution progress.
    """
    run_dir = Path("data/runs") / run_id
    if not (run_dir / "meta.json").exists():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    def event_generator():
        try:
            for event in stream_batch_events(run_id=run_id, stage=stage, client=app.state.client):
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
            "X-Accel-Buffering": "no"
        }
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: PASS (all tests in test_app pass)

- [ ] **Step 5: Run full test suite across the repository**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest`
Expected: PASS (all 35+ tests pass)

- [ ] **Step 6: Commit**

```bash
git add src/app.py tests/test_app.py
git commit -m "feat(app): add SSE streaming endpoint and update upload route with queued flow"
```

---

### Task 4: Implement UI Progress Stepper Banner, Pause Checkbox & Dynamic Card Hydration

**Files:**
- Modify: `src/templates/index.html`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `POST /api/upload`, `GET /api/runs/{run_id}/stream`, `EventSource`
- Produces:
  - Interactive upload modal with "Pause for classification review" toggle
  - Sticky 4-step progress stepper banner (0% to 100%)
  - Dynamic cards progressively populating in the 3-column grid
  - Amber banner with `[ Proceed to Plan Generation → ]` button when paused
  - Drawer inspection during review pause

- [ ] **Step 1: Write the failing template test**

Add `test_template_contains_sse_stepper_and_pause_checkbox` to `tests/test_app.py`:

```python
    def test_template_contains_sse_stepper_and_pause_checkbox(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.text
        # Upload modal review pause toggle
        self.assertIn("pauseAfterClassification", html)
        self.assertIn("Pause for classification review", html)

        # Multi-stage progress stepper banner
        self.assertIn("streamActive", html)
        self.assertIn("streamProgress", html)
        self.assertIn("Proceed to Plan Generation", html)
        self.assertIn("EventSource", html)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: FAIL with `AssertionError: 'pauseAfterClassification' not found in response HTML`

- [ ] **Step 3: Update src/templates/index.html**

Update `src/templates/index.html`:
1. In `x-data` object, add reactive state:
   - `pauseAfterClassification: false`
   - `streamActive: false`
   - `streamPaused: false`
   - `streamProgress: 0`
   - `streamMessage: ''`
   - `streamStage: 'idle'` (idle, classification, planning, completed)
   - `eventSource: null`
2. Add methods in `x-data`:
   - `uploadBatch()`: sends `formData` with `pause_after_classification`, sets up `activeBatch`, calls `startStream(data.run_id)`.
   - `startStream(runId, stage=null)`: connects `new EventSource('/api/runs/' + runId + '/stream' + (stage ? '?stage=' + stage : ''))`, handles messages:
     - `stage_start`: updates `streamStage` and `streamMessage`.
     - `item_progress` (classification): calculates progress (0%..50%), appends/updates item card in `activeBatch.items` with classification and bin, updates `activeBatch.bin_counts`.
     - `stage_paused`: sets `streamPaused = true`, `streamActive = false`, closes `EventSource`.
     - `item_progress` (planning): calculates progress (50%..100%), updates item in `activeBatch.items` with complete dossier.
     - `complete`: sets `streamProgress = 100`, `streamStage = 'completed'`, `streamActive = false`, closes `EventSource`.
   - `resumePlanning()`: sets `streamPaused = false`, `streamActive = true`, calls `startStream(activeBatch.run_id, 'planning')`.
3. Add styled checkbox in Upload Modal below dropzone:
   ```html
   <div class="mt-4 p-3 rounded-lg bg-slate-900/60 border border-slate-700/60 flex items-start gap-3">
     <input type="checkbox" id="pauseAfterClassification" x-model="pauseAfterClassification" class="mt-1 h-4 w-4 rounded border-slate-700 bg-slate-800 text-emerald-500 focus:ring-emerald-500/20">
     <label for="pauseAfterClassification" class="text-xs text-slate-300">
       <span class="font-semibold text-slate-200 block">Pause for classification review before generating detailed plans</span>
       Inspect assigned hazard badges and storage bins before synthesizing 14-field compliance dossiers.
     </label>
   </div>
   ```
4. Add sticky 4-step Progress Stepper Banner above the card grid:
   - Step pills: `1. Ingestion (✓)` → `2. Classification` → `3. Planning` → `4. Segregated`.
   - Dynamic animated progress bar with `x-bind:style="'width: ' + streamProgress + '%'"` (`transition-all duration-300`).
   - Status text: `x-text="streamMessage"`.
   - Amber pause callout when `streamPaused`:
     ```html
     <div x-show="streamPaused" class="mt-3 p-3 rounded-lg bg-amber-950/40 border border-amber-500/40 flex items-center justify-between">
       <div class="flex items-center gap-2 text-amber-300 text-xs font-medium">
         <span>⚠️ Classification complete. Review hazard badges below before generating plans.</span>
       </div>
       <button @click="resumePlanning()" class="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-semibold shadow-md transition-colors">
         Proceed to Plan Generation →
       </button>
     </div>
     ```
5. Update chemical card in grid:
   - When `!item.container` (item is only classified, not planned yet):
     - Displays pulsing badge: `<span class="px-2 py-0.5 rounded text-[10px] font-medium bg-cyan-950 text-cyan-400 border border-cyan-800/60 animate-pulse">Plan Generating...</span>`.
     - Footer button says: `Inspect Badges →`.
   - When `item.container` is present:
     - Normal container and segregation snippet rendered; button says: `View Full Plan →`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit**

```bash
git add src/templates/index.html tests/test_app.py
git commit -m "feat(ui): add progress stepper banner, pause checkbox, and progressive card hydration"
```

---

### Task 5: End-to-End Workbook Ingestion with Live SSE & Classification Review Test

**Files:**
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `POST /api/upload`, `GET /api/runs/{run_id}/stream`, repository sample `src/Hazardous Waste.xlsx`
- Produces: Complete end-to-end integration test verifying full real-time batch lifecycle.

- [ ] **Step 1: Write the end-to-end integration test**

Add `test_e2e_live_sse_batch_processing_and_review_pause` to `tests/test_app.py`:

```python
    def test_e2e_live_sse_batch_processing_and_review_pause(self):
        sample_path = Path("src/Hazardous Waste.xlsx")
        self.assertTrue(sample_path.exists(), "Sample workbook src/Hazardous Waste.xlsx must exist")

        with open(sample_path, "rb") as f:
            file_bytes = f.read()

        # 1. Upload workbook with pause_after_classification=True
        upload_resp = self.client.post(
            "/api/upload",
            files={"file": ("Hazardous Waste.xlsx", file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"pause_after_classification": "true"}
        )
        self.assertEqual(upload_resp.status_code, 200)
        queued = upload_resp.json()
        run_id = queued["run_id"]
        total_count = queued["total_count"]
        self.assertGreater(total_count, 0)
        self.assertTrue(queued["pause_after_classification"])

        # 2. Connect to SSE stream for Stage 1 (Classification)
        stream_stage1 = self.client.get(f"/api/runs/{run_id}/stream")
        self.assertEqual(stream_stage1.status_code, 200)
        body1 = stream_stage1.text

        # Verify Stage 1 emitted classification events and paused cleanly
        self.assertIn('"stage": "classification"', body1)
        self.assertIn('"type": "stage_paused"', body1)
        self.assertNotIn('"type": "complete"', body1)

        # 3. Resume Stage 2 (Planning)
        stream_stage2 = self.client.get(f"/api/runs/{run_id}/stream?stage=planning")
        self.assertEqual(stream_stage2.status_code, 200)
        body2 = stream_stage2.text

        # Verify Stage 2 emitted planning events and completed
        self.assertIn('"stage": "planning"', body2)
        self.assertIn('"type": "complete"', body2)
        self.assertIn('"status": "completed"', body2)
```

- [ ] **Step 2: Run the test to verify PASS**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests.test_app.TestAppRoutes.test_e2e_live_sse_batch_processing_and_review_pause -v`
Expected: PASS

- [ ] **Step 3: Run the full test suite across the repository**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest`
Expected: PASS (all tests pass, 36+ tests)

- [ ] **Step 4: Commit**

```bash
git add tests/test_app.py
git commit -m "test(e2e): verify live SSE streaming batch lifecycle and review pause workflow"
```

---

## Self-Review Checklist

1. **Spec Coverage**:
   - Live SSE streaming endpoint streaming JSON events? Covered in Task 2 & Task 3 (`GET /api/runs/{run_id}/stream`).
   - Animated stepper banner with progress bar, percentage, and dynamic status text? Covered in Task 4 (`src/templates/index.html`).
   - Dynamic cards appearing/updating without page refresh? Covered in Task 4 (progressive hydration).
   - "Pause for review after classification" option with resume? Covered in Task 2, Task 3, Task 4, and Task 5.
   - Sequential event delivery and completion signal tests? Covered in Task 2, Task 3, and Task 5.
2. **No Placeholders**: All tasks contain explicit code blocks and runnable commands with exact assertions.
3. **Type Consistency**: `BatchQueuedResponse`, `stream_batch_events`, `initialize_batch_run`, `StreamingResponse`, and SSE payloads match across all tasks.
4. **Environment Constraints**: Standard library `unittest` used exclusively; Conda env `d2s-mtp` targeted in all run commands.
