# Ticket 06: Institutional Multi-Sheet Excel Export & Run History Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide institutional EHS compliance reporting parity via a 3-sheet Excel workbook export and zero-latency filtered CSV export, backed by an immutable Run History Archive sidebar allowing instant reloading of historical laboratory chemical evaluations with zero redundant API token expenditure.

**Architecture:** 
- In the backend (`src/services.py` & `src/app.py`), implement `generate_batch_excel` generating an official 3-sheet workbook (`Management Plan`, `Classification`, `Review Required`) matching `hazardous_waste_management_plan.xlsx` using `openpyxl`, cached at `data/runs/<run_id>/output.xlsx`. Add endpoints `GET /api/runs` (summaries sorted newest first), `GET /api/runs/{run_id}` (full reconstructed batch response from `meta.json` with 0 API tokens), and `GET /api/runs/{run_id}/export` (streaming the Excel workbook).
- In the frontend (`src/templates/index.html`), implement a left slide-over Run History Archive drawer toggled via `🕒 Run History (N)` in the header, 1-click batch reloading, and batch summary export buttons (`[ 📊 Export Excel (.xlsx) ]` and `[ 📄 Export Filtered CSV ]`) with dynamic client-side RFC 4180 CSV blob generation.

**Tech Stack:** Python 3.10+, FastAPI, openpyxl, pandas, Pydantic v2, Alpine.js v3, Tailwind CSS CDN, Python standard library `unittest`.

**Spec:** `.scratch/frontend/issues/06-excel-export-and-run-history-archive.md` and locked design decisions in `CONTEXT.md`.

## Global Constraints

- Python Runtime: Strictly target dedicated Conda environment `C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe`. Zero packages in base.
- Testing Framework: Python standard library `unittest` ONLY (`unittest.TestCase`). Do NOT use `pytest`.
- Excel Standards: Strict 3-sheet parity matching `src/generate_management_plan.py` (14 columns in `Management Plan`) and `src/classify_waste.py` (5 categories in `Classification`, exception register in `Review Required`).
- Archive Immutability: Read-only persistence in `data/runs/<run_id>/` without deletion endpoints to preserve EHS regulatory audit trails.
- Git Commits: Frequent, atomic commits with author `Aryan Das <starsnipe407@gmail.com>`.

---

### Task 1: Multi-Sheet Excel Export Service in `src/services.py`

**Files:**
- Modify: `src/models.py:50-85`
- Modify: `src/services.py:440-574`
- Test: `tests/test_services.py`

**Interfaces:**
- Consumes: `meta.json` dossiers and classifications dictionary from `data/runs/<run_id>/`.
- Produces: 
  - `RunSummaryResponse(run_id: str, filename: str, timestamp: str, total_count: int, bin_counts: dict[str, int], status: str)` in `src/models.py`.
  - `generate_batch_excel(run_id: str, runs_dir: Path | None = None) -> Path` in `src/services.py`: creates/refreshes `output.xlsx` with sheets `Management Plan` (14 columns), `Classification` (5 categories), and `Review Required`.
  - `list_runs(runs_dir: Path | None = None) -> list[dict]` in `src/services.py`.
  - `get_run_details(run_id: str, runs_dir: Path | None = None) -> BatchRunResponse` in `src/services.py`.

- [ ] **Step 1: Write the failing tests in `tests/test_services.py`**

Add tests for `generate_batch_excel`, `list_runs`, and `get_run_details`:

```python
    def test_generate_batch_excel_creates_3_sheet_workbook(self):
        from src.services import generate_batch_excel
        import openpyxl

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            run_id = "test_run_excel"
            run_dir = tmp_path / run_id
            run_dir.mkdir(parents=True)

            meta_data = {
                "run_id": run_id,
                "filename": "lab_chemicals.xlsx",
                "timestamp": "2026-10-29T10:00:00",
                "status": "completed",
                "chemicals": ["Methanol", "Hydrochloric Acid", "Mystery Chem"],
                "bin_counts": {
                    "Flammable Solvents": 1,
                    "Inorganic Acids": 1,
                    "Review Queue": 1,
                },
                "classifications": {
                    "Methanol": {"categories": ["Flammable", "Toxic"], "bin": "Flammable Solvents"},
                    "Hydrochloric Acid": {"categories": ["Corrosive"], "bin": "Inorganic Acids"},
                    "Mystery Chem": {"categories": [], "bin": "Review Queue"},
                },
                "dossiers": {
                    "Methanol": {
                        "chemical": "Methanol",
                        "bin": "Flammable Solvents",
                        "categories": ["Flammable", "Toxic"],
                        "container": "Glass Bottle",
                        "storage": "Flammables cabinet",
                        "ppe": "Nitrile gloves",
                        "segregation": "Keep away from oxidizers",
                        "labeling": "Flammable Liquid",
                        "spill": "Absorb with inert pads",
                        "identification": "Solvent waste",
                        "prohibited": "Do not pour down drain",
                        "verification": "Check pH",
                        "usepa": "D001",
                        "india": "Schedule II",
                        "treatment": "Incineration",
                        "disposal": "Authorized TSDF",
                        "review_required": False,
                    },
                    "Hydrochloric Acid": {
                        "chemical": "Hydrochloric Acid",
                        "bin": "Inorganic Acids",
                        "categories": ["Corrosive"],
                        "container": "Acid-resistant HDPE container",
                        "storage": "Dedicated acid locker",
                        "ppe": "Acid apron and faceshield",
                        "segregation": "Isolate from bases and cyanide",
                        "labeling": "Corrosive Acid Waste",
                        "spill": "Neutralize with sodium bicarbonate",
                        "identification": "Mineral acid stream",
                        "prohibited": "Do not mix with flammables",
                        "verification": "Test with pH paper",
                        "usepa": "D002",
                        "india": "Schedule II",
                        "treatment": "Neutralization",
                        "disposal": "Permitted facility",
                        "review_required": False,
                    },
                    "Mystery Chem": {
                        "chemical": "Mystery Chem",
                        "bin": "Review Queue",
                        "categories": [],
                        "container": "Secondary containment bin",
                        "storage": "Quarantine bench",
                        "ppe": "Standard PPE",
                        "segregation": "Do not mix",
                        "labeling": "Unidentified Chemical",
                        "spill": "Contain immediately",
                        "identification": "Unknown compound",
                        "prohibited": "Do not discard",
                        "verification": "EHS Characterization required",
                        "usepa": "Pending",
                        "india": "Pending",
                        "treatment": "Hold for testing",
                        "disposal": "Hold for testing",
                        "review_required": True,
                        "review_reason": "Classification failed or requires human review",
                    },
                },
            }

            with open(run_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta_data, f, indent=2)

            excel_path = generate_batch_excel(run_id, runs_dir=tmp_path)
            self.assertTrue(excel_path.exists())
            self.assertEqual(excel_path.name, "output.xlsx")

            wb = openpyxl.load_workbook(excel_path)
            self.assertEqual(wb.sheetnames, ["Management Plan", "Classification", "Review Required"])

            ws_mp = wb["Management Plan"]
            headers = [cell.value for cell in ws_mp[1]]
            self.assertEqual(len(headers), 14)
            self.assertEqual(headers[0], "Chemical")
            self.assertEqual(headers[1], "Recommended Container")
            self.assertEqual(headers[13], "Verification Required")
            self.assertEqual(ws_mp.max_row, 4)  # header + 3 chemicals

            ws_clf = wb["Classification"]
            clf_headers = [cell.value for cell in ws_clf[1]]
            self.assertEqual(clf_headers, ["Flammable", "Carcinogenic", "Infectious", "Toxic", "Corrosive"])

            ws_rev = wb["Review Required"]
            rev_headers = [cell.value for cell in ws_rev[1]]
            self.assertEqual(rev_headers, ["Chemical", "Review Reason"])
            self.assertEqual(ws_rev.max_row, 2)  # header + Mystery Chem
            self.assertEqual(ws_rev.cell(row=2, column=1).value, "Mystery Chem")

    def test_list_runs_and_get_run_details(self):
        from src.services import list_runs, get_run_details

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            run_id = "run_2026-10-29_090000"
            run_dir = tmp_path / run_id
            run_dir.mkdir(parents=True)

            meta_data = {
                "run_id": run_id,
                "filename": "inventory.xlsx",
                "timestamp": "2026-10-29T09:00:00",
                "status": "completed",
                "total_count": 1,
                "chemicals": ["Methanol"],
                "bin_counts": {"Flammable Solvents": 1},
                "dossiers": {
                    "Methanol": {
                        "chemical": "Methanol",
                        "bin": "Flammable Solvents",
                        "categories": ["Flammable"],
                        "container": "Glass Bottle",
                        "storage": "Cabinet",
                        "ppe": "Gloves",
                        "segregation": "Separate",
                        "labeling": "Flammable",
                        "spill": "Pads",
                        "identification": "Solvent",
                        "prohibited": "Drain",
                        "verification": "None",
                        "usepa": "D001",
                        "india": "Sched II",
                        "treatment": "Incineration",
                        "disposal": "TSDF",
                    }
                },
            }
            with open(run_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta_data, f, indent=2)

            runs = list_runs(runs_dir=tmp_path)
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["run_id"], run_id)
            self.assertEqual(runs[0]["filename"], "inventory.xlsx")
            self.assertEqual(runs[0]["total_count"], 1)

            details = get_run_details(run_id, runs_dir=tmp_path)
            self.assertEqual(details.run_id, run_id)
            self.assertEqual(len(details.items), 1)
            self.assertEqual(details.items[0].chemical, "Methanol")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_services.py`
Expected: FAIL with `ImportError: cannot import name 'generate_batch_excel' from 'src.services'`

- [ ] **Step 3: Define `RunSummaryResponse` in `src/models.py` and implement functions in `src/services.py`**

In `src/models.py`:
```python
class RunSummaryResponse(BaseModel):
    run_id: str
    filename: str
    timestamp: str
    total_count: int
    bin_counts: dict[str, int] = Field(default_factory=dict)
    status: str = "completed"
```

In `src/services.py`, implement `generate_batch_excel`, `list_runs`, and `get_run_details`:
```python
def generate_batch_excel(run_id: str, runs_dir: Path | None = None) -> Path:
    target_runs_dir = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR
    run_dir = target_runs_dir / run_id
    meta_path = run_dir / "meta.json"

    if not meta_path.exists():
        raise FileNotFoundError(f"Run '{run_id}' not found.")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    if meta.get("status") not in ("completed", None):
        raise ValueError(f"Run '{run_id}' is still in progress.")

    chemicals = meta.get("chemicals", [])
    dossiers = meta.get("dossiers", {})
    classifications = meta.get("classifications", {})

    # Sheet 1: Management Plan (14 fields matching institutional standard)
    management_rows = []
    for chem in chemicals:
        dos = dossiers.get(chem, {})
        management_rows.append({
            "Chemical": chem,
            "Recommended Container": dos.get("container", ""),
            "Storage Requirements": dos.get("storage", ""),
            "Handling & PPE": dos.get("ppe", ""),
            "Segregation & Incompatibilities": dos.get("segregation", ""),
            "Labeling Requirements": dos.get("labeling", ""),
            "Spill & Emergency Management": dos.get("spill", ""),
            "Identification & Characterization": dos.get("identification", ""),
            "USEPA RCRA Framework": dos.get("usepa", ""),
            "Indian HOWM Framework": dos.get("india", ""),
            "Treatment Framework": dos.get("treatment", ""),
            "Final Disposal Framework": dos.get("disposal", ""),
            "Prohibited / Unsafe Actions": dos.get("prohibited", ""),
            "Verification Required": dos.get("verification", ""),
        })

    # Sheet 2: Classification (5 hazard category columns matching classify_waste.py)
    hazard_categories = ["Flammable", "Carcinogenic", "Infectious", "Toxic", "Corrosive"]
    category_map = {cat: [] for cat in hazard_categories}
    for chem in chemicals:
        clf = classifications.get(chem, {})
        cats = clf.get("categories", [])
        if not cats:
            cats = dossiers.get(chem, {}).get("categories", [])
        for cat in cats:
            c_norm = cat.capitalize()
            if c_norm in category_map:
                category_map[c_norm].append(chem)

    max_len = max([len(v) for v in category_map.values()] or [0])
    clf_output = {}
    for cat in hazard_categories:
        items = category_map[cat]
        clf_output[cat] = items + [None] * (max_len - len(items))

    # Sheet 3: Review Required
    review_rows = []
    for chem in chemicals:
        dos = dossiers.get(chem, {})
        if dos.get("review_required") or dos.get("bin") == "Review Queue":
            review_rows.append({
                "Chemical": chem,
                "Review Reason": dos.get("review_reason") or "Classification or plan requires human review",
            })

    output_path = run_dir / "output.xlsx"
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(management_rows).to_excel(writer, sheet_name="Management Plan", index=False)
        pd.DataFrame(clf_output).to_excel(writer, sheet_name="Classification", index=False)
        pd.DataFrame(review_rows if review_rows else [], columns=["Chemical", "Review Reason"]).to_excel(
            writer, sheet_name="Review Required", index=False
        )

    return output_path


def list_runs(runs_dir: Path | None = None) -> list[dict]:
    target_runs_dir = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR
    if not target_runs_dir.exists():
        return []

    summaries = []
    for entry in target_runs_dir.iterdir():
        if entry.is_dir():
            meta_path = entry / "meta.json"
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    summaries.append({
                        "run_id": meta.get("run_id", entry.name),
                        "filename": meta.get("filename", "inventory.xlsx"),
                        "timestamp": meta.get("timestamp", entry.name),
                        "total_count": meta.get("total_count", 0),
                        "bin_counts": meta.get("bin_counts", {}),
                        "status": meta.get("status", "completed"),
                    })
                except Exception:
                    continue

    summaries.sort(key=lambda s: s.get("timestamp", s.get("run_id")), reverse=True)
    return summaries


def get_run_details(run_id: str, runs_dir: Path | None = None) -> BatchRunResponse:
    target_runs_dir = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR
    run_dir = target_runs_dir / run_id
    meta_path = run_dir / "meta.json"

    if not meta_path.exists():
        raise FileNotFoundError(f"Run '{run_id}' not found.")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    chemicals = meta.get("chemicals", [])
    dossiers = meta.get("dossiers", {})
    items = []
    for chem in chemicals:
        if chem in dossiers:
            items.append(WasteManagementDossier(**dossiers[chem]))

    return BatchRunResponse(
        run_id=meta.get("run_id", run_id),
        filename=meta.get("filename", "inventory.xlsx"),
        total_count=meta.get("total_count", len(items)),
        bin_counts=meta.get("bin_counts", {}),
        items=items,
    )
```
Also update `stream_batch_events` (line 459) and `remediate_batch_item` (line 570) to invoke `generate_batch_excel(run_id, target_runs_dir)` on run completion and post-remediation.

- [ ] **Step 4: Run test to verify it passes**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_services.py`
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit**

```bash
git add src/models.py src/services.py tests/test_services.py
git commit -m "feat(services): implement generate_batch_excel, list_runs, and get_run_details"
```

---

### Task 2: Excel Export & Run History Archive Endpoints in `src/app.py`

**Files:**
- Modify: `src/app.py:100-195`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `generate_batch_excel`, `list_runs`, `get_run_details` from `src/services.py`, `RunSummaryResponse`, `BatchRunResponse` from `src/models.py`.
- Produces:
  - `GET /api/runs`: Returns `list[RunSummaryResponse]`.
  - `GET /api/runs/{run_id}`: Returns `BatchRunResponse` (or 404).
  - `GET /api/runs/{run_id}/export`: Returns `FileResponse` with `.xlsx` attachment (or 404, 409).

- [ ] **Step 1: Write the failing tests in `tests/test_app.py`**

Add tests for the three new endpoints:

```python
    def test_list_runs_endpoint(self):
        # Create a mock run directory
        from src.services import DEFAULT_RUNS_DIR
        mock_id = "test_run_list_endpoint"
        mock_dir = DEFAULT_RUNS_DIR / mock_id
        mock_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(mock_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump({
                    "run_id": mock_id,
                    "filename": "test.xlsx",
                    "timestamp": "2026-10-29T12:00:00",
                    "total_count": 2,
                    "bin_counts": {"Flammable Solvents": 2},
                    "status": "completed",
                }, f)

            response = self.client.get("/api/runs")
            self.assertEqual(response.status_code, 200)
            runs = response.json()
            self.assertIsInstance(runs, list)
            match = next((r for r in runs if r["run_id"] == mock_id), None)
            self.assertIsNotNone(match)
            self.assertEqual(match["filename"], "test.xlsx")
            self.assertEqual(match["total_count"], 2)
        finally:
            shutil.rmtree(mock_dir, ignore_errors=True)

    def test_get_run_endpoint_success_and_not_found(self):
        from src.services import DEFAULT_RUNS_DIR
        mock_id = "test_run_get_details"
        mock_dir = DEFAULT_RUNS_DIR / mock_id
        mock_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(mock_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump({
                    "run_id": mock_id,
                    "filename": "lab.xlsx",
                    "timestamp": "2026-10-29T12:00:00",
                    "total_count": 1,
                    "bin_counts": {"Flammable Solvents": 1},
                    "status": "completed",
                    "chemicals": ["Ethanol"],
                    "dossiers": {
                        "Ethanol": {
                            "chemical": "Ethanol",
                            "bin": "Flammable Solvents",
                            "categories": ["Flammable"],
                            "container": "Glass",
                            "storage": "Cabinet",
                            "ppe": "Gloves",
                            "segregation": "Oxidizers",
                            "labeling": "Flammable",
                            "spill": "Absorb",
                            "identification": "Alcohol",
                            "prohibited": "Drain",
                            "verification": "None",
                            "usepa": "D001",
                            "india": "Sched II",
                            "treatment": "Thermal",
                            "disposal": "TSDF",
                        }
                    }
                }, f)

            response = self.client.get(f"/api/runs/{mock_id}")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["run_id"], mock_id)
            self.assertEqual(len(data["items"]), 1)
            self.assertEqual(data["items"][0]["chemical"], "Ethanol")

            # 404 for unknown run
            resp_404 = self.client.get("/api/runs/non_existent_run_12345")
            self.assertEqual(resp_404.status_code, 404)
        finally:
            shutil.rmtree(mock_dir, ignore_errors=True)

    def test_export_run_excel_endpoint_success_and_in_progress_guard(self):
        from src.services import DEFAULT_RUNS_DIR
        mock_id = "test_run_export_excel"
        mock_dir = DEFAULT_RUNS_DIR / mock_id
        mock_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(mock_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump({
                    "run_id": mock_id,
                    "filename": "sample.xlsx",
                    "timestamp": "2026-10-29T12:00:00",
                    "total_count": 1,
                    "bin_counts": {"Flammable Solvents": 1},
                    "status": "completed",
                    "chemicals": ["Ethanol"],
                    "dossiers": {
                        "Ethanol": {
                            "chemical": "Ethanol",
                            "bin": "Flammable Solvents",
                            "categories": ["Flammable"],
                            "container": "Glass",
                            "storage": "Cabinet",
                            "ppe": "Gloves",
                            "segregation": "Oxidizers",
                            "labeling": "Flammable",
                            "spill": "Absorb",
                            "identification": "Alcohol",
                            "prohibited": "Drain",
                            "verification": "None",
                            "usepa": "D001",
                            "india": "Sched II",
                            "treatment": "Thermal",
                            "disposal": "TSDF",
                        }
                    }
                }, f)

            response = self.client.get(f"/api/runs/{mock_id}/export")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.headers.get("content-type"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            self.assertIn("hazardous_waste_management_plan_test_run_export_excel.xlsx", response.headers.get("content-disposition", ""))
            self.assertGreater(len(response.content), 1000)

            # 409 guard for in-progress run
            with open(mock_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump({"run_id": mock_id, "status": "planning"}, f)

            resp_in_progress = self.client.get(f"/api/runs/{mock_id}/export")
            self.assertEqual(resp_in_progress.status_code, 409)
        finally:
            shutil.rmtree(mock_dir, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: FAIL with 404 or 405 on `/api/runs` and `/api/runs/{run_id}/export`

- [ ] **Step 3: Implement endpoints in `src/app.py`**

In `src/app.py`:
```python
from fastapi.responses import FileResponse
from src.models import (
    WasteManagementDossier,
    BatchRunResponse,
    BatchQueuedResponse,
    RetryItemRequest,
    RetryItemResponse,
    RunSummaryResponse,
)
from src.services import (
    lookup_chemical,
    process_excel_batch,
    initialize_batch_run,
    stream_batch_events,
    remediate_batch_item,
    generate_batch_excel,
    list_runs,
    get_run_details,
)

@app.get("/api/runs", response_model=list[RunSummaryResponse])
async def get_runs_history():
    return list_runs()


@app.get("/api/runs/{run_id}", response_model=BatchRunResponse)
async def get_run(run_id: str):
    try:
        return get_run_details(run_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")


@app.get("/api/runs/{run_id}/export")
async def export_run_excel(run_id: str):
    try:
        excel_path = generate_batch_excel(run_id)
        return FileResponse(
            path=excel_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"hazardous_waste_management_plan_{run_id}.xlsx",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/app.py tests/test_app.py
git commit -m "feat(app): add /api/runs, /api/runs/{run_id}, and /api/runs/{run_id}/export endpoints"
```

---

### Task 3: Run History Drawer, Excel Export & Filtered CSV in `src/templates/index.html`

**Files:**
- Modify: `src/templates/index.html`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `/api/runs`, `/api/runs/{run_id}`, `/api/runs/{run_id}/export`.
- Produces:
  - Header button: `[ 🕒 Run History (N) ]` opening the left slide-over drawer.
  - Left slide-over drawer: displays past runs with date, filename, item counts, miniature bin badges, `[ 👁️ Load Batch ]`, and `[ 📥 .xlsx ]` export link; friendly empty state if 0 runs.
  - Batch summary header export buttons:
    - `[ 📊 Export Excel (.xlsx) ]` (direct link to `/api/runs/${activeBatch.run_id}/export`)
    - `[ 📄 Export Filtered CSV ]` (triggers `exportFilteredCsv()`)
  - Alpine.js `hazWasteApp()` properties & methods:
    - `historyDrawerOpen`: boolean
    - `runHistory`: array of runs
    - `fetchRunHistory()`: fetches `/api/runs`
    - `openRunHistory()`: sets `historyDrawerOpen = true`, refreshes history
    - `loadRun(runId)`: loads batch from `/api/runs/{runId}`, sets `activeBatch`, clears search/filter state, closes drawer
    - `exportFilteredCsv()`: serializes `filteredItems` to RFC 4180 CSV blob and triggers download

- [ ] **Step 1: Write template assertion tests in `tests/test_app.py`**

Add `test_template_contains_run_history_archive_and_export_buttons`:

```python
    def test_template_contains_run_history_archive_and_export_buttons(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.text

        # Header Run History button
        self.assertIn("Run History", html)
        self.assertIn("openRunHistory", html)

        # Run History left drawer
        self.assertIn("historyDrawerOpen", html)
        self.assertIn("Run History Archive", html)
        self.assertIn("loadRun", html)

        # Batch summary export buttons
        self.assertIn("Export Excel (.xlsx)", html)
        self.assertIn("exportFilteredCsv", html)
        self.assertIn("Export Filtered CSV", html)

        # Alpine JS methods
        self.assertIn("fetchRunHistory", html)
        self.assertIn("exportFilteredCsv()", html)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: FAIL with `AssertionError: 'Run History' not found in html`

- [ ] **Step 3: Implement Run History Drawer and Export Controls in `src/templates/index.html`**

1. In the global header (around line 60), add the `Run History` toggle button:
```html
        <button @click="openRunHistory()"
                class="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-xs font-medium transition border border-slate-700 flex items-center gap-1.5 shadow-sm">
          <span>🕒</span>
          <span>Run History</span>
          <span class="px-1.5 py-0.2 rounded-full font-mono text-[10px] bg-slate-700 text-emerald-400 font-bold" x-text="runHistory.length"></span>
        </button>
```

2. In the Batch Summary Header button group (next to "Upload New Batch"), add the export buttons:
```html
            <div class="flex flex-wrap items-center gap-2.5">
              <!-- Export Excel (.xlsx) -->
              <a :href="'/api/runs/' + activeBatch.run_id + '/export'"
                 download
                 class="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition flex items-center gap-1.5 shadow-md shadow-emerald-950/40">
                <span>📊</span>
                <span>Export Excel (.xlsx)</span>
              </a>

              <!-- Export Filtered CSV -->
              <button @click="exportFilteredCsv()"
                      class="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white rounded-lg text-xs font-medium transition border border-slate-700 flex items-center gap-1.5">
                <span>📄</span>
                <span>Export Filtered CSV</span>
              </button>

              <button @click="uploadModalOpen = true"
                      class="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white rounded-lg text-xs font-medium transition border border-slate-700 flex items-center gap-1.5">
                <span>📁</span>
                <span>Upload New Batch</span>
              </button>
            </div>
```

3. Add the left slide-over Run History Drawer:
```html
  <!-- Left Slide-over Run History Archive Drawer -->
  <div x-show="historyDrawerOpen"
       class="fixed inset-0 z-50 overflow-hidden"
       x-cloak>
    <!-- Dark Backdrop -->
    <div x-show="historyDrawerOpen"
         x-transition:enter="ease-out duration-300"
         x-transition:enter-start="opacity-0"
         x-transition:enter-end="opacity-100"
         x-transition:leave="ease-in duration-200"
         x-transition:leave-start="opacity-100"
         x-transition:leave-end="opacity-0"
         @click="historyDrawerOpen = false"
         class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm transition-opacity"></div>

    <div class="fixed inset-y-0 left-0 max-w-full flex">
      <div x-show="historyDrawerOpen"
           x-transition:enter="transform transition ease-in-out duration-300"
           x-transition:enter-start="-translate-x-full"
           x-transition:enter-end="translate-x-0"
           x-transition:leave="transform transition ease-in-out duration-300"
           x-transition:leave-start="translate-x-0"
           x-transition:leave-end="-translate-x-full"
           class="w-screen max-w-md bg-slate-900 border-r border-slate-800 shadow-2xl flex flex-col">

        <!-- Drawer Header -->
        <div class="p-6 border-b border-slate-800 flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <span class="text-xl">🕒</span>
            <div>
              <h2 class="text-lg font-bold text-white tracking-tight">Run History Archive</h2>
              <p class="text-xs text-slate-400">Past laboratory inventory evaluations</p>
            </div>
          </div>
          <button @click="historyDrawerOpen = false"
                  class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition">
            ✕
          </button>
        </div>

        <!-- Drawer Body -->
        <div class="flex-1 overflow-y-auto p-6 space-y-4">
          <!-- Empty State -->
          <template x-if="runHistory.length === 0">
            <div class="text-center py-12 px-4 rounded-xl border border-dashed border-slate-800 bg-slate-950/40 space-y-3">
              <span class="text-3xl">📂</span>
              <h3 class="text-sm font-semibold text-slate-200">No Past Batch Runs Found</h3>
              <p class="text-xs text-slate-400 max-w-xs mx-auto">
                Upload a chemical inventory workbook to generate and archive your first compliant waste evaluation.
              </p>
              <button @click="historyDrawerOpen = false; uploadModalOpen = true"
                      class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition inline-flex items-center gap-1.5 shadow-md shadow-emerald-950/40">
                <span>📁</span>
                <span>Upload Batch (.xlsx)</span>
              </button>
            </div>
          </template>

          <!-- Run Cards -->
          <template x-for="run in runHistory" :key="run.run_id">
            <div :class="activeBatch && activeBatch.run_id === run.run_id ? 'border-emerald-500/50 bg-emerald-950/10 ring-1 ring-emerald-500/30' : 'border-slate-800 bg-slate-950/60'"
                 class="rounded-xl border p-4 space-y-3 hover:border-slate-700 transition">
              <div class="flex items-start justify-between gap-2">
                <div>
                  <div class="flex items-center gap-2">
                    <span class="font-semibold text-sm text-white flex items-center gap-1.5">
                      <span>📑</span>
                      <span x-text="run.filename"></span>
                    </span>
                    <template x-if="activeBatch && activeBatch.run_id === run.run_id">
                      <span class="text-[10px] font-mono font-bold uppercase px-1.5 py-0.2 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">Active</span>
                    </template>
                  </div>
                  <div class="text-[11px] font-mono text-slate-400 mt-0.5" x-text="formatDate(run.timestamp)"></div>
                </div>
                <span class="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 whitespace-nowrap">
                  <span x-text="run.total_count"></span> chemicals
                </span>
              </div>

              <!-- Mini Bin Pills -->
              <div class="flex flex-wrap gap-1.5 text-[10px] font-mono">
                <template x-for="(count, bin) in run.bin_counts" :key="bin">
                  <span class="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
                    <span x-text="bin"></span>: <span class="font-bold text-white" x-text="count"></span>
                  </span>
                </template>
              </div>

              <!-- Actions -->
              <div class="flex items-center justify-between gap-2 pt-2 border-t border-slate-800/80">
                <button @click="loadRun(run.run_id)"
                        class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white rounded-lg text-xs font-medium transition border border-slate-700 flex items-center gap-1">
                  <span>👁️</span>
                  <span>Load Batch</span>
                </button>
                <a :href="'/api/runs/' + run.run_id + '/export'"
                   download
                   class="px-2.5 py-1.5 bg-slate-800/80 hover:bg-emerald-950/60 text-slate-300 hover:text-emerald-300 rounded-lg text-xs font-mono transition border border-slate-700/80 hover:border-emerald-700/60 flex items-center gap-1">
                  <span>📥</span>
                  <span>.xlsx</span>
                </a>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
```

4. In the Alpine.js `hazWasteApp()` object:
```javascript
        historyDrawerOpen: false,
        runHistory: [],

        async fetchRunHistory() {
          try {
            const resp = await fetch('/api/runs');
            if (resp.ok) {
              this.runHistory = await resp.json();
            }
          } catch (e) {
            console.error('Failed to fetch run history:', e);
          }
        },

        openRunHistory() {
          this.fetchRunHistory();
          this.historyDrawerOpen = true;
        },

        async loadRun(runId) {
          try {
            const resp = await fetch(`/api/runs/${runId}`);
            if (!resp.ok) throw new Error(`Failed to load run ${runId}`);
            const data = await resp.json();
            this.activeBatch = data;
            this.batchSearchQuery = '';
            this.activeHazardFilters = [];
            this.historyDrawerOpen = false;
          } catch (e) {
            alert(e.message);
          }
        },

        formatDate(isoStr) {
          if (!isoStr) return '';
          try {
            const d = new Date(isoStr);
            return isNaN(d.getTime()) ? isoStr : d.toLocaleString();
          } catch {
            return isoStr;
          }
        },

        exportFilteredCsv() {
          if (!this.filteredItems || this.filteredItems.length === 0) {
            alert('No items match current filters to export.');
            return;
          }
          const headers = [
            'Chemical',
            'Physical Segregation Bin',
            'Hazard Categories',
            'Recommended Container',
            'Storage Requirements',
            'Handling & PPE',
            'Segregation & Incompatibilities',
            'Labeling Requirements',
            'USEPA RCRA Framework',
            'Indian HOWM Framework',
            'Treatment Framework',
            'Final Disposal Framework',
            'Review Required'
          ];

          const escapeCsv = (str) => {
            if (str === null || str === undefined) return '""';
            const s = String(str).replace(/"/g, '""');
            return `"${s}"`;
          };

          const rows = this.filteredItems.map(item => [
            escapeCsv(item.chemical),
            escapeCsv(item.segregation_bin || item.bin),
            escapeCsv((item.categories || []).join('; ')),
            escapeCsv(item.recommended_container || item.container),
            escapeCsv(item.storage),
            escapeCsv(item.ppe),
            escapeCsv(item.segregation),
            escapeCsv(item.labeling),
            escapeCsv(item.usepa),
            escapeCsv(item.india),
            escapeCsv(item.treatment),
            escapeCsv(item.disposal),
            escapeCsv(item.review_required ? 'YES' : 'NO')
          ].join(','));

          const csvContent = [headers.map(escapeCsv).join(','), ...rows].join('\r\n');
          const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          const filename = `${this.activeBatch?.run_id || 'batch'}_filtered.csv`;
          link.setAttribute('href', url);
          link.setAttribute('download', filename);
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          URL.revokeObjectURL(url);
        },
```
Call `this.fetchRunHistory()` in `init()`, and also refresh `fetchRunHistory()` inside `handleStreamComplete()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/templates/index.html tests/test_app.py
git commit -m "feat(ui): add Run History drawer, Excel export link, and client-side filtered CSV export"
```

---

### Task 4: End-to-End Archive & Export Parity Integration Test

**Files:**
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: Complete API (`POST /api/upload`, `GET /api/runs`, `GET /api/runs/{run_id}`, `GET /api/runs/{run_id}/export`, `POST /api/runs/{run_id}/retry`).
- Produces: Comprehensive integration verification test covering upload -> run completion -> history indexing -> 3-sheet Excel parity assertion -> remediation -> re-export verification.

- [ ] **Step 1: Write integration test `test_e2e_archive_indexing_and_excel_export_parity` in `tests/test_app.py`**

```python
    def test_e2e_archive_indexing_and_excel_export_parity(self):
        import openpyxl
        from unittest.mock import patch
        from src.models import WasteManagementDossier, HazardClassification, ManagementPlan

        # 1. Create a sample batch workbook with 2 chemicals
        buf = io.BytesIO()
        df = pd.DataFrame({"Chemical": ["Toluene", "Nitric Acid"]})
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)

        # 2. Upload batch and process
        with patch("src.services.classify_chemical") as mock_clf, \
             patch("src.services.make_plan") as mock_plan:

            mock_clf.side_effect = lambda chem, client=None: (
                HazardClassification(chemical="Toluene", flammable=True, toxic=True)
                if chem == "Toluene" else
                HazardClassification(chemical="Nitric Acid", corrosive=True)
            )

            mock_plan.side_effect = lambda chem, cats, client=None: (
                ManagementPlan(
                    recommended_container="Safety can",
                    storage_requirements="Flammable cabinet",
                    handling_and_ppe="Nitrile gloves",
                    segregation_and_incompatibilities="Avoid oxidizers",
                    labeling_requirements="Flammable Liquid",
                    spill_and_emergency_management="Absorb with pads",
                    identification_and_characterization="Aromatic hydrocarbon",
                    prohibited_or_unsafe_actions="Do not pour in sink",
                    verification_required="Visual check",
                    usepa_framework="D001",
                    indian_framework="HOWM Schedule II",
                    treatment_framework="Incineration",
                    final_disposal_framework="Licensed TSDF",
                ) if chem == "Toluene" else
                ManagementPlan(
                    recommended_container="Acid bottle",
                    storage_requirements="Acid locker",
                    handling_and_ppe="Acid suit",
                    segregation_and_incompatibilities="Avoid bases",
                    labeling_requirements="Corrosive",
                    spill_and_emergency_management="Neutralize",
                    identification_and_characterization="Inorganic acid",
                    prohibited_or_unsafe_actions="Do not mix with organic",
                    verification_required="pH strip",
                    usepa_framework="D002",
                    indian_framework="HOWM Schedule II",
                    treatment_framework="Neutralization",
                    final_disposal_framework="Licensed facility",
                )
            )

            upload_resp = self.client.post(
                "/api/upload",
                files={"file": ("e2e_archive_test.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            self.assertEqual(upload_resp.status_code, 200)
            run_id = upload_resp.json()["run_id"]

            # Consume stream to completion
            stream_resp = self.client.get(f"/api/runs/{run_id}/stream")
            self.assertEqual(stream_resp.status_code, 200)
            events = [line for line in stream_resp.iter_lines() if line]
            self.assertTrue(any("complete" in e for e in events))

        # 3. Verify run appears in GET /api/runs
        runs_resp = self.client.get("/api/runs")
        self.assertEqual(runs_resp.status_code, 200)
        run_ids = [r["run_id"] for r in runs_resp.json()]
        self.assertIn(run_id, run_ids)

        # 4. Verify run details in GET /api/runs/{run_id}
        details_resp = self.client.get(f"/api/runs/{run_id}")
        self.assertEqual(details_resp.status_code, 200)
        data = details_resp.json()
        self.assertEqual(data["run_id"], run_id)
        self.assertEqual(len(data["items"]), 2)

        # 5. Verify Excel export parity in GET /api/runs/{run_id}/export
        export_resp = self.client.get(f"/api/runs/{run_id}/export")
        self.assertEqual(export_resp.status_code, 200)
        self.assertEqual(
            export_resp.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn(f"hazardous_waste_management_plan_{run_id}.xlsx", export_resp.headers["content-disposition"])

        wb = openpyxl.load_workbook(io.BytesIO(export_resp.content))
        self.assertEqual(wb.sheetnames, ["Management Plan", "Classification", "Review Required"])

        ws_mp = wb["Management Plan"]
        self.assertEqual(ws_mp.max_row, 3)  # header + 2 chemicals
        self.assertEqual(ws_mp.cell(row=1, column=1).value, "Chemical")
        self.assertEqual(ws_mp.cell(row=1, column=14).value, "Verification Required")

        ws_clf = wb["Classification"]
        self.assertEqual([c.value for c in ws_clf[1]], ["Flammable", "Carcinogenic", "Infectious", "Toxic", "Corrosive"])

        ws_rev = wb["Review Required"]
        self.assertEqual([c.value for c in ws_rev[1]], ["Chemical", "Review Reason"])
```

- [ ] **Step 2: Run test to verify it passes**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: PASS

- [ ] **Step 3: Run the full test suite across the entire repository**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest discover -s tests -v`
Expected: All tests pass (60+ tests passing)

- [ ] **Step 4: Commit**

```bash
git add tests/test_app.py
git commit -m "test(e2e): verify batch archive indexing and 3-sheet Excel export parity"
```

---

### Task 5: Issue Tracker Closure & Documentation Verification

**Files:**
- Modify: `.scratch/frontend/issues/06-excel-export-and-run-history-archive.md`

- [ ] **Step 1: Update Ticket 06 status and checklist in issue tracker**

Mark all acceptance criteria checked (`[x]`) and set `Status: closed` in `.scratch/frontend/issues/06-excel-export-and-run-history-archive.md`.

- [ ] **Step 2: Commit**

```bash
git add .scratch/frontend/issues/06-excel-export-and-run-history-archive.md
git commit -m "docs(issue): close Ticket 06 multi-sheet excel export and run history archive"
```
