# Ticket 05: Review Queue, Inline Name Editing & Single-Item Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement single-item chemical retry and inline renaming with collision protection, error reason display, in-place dossier updating, and dynamic graduation from the Review Queue into physical containment cabinets.

**Architecture:** Add `POST /api/runs/{run_id}/retry` consuming `RetryItemRequest` (`original_name`, `new_name`) and backed by `remediate_batch_item` in `src/services.py`. The service validates against duplicate name collisions, evaluates the chemical via `lookup_chemical`, updates `data/runs/<run_id>/meta.json` (dossiers, classifications, chemicals, bin_counts, and `remediated_from` audit log), and returns `RetryItemResponse`. The frontend provides dual remediation surfaces (on the card and in the slide-over drawer header) with inline editing, failure reason display, 1-click quick retry, and instant reactive graduation across both Card Grid and Cabinet Swimlanes views.

**Tech Stack:** FastAPI, Pydantic, Alpine.js (CDN), Tailwind CSS (CDN), Python standard library `unittest`.

**Spec:** [.scratch/frontend/spec.md](file:///C:/Users/stars/AI-ML/D2S-MTP/.scratch/frontend/spec.md) and [.scratch/frontend/issues/05-review-queue-inline-editing-and-retry.md](file:///C:/Users/stars/AI-ML/D2S-MTP/.scratch/frontend/issues/05-review-queue-inline-editing-and-retry.md)

## Global Constraints

- **Python Runtime**: Strictly target dedicated Conda environment `C:\Users\stars\miniconda3\envs\d2s-mtp` (`python.exe`). Zero packages in base.
- **Frontend Stack**: Server-rendered HTML with Tailwind CSS CDN and Alpine.js CDN. No Node.js build chain; zero npm packages.
- **Testing Standard**: Python standard library `unittest` ONLY (`unittest.TestCase`). Do NOT use `pytest`. Run tests via `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest`.
- **Git Config**: Author Aryan Das <starsnipe407@gmail.com>. Windows PowerShell syntax (use `;` instead of `&&`).
- **Domain Language**: Adhere strictly to [CONTEXT.md](file:///C:/Users/stars/AI-ML/D2S-MTP/CONTEXT.md) terms: `Batch Run`, `Review Queue`, `Classification Review`, `Containment Zone`, `Item Remediation`, `Segregation Bin`, `Waste Management Plan`.

---

## File Structure

- `src/models.py`: Adds `RetryItemRequest` and `RetryItemResponse`.
- `src/services.py`: Implements `remediate_batch_item(run_id, original_name, new_name, runs_dir, client)`.
- `src/app.py`: Adds `POST /api/runs/{run_id}/retry` endpoint.
- `src/templates/index.html`: Adds inline chemical editing, failure reason banner, 1-click retry button, drawer remediation controls, and graduation reactivity.
- `tests/test_models.py`: Unit tests for retry models.
- `tests/test_services.py`: Unit tests for `remediate_batch_item` (successful remediation, collision guard, empty name, still requiring review, audit metadata).
- `tests/test_app.py`: Unit tests for `POST /api/runs/{run_id}/retry` endpoint, template hooks, and end-to-end remediation test.

---

### Task 1: Define Retry Models & Implement `remediate_batch_item` Service

**Files:**
- Modify: `src/models.py`
- Modify: `src/services.py`
- Modify: `tests/test_models.py`
- Modify: `tests/test_services.py`

**Interfaces:**
- Consumes: `lookup_chemical`, `WasteManagementDossier`, `DEFAULT_RUNS_DIR`
- Produces:
  - `RetryItemRequest(original_name=str, new_name=str)`
  - `RetryItemResponse(status=str, chemical=str, original_name=str, dossier=WasteManagementDossier, bin_counts=dict[str, int])`
  - `remediate_batch_item(run_id: str, original_name: str, new_name: str, runs_dir: Path | None = None, client=None) -> tuple[WasteManagementDossier, dict[str, int]]`

- [ ] **Step 1: Write failing unit tests in `tests/test_models.py` and `tests/test_services.py`**

In `tests/test_models.py`:
```python
    def test_retry_models_schema(self):
        from src.models import RetryItemRequest, RetryItemResponse, WasteManagementDossier

        req = RetryItemRequest(original_name="Mystery Acid", new_name="Hydrochloric Acid")
        self.assertEqual(req.original_name, "Mystery Acid")
        self.assertEqual(req.new_name, "Hydrochloric Acid")

        dossier = WasteManagementDossier(
            chemical="Hydrochloric Acid",
            flammable=False,
            carcinogenic=False,
            infectious=False,
            toxic=False,
            corrosive=True,
            segregation_bin="Inorganic Acids",
            identification="HCl",
            segregation="Keep away from bases",
            container="Polyethylene drum",
            labeling="CORROSIVE",
            storage="Acid cabinet",
            ppe="Gloves, goggles",
            spill="Neutralize with sodium bicarbonate",
            treatment="Neutralization",
            disposal="TSDF inorganic acid stream",
            usepa="D002",
            india="Schedule II",
            prohibited="Do not pour into sink",
            verification="Verify pH",
            review_required=False,
            review_reason=None
        )
        resp = RetryItemResponse(
            status="success",
            chemical="Hydrochloric Acid",
            original_name="Mystery Acid",
            dossier=dossier,
            bin_counts={"Inorganic Acids": 1, "Review Queue": 0}
        )
        self.assertEqual(resp.status, "success")
        self.assertEqual(resp.dossier.chemical, "Hydrochloric Acid")
```

In `tests/test_services.py`:
```python
    def test_remediate_batch_item_success(self):
        fake_client = FakeClient()
        classification = HazardClassification(
            flammable=True, carcinogenic=False, infectious=False, toxic=False, corrosive=False
        )
        plan = ManagementPlan(
            chemical='Acetone',
            identification_and_characterization='Ketone solvent',
            segregation_and_incompatibilities='Keep away from oxidizers',
            recommended_container='Safety can',
            labeling_requirements='FLAMMABLE',
            storage_requirements='Flammables cabinet',
            handling_and_ppe='Nitrile gloves',
            spill_and_emergency_management='Absorb with vermiculite',
            treatment_framework='Thermal oxidation',
            final_disposal_framework='Incineration at TSDF',
            usepa_framework='D001',
            indian_framework='HOWM Schedule II',
            prohibited_or_unsafe_actions='No drain disposal',
            verification_required='Verify flash point',
        )
        def side_effect(**kwargs):
            if kwargs['text_format'] is HazardClassification:
                return types.SimpleNamespace(output_parsed=classification)
            return types.SimpleNamespace(output_parsed=plan)
        fake_client.responses.parse = side_effect

        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            run_id = "test_remediation_run"
            run_folder = runs_path / run_id
            run_folder.mkdir(parents=True, exist_ok=True)

            # Write initial meta.json with Mystery Liquid in Review Queue
            initial_meta = {
                "run_id": run_id,
                "filename": "test.xlsx",
                "chemicals": ["Mystery Liquid", "Toluene"],
                "status": "completed",
                "bin_counts": {
                    "Flammable Solvents": 1,
                    "Inorganic Acids": 0,
                    "Inorganic Bases": 0,
                    "Carcinogenic & Toxic Organics": 0,
                    "Biohazard & Infectious": 0,
                    "Review Queue": 1,
                },
                "classifications": {
                    "Mystery Liquid": {"classification": {}, "bin": "Review Queue"},
                    "Toluene": {"classification": {"flammable": True}, "bin": "Flammable Solvents"}
                },
                "dossiers": {
                    "Mystery Liquid": {
                        "chemical": "Mystery Liquid",
                        "flammable": False,
                        "carcinogenic": False,
                        "infectious": False,
                        "toxic": False,
                        "corrosive": False,
                        "segregation_bin": "Review Queue",
                        "identification": "",
                        "segregation": "",
                        "container": "",
                        "labeling": "",
                        "storage": "",
                        "ppe": "",
                        "spill": "",
                        "treatment": "",
                        "disposal": "",
                        "usepa": "",
                        "india": "",
                        "prohibited": "",
                        "verification": "",
                        "review_required": True,
                        "review_reason": "API timeout"
                    },
                    "Toluene": {
                        "chemical": "Toluene",
                        "flammable": True,
                        "carcinogenic": False,
                        "infectious": False,
                        "toxic": False,
                        "corrosive": False,
                        "segregation_bin": "Flammable Solvents",
                        "identification": "",
                        "segregation": "",
                        "container": "",
                        "labeling": "",
                        "storage": "",
                        "ppe": "",
                        "spill": "",
                        "treatment": "",
                        "disposal": "",
                        "usepa": "",
                        "india": "",
                        "prohibited": "",
                        "verification": "",
                        "review_required": False,
                        "review_reason": None
                    }
                },
                "remediated_from": {}
            }
            with open(run_folder / "meta.json", "w", encoding="utf-8") as f:
                json.dump(initial_meta, f, indent=2)

            # Remediate Mystery Liquid -> Acetone
            dossier, bin_counts = remediate_batch_item(
                run_id=run_id,
                original_name="Mystery Liquid",
                new_name="Acetone",
                runs_dir=runs_path,
                client=fake_client
            )

            # Assertions
            self.assertEqual(dossier.chemical, "Acetone")
            self.assertFalse(dossier.review_required)
            self.assertEqual(dossier.segregation_bin, "Flammable Solvents")
            self.assertEqual(bin_counts["Review Queue"], 0)
            self.assertEqual(bin_counts["Flammable Solvents"], 2)

            # Assert meta.json updated
            with open(run_folder / "meta.json", "r", encoding="utf-8") as f:
                meta = json.load(f)
            self.assertIn("Acetone", meta["chemicals"])
            self.assertNotIn("Mystery Liquid", meta["chemicals"])
            self.assertEqual(meta["remediated_from"]["Acetone"], "Mystery Liquid")

    def test_remediate_batch_item_collision_guard(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runs_path = Path(tmp_dir)
            run_id = "collision_run"
            run_folder = runs_path / run_id
            run_folder.mkdir(parents=True, exist_ok=True)

            meta = {
                "run_id": run_id,
                "chemicals": ["Mystery Liquid", "Acetone"],
                "dossiers": {"Mystery Liquid": {}, "Acetone": {}},
                "bin_counts": {}
            }
            with open(run_folder / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f)

            with self.assertRaises(ValueError) as ctx:
                remediate_batch_item(
                    run_id=run_id,
                    original_name="Mystery Liquid",
                    new_name="Acetone",
                    runs_dir=runs_path
                )
            self.assertIn("already present in this batch", str(ctx.exception))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_models.py tests/test_services.py`
Expected: FAIL with `ImportError: cannot import name 'RetryItemRequest'` and `NameError: name 'remediate_batch_item' is not defined`

- [ ] **Step 3: Implement models in `src/models.py`**

Add to `src/models.py`:
```python
class RetryItemRequest(BaseModel):
    original_name: str
    new_name: str


class RetryItemResponse(BaseModel):
    status: str = "success"
    chemical: str
    original_name: str
    dossier: WasteManagementDossier
    bin_counts: dict[str, int]
```

- [ ] **Step 4: Implement `remediate_batch_item` in `src/services.py`**

Add to `src/services.py`:
```python
def remediate_batch_item(
    run_id: str,
    original_name: str,
    new_name: str,
    runs_dir: Path | None = None,
    client=None
) -> tuple[WasteManagementDossier, dict[str, int]]:
    target_runs_dir = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR
    run_dir = target_runs_dir / run_id
    meta_path = run_dir / "meta.json"

    if not meta_path.exists():
        raise FileNotFoundError(f"Run '{run_id}' not found.")

    clean_new_name = normalize_chemical_name(new_name)
    if not clean_new_name:
        raise ValueError("Chemical name cannot be empty.")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    chemicals: list[str] = meta.get("chemicals", [])
    orig_clean = normalize_chemical_name(original_name)

    # Find original chemical index (case-insensitive)
    found_idx = -1
    matched_orig_name = None
    for idx, c in enumerate(chemicals):
        if c.strip().lower() == orig_clean.lower():
            found_idx = idx
            matched_orig_name = c
            break

    if found_idx == -1:
        raise ValueError(f"Chemical '{original_name}' not found in run '{run_id}'.")

    # Collision guard: check if new_name already exists in other entries
    for idx, c in enumerate(chemicals):
        if idx != found_idx and c.strip().lower() == clean_new_name.lower():
            raise ValueError(
                f"A chemical named '{clean_new_name}' is already present in this batch. Please specify a distinguishing formulation (e.g., '{clean_new_name} 50%' or '{clean_new_name}/Water Mix')."
            )

    # Re-evaluate chemical
    dossier = lookup_chemical(clean_new_name, client=client)

    # Update metadata
    chemicals[found_idx] = clean_new_name
    meta["chemicals"] = chemicals

    dossiers = meta.get("dossiers", {})
    if matched_orig_name in dossiers and matched_orig_name != clean_new_name:
        del dossiers[matched_orig_name]
    dossiers[clean_new_name] = dossier.model_dump()
    meta["dossiers"] = dossiers

    classifications = meta.get("classifications", {})
    if matched_orig_name in classifications and matched_orig_name != clean_new_name:
        del classifications[matched_orig_name]
    classifications[clean_new_name] = {
        "classification": {
            "flammable": dossier.flammable,
            "carcinogenic": dossier.carcinogenic,
            "infectious": dossier.infectious,
            "toxic": dossier.toxic,
            "corrosive": dossier.corrosive
        },
        "bin": dossier.segregation_bin
    }
    meta["classifications"] = classifications

    # Recalculate bin counts
    recalculated_counts = {
        "Flammable Solvents": 0,
        "Inorganic Acids": 0,
        "Inorganic Bases": 0,
        "Carcinogenic & Toxic Organics": 0,
        "Biohazard & Infectious": 0,
        "Review Queue": 0,
    }
    for item in dossiers.values():
        bin_name = item.get("segregation_bin")
        if item.get("review_required") or bin_name == "Review Queue":
            recalculated_counts["Review Queue"] = recalculated_counts.get("Review Queue", 0) + 1
        elif bin_name in recalculated_counts:
            recalculated_counts[bin_name] += 1
        else:
            recalculated_counts["Review Queue"] = recalculated_counts.get("Review Queue", 0) + 1

    meta["bin_counts"] = recalculated_counts

    remediated_from = meta.get("remediated_from", {})
    remediated_from[clean_new_name] = matched_orig_name
    meta["remediated_from"] = remediated_from

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return dossier, recalculated_counts
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_models.py tests/test_services.py`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/models.py src/services.py tests/test_models.py tests/test_services.py
git commit -m "feat(services): implement remediate_batch_item and define retry models"
```

---

### Task 2: Implement POST /api/runs/{run_id}/retry Endpoint

**Files:**
- Modify: `src/app.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `RetryItemRequest`, `RetryItemResponse`, `remediate_batch_item`
- Produces: `POST /api/runs/{run_id}/retry` HTTP endpoint

- [ ] **Step 1: Write failing unit tests in `tests/test_app.py`**

Add unit tests in `tests/test_app.py`:
- `test_retry_endpoint_success_and_bin_recalculation`
- `test_retry_endpoint_duplicate_collision_returns_422`
- `test_retry_endpoint_empty_name_returns_422`
- `test_retry_endpoint_unknown_run_returns_404`

```python
    def test_retry_endpoint_success_and_bin_recalculation(self):
        # 1. Upload a batch with 1 item
        excel_bytes = self._create_test_excel(['Mystery Chemical'])
        upload_resp = self.client.post(
            "/api/upload",
            files={"file": ("inventory.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"pause_after_classification": "false"}
        )
        run_id = upload_resp.json()["run_id"]

        # Run stream to completion so dossiers are saved
        self.client.get(f"/api/runs/{run_id}/stream")

        # 2. Call POST /api/runs/{run_id}/retry
        retry_resp = self.client.post(
            f"/api/runs/{run_id}/retry",
            json={"original_name": "Mystery Chemical", "new_name": "Acetone"}
        )
        self.assertEqual(retry_resp.status_code, 200)
        data = retry_resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["chemical"], "Acetone")
        self.assertEqual(data["original_name"], "Mystery Chemical")
        self.assertIn("dossier", data)
        self.assertIn("bin_counts", data)

    def test_retry_endpoint_duplicate_collision_returns_422(self):
        excel_bytes = self._create_test_excel(['Acetone', 'Mystery Chemical'])
        upload_resp = self.client.post(
            "/api/upload",
            files={"file": ("inventory.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        run_id = upload_resp.json()["run_id"]
        self.client.get(f"/api/runs/{run_id}/stream")

        retry_resp = self.client.post(
            f"/api/runs/{run_id}/retry",
            json={"original_name": "Mystery Chemical", "new_name": "Acetone"}
        )
        self.assertEqual(retry_resp.status_code, 422)
        self.assertIn("already present in this batch", retry_resp.json()["detail"])

    def test_retry_endpoint_empty_name_returns_422(self):
        retry_resp = self.client.post(
            "/api/runs/any_run_id/retry",
            json={"original_name": "Acetone", "new_name": "   "}
        )
        self.assertEqual(retry_resp.status_code, 422)

    def test_retry_endpoint_unknown_run_returns_404(self):
        retry_resp = self.client.post(
            "/api/runs/nonexistent_run_99999/retry",
            json={"original_name": "Acetone", "new_name": "Methanol"}
        )
        self.assertEqual(retry_resp.status_code, 404)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: FAIL with HTTP 404 / route not defined

- [ ] **Step 3: Implement endpoint in `src/app.py`**

Add import and endpoint to `src/app.py`:
```python
from src.models import (
    BatchQueuedResponse,
    BatchRunResponse,
    RetryItemRequest,
    RetryItemResponse,
    WasteManagementDossier,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/app.py tests/test_app.py
git commit -m "feat(app): add POST /api/runs/{run_id}/retry endpoint"
```

---

### Task 3: Implement Inline Editing, Quick Retry, and Drawer Remediation UI

**Files:**
- Modify: `src/templates/index.html`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `POST /api/runs/{run_id}/retry`, `activeBatch`
- Produces:
  - Inline edit mode on chemical cards (`editingChemical`, `editNameInput`, `startEditing`, `cancelEditing`)
  - 1-click retry button (`retryChemical`)
  - Failure explanation box with failure reason (`Reason: ...`)
  - Drawer-level remediation header
  - Dynamic graduation from Review Queue into physical containment cabinets

- [ ] **Step 1: Write failing template unit test in `tests/test_app.py`**

Add `test_template_contains_inline_editing_and_retry_controls`:
```python
    def test_template_contains_inline_editing_and_retry_controls(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.text

        # Review card inline edit and retry bindings
        self.assertIn("startEditing", html)
        self.assertIn("cancelEditing", html)
        self.assertIn("retryChemical", html)
        self.assertIn("editingChemical", html)
        self.assertIn("editNameInput", html)
        self.assertIn("retryingChemical", html)
        self.assertIn("retryError", html)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: FAIL with `AssertionError: 'startEditing' not found in response HTML`

- [ ] **Step 3: Update `src/templates/index.html`**

1. In `x-data`, add reactive state and methods:
```javascript
editingChemical: null,
editNameInput: '',
retryingChemical: null,
retryError: null,

startEditing(item) {
  this.editingChemical = item.chemical;
  this.editNameInput = item.chemical;
  this.retryError = null;
},

cancelEditing() {
  this.editingChemical = null;
  this.editNameInput = '';
  this.retryError = null;
},

async retryChemical(originalName, customNewName = null) {
  const newName = customNewName !== null ? customNewName.trim() : originalName.trim();
  if (!newName) {
    this.retryError = 'Chemical name cannot be empty.';
    return;
  }
  if (!this.activeBatch || !this.activeBatch.run_id) {
    this.retryError = 'No active batch run.';
    return;
  }

  this.retryingChemical = originalName;
  this.retryError = null;

  try {
    const res = await fetch(`/api/runs/${this.activeBatch.run_id}/retry`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ original_name: originalName, new_name: newName })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Failed to retry chemical.');
    }

    // Update item in activeBatch.items
    const idx = this.activeBatch.items.findIndex(i => i.chemical.toLowerCase() === originalName.toLowerCase());
    if (idx >= 0) {
      this.activeBatch.items[idx] = data.dossier;
    }
    // Update bin counts
    if (data.bin_counts) {
      this.activeBatch.bin_counts = data.bin_counts;
    }
    // Update activeDossier if open in drawer
    if (this.activeDossier && this.activeDossier.chemical.toLowerCase() === originalName.toLowerCase()) {
      this.activeDossier = data.dossier;
    }

    this.editingChemical = null;
    this.editNameInput = '';
  } catch (err) {
    this.retryError = err.message;
  } finally {
    this.retryingChemical = null;
  }
},
```

2. In the Chemical Card template (both in Card Grid and in Cabinet Swimlanes), update the card header and failure explanation:
```html
<!-- Card Header with Inline Edit and Quick Retry -->
<div class="flex items-start justify-between gap-2">
  <!-- Normal Display Mode -->
  <template x-if="editingChemical !== item.chemical">
    <div class="flex items-center gap-2 flex-1 min-w-0">
      <h3 class="text-base font-bold text-white tracking-tight truncate" x-text="item.chemical"></h3>
      <template x-if="item.review_required">
        <button @click="startEditing(item)" title="Edit chemical name" class="p-1 rounded text-slate-400 hover:text-amber-300 hover:bg-slate-800 transition text-xs shrink-0">
          ✏️
        </button>
      </template>
    </div>
  </template>

  <!-- Inline Edit Mode -->
  <template x-if="editingChemical === item.chemical">
    <div class="flex-1 space-y-2">
      <input type="text"
             x-model="editNameInput"
             @keydown.enter="retryChemical(item.chemical, editNameInput)"
             @keydown.escape="cancelEditing()"
             class="w-full px-2.5 py-1.5 rounded-lg bg-slate-950 border border-amber-500/80 text-xs text-white focus:outline-none focus:ring-1 focus:ring-amber-400 font-medium">
      <div class="flex items-center gap-2">
        <button @click="retryChemical(item.chemical, editNameInput)"
                :disabled="retryingChemical === item.chemical"
                class="px-2.5 py-1 rounded-md bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-semibold shadow transition disabled:opacity-50">
          Save &amp; Retry
        </button>
        <button @click="cancelEditing()"
                class="px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition">
          Cancel
        </button>
      </div>
    </div>
  </template>

  <template x-if="item.review_required && editingChemical !== item.chemical">
    <div class="flex items-center gap-1.5 shrink-0">
      <button @click="retryChemical(item.chemical)"
              :disabled="retryingChemical === item.chemical"
              title="Retry evaluation"
              class="px-2 py-0.5 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-[10px] font-mono font-medium transition flex items-center gap-1 disabled:opacity-50">
        <span :class="retryingChemical === item.chemical ? 'animate-spin' : ''">🔄</span>
        <span>Retry</span>
      </button>
      <span class="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 whitespace-nowrap">
        Review Required
      </span>
    </div>
  </template>
</div>

<!-- Failure Explanation Box (for Review Required items) -->
<template x-if="item.review_required">
  <div class="p-2.5 rounded-lg bg-amber-950/40 border border-amber-500/40 text-xs text-amber-300/90 space-y-1">
    <div class="font-semibold text-[11px] uppercase tracking-wider text-amber-400 flex items-center gap-1">
      <span>⚠️ Evaluation Review Reason:</span>
    </div>
    <p class="text-[11px] leading-relaxed text-amber-200/80" x-text="item.review_reason || 'Requires human verification before disposal authorization.'"></p>
    <template x-if="retryError && retryingChemical === item.chemical">
      <p class="text-[11px] font-medium text-red-400 pt-1" x-text="retryError"></p>
    </template>
  </div>
</template>
```

3. Update the Slide-Over Drawer Header (`x-show="showDrawer"`):
Add remediation toggle directly in the drawer banner when `activeDossier && activeDossier.review_required`:
```html
<template x-if="activeDossier && activeDossier.review_required">
  <div class="p-3 rounded-lg bg-amber-950/40 border border-amber-500/40 flex items-center justify-between gap-3 text-xs">
    <div>
      <span class="font-semibold text-amber-300 block">⚠️ Quarantined in Review Queue</span>
      <span class="text-amber-200/80 text-[11px]" x-text="activeDossier.review_reason || 'Requires manual characterization.'"></span>
    </div>
    <button @click="retryChemical(activeDossier.chemical)"
            :disabled="retryingChemical === activeDossier.chemical"
            class="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-semibold shadow transition shrink-0 flex items-center gap-1 disabled:opacity-50">
      <span :class="retryingChemical === activeDossier.chemical ? 'animate-spin' : ''">🔄</span>
      <span>Retry Chemical</span>
    </button>
  </div>
</template>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/templates/index.html tests/test_app.py
git commit -m "feat(ui): add inline editing, quick retry, and drawer remediation controls"
```

---

### Task 4: End-to-End Workbook Remediation & Physical Cabinet Graduation Test

**Files:**
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `POST /api/upload`, `POST /api/runs/{run_id}/retry`, `src/Hazardous Waste.xlsx`
- Produces: Complete end-to-end integration test verifying full remediation and cabinet graduation lifecycle.

- [ ] **Step 1: Write the end-to-end integration test in `tests/test_app.py`**

Add `test_e2e_remediation_and_cabinet_graduation` in `tests/test_app.py`:
```python
    def test_e2e_remediation_and_cabinet_graduation(self):
        # 1. Create a workbook with an unknown ambiguous chemical
        excel_bytes = self._create_test_excel(['Mystery Chemical Mix', 'Methanol'])
        upload_resp = self.client.post(
            "/api/upload",
            files={"file": ("inventory.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        self.assertEqual(upload_resp.status_code, 200)
        run_id = upload_resp.json()["run_id"]

        # 2. Stream to completion
        stream_resp = self.client.get(f"/api/runs/{run_id}/stream")
        self.assertEqual(stream_resp.status_code, 200)

        # 3. Verify Mystery Chemical Mix is initially in Review Queue
        meta_path = Path("data/runs") / run_id / "meta.json"
        with open(meta_path, "r", encoding="utf-8") as f:
            meta_before = json.load(f)
        self.assertIn("Mystery Chemical Mix", meta_before["dossiers"])
        self.assertTrue(meta_before["dossiers"]["Mystery Chemical Mix"]["review_required"])
        self.assertEqual(meta_before["dossiers"]["Mystery Chemical Mix"]["segregation_bin"], "Review Queue")
        initial_review_count = meta_before["bin_counts"]["Review Queue"]

        # 4. Remediate 'Mystery Chemical Mix' -> 'Hydrochloric Acid'
        retry_resp = self.client.post(
            f"/api/runs/{run_id}/retry",
            json={"original_name": "Mystery Chemical Mix", "new_name": "Hydrochloric Acid"}
        )
        self.assertEqual(retry_resp.status_code, 200)
        result = retry_resp.json()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["chemical"], "Hydrochloric Acid")
        self.assertFalse(result["dossier"]["review_required"])
        self.assertEqual(result["dossier"]["segregation_bin"], "Inorganic Acids")

        # 5. Verify graduation in metadata
        with open(meta_path, "r", encoding="utf-8") as f:
            meta_after = json.load(f)
        self.assertIn("Hydrochloric Acid", meta_after["chemicals"])
        self.assertNotIn("Mystery Chemical Mix", meta_after["chemicals"])
        self.assertEqual(meta_after["bin_counts"]["Review Queue"], initial_review_count - 1)
        self.assertEqual(meta_after["bin_counts"]["Inorganic Acids"], 1)
        self.assertEqual(meta_after["remediated_from"]["Hydrochloric Acid"], "Mystery Chemical Mix")
```

- [ ] **Step 2: Run the test to verify PASS**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests.test_app.TestAppRoutes.test_e2e_remediation_and_cabinet_graduation -v`
Expected: PASS

- [ ] **Step 3: Run full test suite across the repository**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest`
Expected: PASS (all 48+ tests pass cleanly)

- [ ] **Step 4: Commit**

```bash
git add tests/test_app.py
git commit -m "test(e2e): verify item remediation and physical cabinet graduation lifecycle"
```

---

## Self-Review Checklist

1. **Spec Coverage**:
   - Failed chemicals captured and marked with `review_required = True`? Yes (Task 1 & Task 4).
   - Problematic items appear under "Review Required" filter pill and Review Queue bin? Yes (Task 1 & Task 3).
   - Cards highlight specific failure reason and provide inline edit field to rename chemical? Yes (Task 3).
   - 1-click Retry button re-runs single item without re-processing other completed chemicals? Yes (Task 1, 2, 3).
   - Successfully retrying removes review flag, updates hazard badges, and moves to appropriate physical containment bin? Yes (Task 1, 3, 4).
   - Unit tests verify error capture, inline rename payload handling, and single-item retry resolution? Yes (Task 1, 2, 4).
2. **No Placeholders**: All tasks contain explicit code blocks and runnable commands with exact assertions.
3. **Type Consistency**: `RetryItemRequest`, `RetryItemResponse`, `remediate_batch_item`, and Alpine handlers match exactly.
4. **Environment Constraints**: Standard library `unittest` used exclusively; Conda env `d2s-mtp` targeted in all run commands.
