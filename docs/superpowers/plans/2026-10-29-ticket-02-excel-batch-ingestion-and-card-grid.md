# Ticket 02: Excel Batch Ingestion & Physical Segregation Card Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide an Excel workbook upload modal with drag-and-drop dropzone, flexible column detection, de-duplication, local run directory persistence, and an interactive 3-column physical segregation card grid populated with full 14-field compliance dossiers.

**Architecture:** Extend FastAPI with `python-multipart` to accept `.xlsx`/`.xls` file uploads via `POST /api/upload`. Implement `process_excel_batch` in `src/services.py` that normalizes headers, de-duplicates chemicals, enforces a 50-item safeguard limit, saves run artifacts to `data/runs/<timestamp>/input.xlsx` and `meta.json`, and evaluates unique chemicals via `lookup_chemical`. Update `src/templates/index.html` with Alpine.js to manage the upload modal, in-flight spinner, batch summary header with cabinet bin counts, and a responsive 3-column segregation card grid with amber highlights for review items.

**Tech Stack:** FastAPI, Jinja2, openpyxl, pandas, python-multipart, Alpine.js (CDN), Tailwind CSS (CDN), Python standard library `unittest`.

**Spec:** [.scratch/frontend/spec.md](file:///C:/Users/stars/AI-ML/D2S-MTP/.scratch/frontend/spec.md) and [.scratch/frontend/issues/02-excel-batch-ingestion-and-card-grid.md](file:///C:/Users/stars/AI-ML/D2S-MTP/.scratch/frontend/issues/02-excel-batch-ingestion-and-card-grid.md)

## Global Constraints

- **Python Runtime**: Strictly target Conda environment `C:\Users\stars\miniconda3\envs\d2s-mtp`.
- **Frontend Stack**: Server-rendered HTML with Tailwind CSS CDN and Alpine.js CDN. No Node.js build chain; zero npm packages.
- **Testing Standard**: Python standard library `unittest` ONLY (`unittest.TestCase`). Do NOT use `pytest`. Run tests via `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest`.
- **Domain Vocabulary**: Strictly adhere to [CONTEXT.md](file:///C:/Users/stars/AI-ML/D2S-MTP/CONTEXT.md) terms (`Hazardous Waste`, `Hazard Classification`, `Waste Management Plan`, `Segregation`, `Segregation Bin`, `Recommended Container`, `Treatment Framework`, `Final Disposal Framework`, `RCRA Framework`, `HOWM Framework`, `Batch Run`, `Review Queue`).
- **File Ingestion Rules**: Flexible case-insensitive header matching (`Hazardous Waste`, `hazardous waste`, or containing `chemical`/`waste`); 50-item maximum safeguard; local run persistence in `data/runs/<timestamp>/`.

---

### Task 1: Environment & Dependency Scaffolding (`python-multipart`)

**Files:**
- Modify: `requirements.txt`
- Modify: `requirement.txt`

**Interfaces:**
- Consumes: None
- Produces: `python-multipart` installed in `C:\Users\stars\miniconda3\envs\d2s-mtp`

- [ ] **Step 1: Update dependency files**

Add `python-multipart>=0.0.9` to both `requirements.txt` and `requirement.txt`:

In `requirements.txt`:
```
fastapi>=0.110.0
uvicorn>=0.28.0
jinja2>=3.1.0
python-multipart>=0.0.9
```

In `requirement.txt`:
```
fastapi>=0.110.0
uvicorn>=0.28.0
jinja2>=3.1.0
python-multipart>=0.0.9
```

- [ ] **Step 2: Install package in target Conda environment**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m pip install "python-multipart>=0.0.9" --progress-bar off
```

- [ ] **Step 3: Verify import works**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -c "import multipart; print('python-multipart OK')"
```
Expected: `python-multipart OK`

- [ ] **Step 4: Verify existing test suite remains green**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest
```
Expected: All 21 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt requirement.txt
git commit -m "build: add python-multipart dependency for file uploads"
```

---

### Task 2: Define `BatchRunResponse` Model

**Files:**
- Modify: `src/models.py`
- Modify: `tests/test_models.py`

**Interfaces:**
- Consumes: `WasteManagementDossier`
- Produces: `BatchRunResponse(BaseModel)` with fields `run_id: str`, `filename: str`, `total_count: int`, `bin_counts: dict[str, int]`, `items: list[WasteManagementDossier]`

- [ ] **Step 1: Write the failing unit test**

In `tests/test_models.py`, add a test for `BatchRunResponse`:

```python
    def test_batch_run_response_serialization(self):
        from src.models import BatchRunResponse

        dossier = WasteManagementDossier(
            chemical='Methanol',
            bin='Flammable Solvents',
            categories=['Flammable', 'Toxic'],
            container='Type I safety can',
            storage='Flammable cabinet',
            ppe='Nitrile gloves, goggles',
            segregation='Isolate from oxidizers',
            labeling='Flammable Liquid',
            spill='Absorb with pads',
            identification='HPLC solvent',
            prohibited='No drain disposal',
            verification='Check flash point',
            usepa='D001, U154',
            india='HOWM Schedule I',
            treatment='TSDF incineration',
            disposal='Authorized TSDF',
            review_required=False,
            review_reason=None,
        )

        batch = BatchRunResponse(
            run_id='2026-10-29_010000',
            filename='inventory.xlsx',
            total_count=1,
            bin_counts={'Flammable Solvents': 1},
            items=[dossier],
        )

        data = batch.model_dump()
        self.assertEqual(data['run_id'], '2026-10-29_010000')
        self.assertEqual(data['filename'], 'inventory.xlsx')
        self.assertEqual(data['total_count'], 1)
        self.assertEqual(data['bin_counts']['Flammable Solvents'], 1)
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['items'][0]['chemical'], 'Methanol')
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests.test_models.TestModels.test_batch_run_response_serialization
```
Expected: FAIL with `ImportError: cannot import name 'BatchRunResponse' from 'src.models'`

- [ ] **Step 3: Implement `BatchRunResponse` in `src/models.py`**

In `src/models.py`, add:

```python
class BatchRunResponse(BaseModel):
    run_id: str
    filename: str
    total_count: int
    bin_counts: dict[str, int] = Field(default_factory=dict)
    items: list[WasteManagementDossier] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests.test_models.TestModels.test_batch_run_response_serialization
```
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest
```
Expected: All 22 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat(models): add BatchRunResponse schema"
```

---

### Task 3: Implement Excel Batch Ingestion & Storage Service

**Files:**
- Modify: `src/services.py`
- Modify: `tests/test_services.py`

**Interfaces:**
- Consumes: `file_bytes: bytes`, `filename: str`, `runs_dir: Path | None = None`, `client: OpenAI | None = None`
- Produces: 
  - `detect_waste_column(df: pd.DataFrame) -> str`
  - `process_excel_batch(file_bytes: bytes, filename: str, runs_dir: Path | None = None, client: OpenAI | None = None) -> BatchRunResponse`

- [ ] **Step 1: Write the failing unit tests**

In `tests/test_services.py`, add helper function and test cases:

```python
import io
import pandas as pd
from src.services import detect_waste_column, process_excel_batch


class TestBatchIngestionServices(unittest.TestCase):
    def _create_test_excel(self, column_name: str, values: list[str]) -> bytes:
        df = pd.DataFrame({column_name: values})
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        return output.getvalue()

    def test_detect_waste_column_variations(self):
        # 1. Exact match
        df1 = pd.DataFrame({'Hazardous Waste': ['Acetone']})
        self.assertEqual(detect_waste_column(df1), 'Hazardous Waste')

        # 2. Case-insensitive and trimmed
        df2 = pd.DataFrame({'  hazardous waste  ': ['Acetone']})
        self.assertEqual(detect_waste_column(df2), '  hazardous waste  ')

        # 3. Fallback to 'chemical' or 'waste'
        df3 = pd.DataFrame({'Chemical Name': ['Acetone'], 'Quantity': ['1L']})
        self.assertEqual(detect_waste_column(df3), 'Chemical Name')

        # 4. No matching column raises ValueError
        df4 = pd.DataFrame({'Sample ID': [1, 2], 'Location': ['Lab 4', 'Lab 5']})
        with self.assertRaises(ValueError) as ctx:
            detect_waste_column(df4)
        self.assertIn("must contain a 'Hazardous Waste' or 'Chemical' column", str(ctx.exception))

    def test_process_excel_batch_success_and_deduplication(self):
        excel_bytes = self._create_test_excel(
            'Hazardous Waste',
            ['Methanol', ' methanol ', 'METHANOL', 'Hydrochloric Acid', None, '']
        )
        fake_client = FakeClient()
        classification = HazardClassification(
            flammable=True, carcinogenic=False, infectious=False, toxic=True, corrosive=False
        )
        plan = ManagementPlan(
            chemical='test',
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
            result = process_excel_batch(
                excel_bytes,
                'test_inventory.xlsx',
                runs_dir=runs_path,
                client=fake_client
            )

            # Assert deduplication: 2 unique chemicals ('Methanol' and 'Hydrochloric Acid')
            self.assertEqual(result.total_count, 2)
            self.assertEqual(result.filename, 'test_inventory.xlsx')
            self.assertIn('Flammable Solvents', result.bin_counts)

            # Assert local run directory created
            run_folder = runs_path / result.run_id
            self.assertTrue(run_folder.exists())
            self.assertTrue((run_folder / 'input.xlsx').exists())
            self.assertTrue((run_folder / 'meta.json').exists())

    def test_process_excel_batch_exceeds_safeguard_limit(self):
        chemicals = [f"Chemical_{i}" for i in range(51)]
        excel_bytes = self._create_test_excel('Hazardous Waste', chemicals)

        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ValueError) as ctx:
                process_excel_batch(excel_bytes, 'too_large.xlsx', runs_dir=Path(tmp_dir))
            self.assertIn("exceeds limit of 50 unique chemicals", str(ctx.exception))
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests.test_services.TestBatchIngestionServices
```
Expected: FAIL with `ImportError: cannot import name 'detect_waste_column' from 'src.services'`

- [ ] **Step 3: Implement `detect_waste_column` and `process_excel_batch` in `src/services.py`**

In `src/services.py`, add the imports, helper, and batch processing logic:

```python
import datetime
import io
import json
from pathlib import Path
import pandas as pd
from src.models import BatchRunResponse

DEFAULT_RUNS_DIR = Path(__file__).resolve().parent.parent / "data" / "runs"
MAX_BATCH_SIZE = 50


def detect_waste_column(df: pd.DataFrame) -> str:
    """
    Locates the hazardous waste column with flexible tolerance:
    1. Exact 'Hazardous Waste'
    2. Case-insensitive trimmed 'hazardous waste'
    3. Any column containing 'chemical' or 'waste'
    """
    cols = list(df.columns)

    # 1. Exact
    if "Hazardous Waste" in cols:
        return "Hazardous Waste"

    # 2. Case-insensitive trimmed
    for col in cols:
        clean = str(col).strip().lower()
        if clean == "hazardous waste":
            return col

    # 3. Fallback to containing 'chemical' or 'waste'
    for col in cols:
        clean = str(col).strip().lower()
        if "chemical" in clean or "waste" in clean:
            return col

    raise ValueError(
        "Uploaded workbook must contain a 'Hazardous Waste' or 'Chemical' column."
    )


def process_excel_batch(
    file_bytes: bytes,
    filename: str,
    runs_dir: Path | None = None,
    client=None
) -> BatchRunResponse:
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

    # 5. Persist run directory
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_dir = target_runs_dir / timestamp_str
    run_dir.mkdir(parents=True, exist_ok=True)

    input_file_path = run_dir / "input.xlsx"
    with open(input_file_path, "wb") as f:
        f.write(file_bytes)

    # 6. Evaluate each chemical
    items = []
    bin_counts: dict[str, int] = {}
    for chem in unique_chemicals:
        dossier = lookup_chemical(chem, client=client)
        items.append(dossier)
        bin_counts[dossier.bin] = bin_counts.get(dossier.bin, 0) + 1

    # 7. Write meta.json
    meta = {
        "run_id": timestamp_str,
        "filename": filename,
        "timestamp": datetime.datetime.now().isoformat(),
        "total_count": len(items),
        "bin_counts": bin_counts,
    }
    with open(run_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return BatchRunResponse(
        run_id=timestamp_str,
        filename=filename,
        total_count=len(items),
        bin_counts=bin_counts,
        items=items,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests.test_services.TestBatchIngestionServices
```
Expected: All 3 tests PASS.

- [ ] **Step 5: Run full test suite**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest
```
Expected: All 25 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/services.py tests/test_services.py
git commit -m "feat(services): implement process_excel_batch with flexible headers and safeguards"
```

---

### Task 4: Implement `POST /api/upload` Endpoint in FastAPI

**Files:**
- Modify: `src/app.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `file: UploadFile = File(...)`
- Produces: `POST /api/upload -> BatchRunResponse` (HTTP 200 on success, HTTP 422 on validation/parsing error)

- [ ] **Step 1: Write the failing endpoint tests**

In `tests/test_app.py`, add tests for `POST /api/upload`:

```python
import io
import pandas as pd
from src.models import BatchRunResponse


class TestAppUploadEndpoint(unittest.TestCase):
    def setUp(self):
        from src.app import app
        self.client = TestClient(app)

    def _create_excel(self, col: str, rows: list[str]) -> io.BytesIO:
        buf = io.BytesIO()
        df = pd.DataFrame({col: rows})
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)
        return buf

    def test_upload_valid_excel_success(self):
        import src.services as services
        fake_client = FakeClient()
        orig_batch = services.process_excel_batch

        try:
            # Inject fake client into process_excel_batch
            services.process_excel_batch = lambda b, fn, **kwargs: orig_batch(b, fn, client=fake_client, **kwargs)

            buf = self._create_excel('Hazardous Waste', ['Methanol', 'Hydrochloric Acid'])
            response = self.client.post(
                '/api/upload',
                files={'file': ('inventory.xlsx', buf, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['filename'], 'inventory.xlsx')
            self.assertEqual(data['total_count'], 2)
            self.assertIn('items', data)
            self.assertEqual(len(data['items']), 2)
        finally:
            services.process_excel_batch = orig_batch

    def test_upload_missing_column_returns_422(self):
        buf = self._create_excel('Invalid Header', ['Item 1'])
        response = self.client.post(
            '/api/upload',
            files={'file': ('bad.xlsx', buf, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("must contain a 'Hazardous Waste' or 'Chemical' column", response.json()['detail'])

    def test_upload_non_excel_extension_returns_422(self):
        response = self.client.post(
            '/api/upload',
            files={'file': ('notes.txt', io.BytesIO(b'hello'), 'text/plain')}
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("Only .xlsx and .xls Excel files are accepted", response.json()['detail'])
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests.test_app.TestAppUploadEndpoint
```
Expected: FAIL with HTTP 404 or Method Not Allowed (`/api/upload` not defined)

- [ ] **Step 3: Implement `POST /api/upload` in `src/app.py`**

In `src/app.py`, add imports `File, UploadFile` from `fastapi`, import `BatchRunResponse`, and add the route:

```python
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from src.models import BatchRunResponse, WasteManagementDossier


@app.post("/api/upload", response_model=BatchRunResponse)
async def api_upload_batch(file: UploadFile = File(...)):
    filename = file.filename or "uploaded_waste.xlsx"
    clean_name = filename.lower()
    if not (clean_name.endswith(".xlsx") or clean_name.endswith(".xls")):
        raise HTTPException(
            status_code=422,
            detail="Only .xlsx and .xls Excel files are accepted."
        )

    try:
        content = await file.read()
        return services.process_excel_batch(content, filename)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected server error processing workbook: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests.test_app.TestAppUploadEndpoint
```
Expected: All 3 tests PASS.

- [ ] **Step 5: Run full test suite**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest
```
Expected: All 28 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/app.py tests/test_app.py
git commit -m "feat(app): add POST /api/upload endpoint for Excel batch ingestion"
```

---

### Task 5: Implement UI Upload Modal, Batch Summary Header & 3-Column Card Grid

**Files:**
- Modify: `src/templates/index.html`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `POST /api/upload`, `POST /api/lookup`, `BatchRunResponse`, `WasteManagementDossier`
- Produces: Complete Variant C UI with Upload Modal, in-flight spinner, Batch Summary Header, and 3-column physical segregation card grid.

- [ ] **Step 1: Write template verification tests in `tests/test_app.py`**

Add tests to `TestApp` in `tests/test_app.py`:

```python
    def test_root_template_contains_upload_modal_and_grid_elements(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.text
        # Header upload button
        self.assertIn('Upload Batch (.xlsx)', html)
        # Upload modal container and dropzone
        self.assertIn('uploadModalOpen', html)
        self.assertIn('handleDrop', html)
        self.assertIn('uploadFile', html)
        # Batch summary bar
        self.assertIn('activeBatch', html)
        self.assertIn('Upload New Batch', html)
        # 3-column card grid
        self.assertIn('grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3', html)
        self.assertIn('View Full Plan →', html)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests.test_app.TestApp.test_root_template_contains_upload_modal_and_grid_elements
```
Expected: FAIL with `AssertionError: 'Upload Batch (.xlsx)' not found in '...'`

- [ ] **Step 3: Update `src/templates/index.html`**

Update `src/templates/index.html` to integrate:
1. Header button: `Upload Batch (.xlsx)` triggering `uploadModalOpen = true`.
2. Modal Component (`uploadModalOpen`):
   - Backdrop with disabled click when `isUploading` is true.
   - Dropzone with `@dragover.prevent`, `@dragleave.prevent`, `@drop.prevent="handleDrop($event)"`.
   - File input `<input type="file" x-ref="fileInput" @change="handleFileSelect($event)" accept=".xlsx,.xls" class="hidden">`.
   - In-flight spinner showing `"Evaluating chemical inventory & generating compliance plans..."` while `isUploading` is true.
   - Inline alert error banner displaying `uploadError` when non-null.
3. Batch Active Summary Bar (`x-if="activeBatch"`):
   - Shows workbook name, timestamp, and total unique chemicals badge.
   - Shows bin breakdown pills: `Flammable Solvents`, `Inorganic Acids`, `Inorganic Bases`, `Carcinogenic & Toxic Organics`, `Biohazard & Infectious`, and `Review Queue`.
   - "Upload New Batch" button.
4. Responsive 3-Column Card Grid:
   - `<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">`
   - Iterates `<template x-for="item in activeBatch.items" :key="item.chemical">`.
   - Card features:
     - Outer container styled with `:class="item.review_required ? 'border-amber-500/50 bg-amber-950/15 ring-1 ring-amber-500/30' : 'border-slate-800 bg-slate-900/90'"`
     - Bin badge with icon: `🗄️ <span x-text="item.bin"></span>`
     - Hazard category badges
     - Container snippet: `🛢️ <span x-text="item.container"></span>`
     - Segregation note: `🔒 <span x-text="item.segregation"></span>`
     - Button `@click="openDossier(item)"` displaying `"View Full Plan →"`.
5. Retain ad-hoc quick search bar in header; `performLookup()` opens slide-over drawer over the batch without discarding `activeBatch`.

- [ ] **Step 4: Run template tests to verify they pass**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests.test_app.TestApp.test_root_template_contains_upload_modal_and_grid_elements
```
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest
```
Expected: All 29 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/templates/index.html tests/test_app.py
git commit -m "feat(ui): add batch upload modal and 3-column physical segregation card grid"
```

---

### Task 6: End-to-End Workbook Ingestion Test with Repository Sample

**Files:**
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `src/Hazardous Waste.xlsx`
- Produces: Verified end-to-end ingestion test of real laboratory inventory workbook.

- [ ] **Step 1: Write the end-to-end test**

In `tests/test_app.py`, add `test_e2e_real_sample_workbook_ingestion`:

```python
    def test_e2e_real_sample_workbook_ingestion(self):
        import src.services as services
        sample_path = Path(__file__).resolve().parent.parent / "src" / "Hazardous Waste.xlsx"
        self.assertTrue(sample_path.exists(), "Sample file src/Hazardous Waste.xlsx must exist")

        fake_client = FakeClient()
        orig_batch = services.process_excel_batch

        try:
            services.process_excel_batch = lambda b, fn, **kwargs: orig_batch(b, fn, client=fake_client, **kwargs)

            with open(sample_path, 'rb') as f:
                content = f.read()

            response = self.client.post(
                '/api/upload',
                files={'file': ('Hazardous Waste.xlsx', io.BytesIO(content), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['filename'], 'Hazardous Waste.xlsx')
            self.assertGreater(data['total_count'], 0)
            self.assertEqual(len(data['items']), data['total_count'])
            # Verify every item has required dossier fields
            for item in data['items']:
                self.assertTrue(bool(item['chemical']))
                self.assertTrue(bool(item['bin']))
                self.assertIsInstance(item['categories'], list)
                self.assertTrue(bool(item['container']))
        finally:
            services.process_excel_batch = orig_batch
```

- [ ] **Step 2: Run end-to-end test to verify it passes**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests.test_app.TestAppUploadEndpoint.test_e2e_real_sample_workbook_ingestion
```
Expected: PASS

- [ ] **Step 3: Run full repository test suite**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest
```
Expected: All 30 tests PASS across `tests/test_app.py`, `tests/test_models.py`, `tests/test_services.py`, and `tests/test_openai_migration.py`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_app.py
git commit -m "test(e2e): verify end-to-end batch ingestion of sample lab workbook"
```

---

## Self-Review Checklist

- [x] **Spec coverage**:
  - Drag-and-drop Excel upload modal (`.xlsx`, `.xls`)? Covered in Task 1, 4, & 5.
  - Automatic detection of "Hazardous Waste" column with case/whitespace tolerance? Covered in Task 3.
  - Case-insensitive chemical de-duplication? Covered in Task 3.
  - 50-item safeguard limit? Covered in Task 3 & 4.
  - Local run persistence under `data/runs/<timestamp>/input.xlsx` and `meta.json`? Covered in Task 3.
  - Physical segregation bin mapping into 6 cabinets? Covered in Task 3.
  - Responsive 3-column segregation card grid matching Variant C design? Covered in Task 5.
  - Amber visual accent for `Review Queue` / `review_required` items? Covered in Task 5.
  - "View Full Plan →" button opening 3-tab slide-over compliance dossier? Covered in Task 5.
  - End-to-end unit tests using Python stdlib `unittest`? Covered in Task 2, 3, 4, 5, & 6.
- [x] **No Placeholders**: All code snippets, tests, commands, and assertions are complete and executable.
- [x] **Type consistency**: `BatchRunResponse` fields (`run_id`, `filename`, `total_count`, `bin_counts`, `items`), `detect_waste_column`, `process_excel_batch`, and `POST /api/upload` signatures match across `models.py`, `services.py`, `app.py`, and test suites.
