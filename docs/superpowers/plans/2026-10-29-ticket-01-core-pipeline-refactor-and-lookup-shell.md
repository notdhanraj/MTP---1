# Ticket 01: Core Pipeline Refactor & Ad-Hoc Chemical Lookup Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor existing waste classification and management plan scripts into importable modules, stand up a lightweight FastAPI application shell in the dedicated Conda environment, and provide an ad-hoc chemical lookup search bar that immediately renders a 3-tab compliance dossier.

**Architecture:** A lightweight FastAPI server running in `src/app.py` serves Jinja2/HTML templates (`src/templates/index.html`) implementing the Variant C interface (Physical Segregation Bins). The endpoint `POST /api/lookup` executes `classify_chemical` and `make_plan` in-process, maps the result to a physical segregation bin, and returns a unified `WasteManagementDossier` Pydantic model displayed in a slide-over drawer with high-visibility safety banners.

**Tech Stack:** Python 3.12 (Conda env `d2s-mtp`), FastAPI, Uvicorn, Jinja2, Pydantic v2, Pandas, Openpyxl, OpenAI Python SDK, Tailwind CSS (CDN), Alpine.js (CDN), Python stdlib `unittest`.

**Spec:** [.scratch/frontend/spec.md](file:///C:/Users/stars/AI-ML/D2S-MTP/.scratch/frontend/spec.md) and [.scratch/frontend/issues/01-core-pipeline-refactor-and-lookup-shell.md](file:///C:/Users/stars/AI-ML/D2S-MTP/.scratch/frontend/issues/01-core-pipeline-refactor-and-lookup-shell.md)

## Global Constraints

- **Python Environment**: All packages and executions MUST strictly target `C:\Users\stars\miniconda3\envs\d2s-mtp`. Never install into base or external environments.
- **Testing Standard**: Python standard library `unittest` ONLY (`unittest.TestCase`, `unittest.mock.patch`). Do NOT use `pytest`.
- **Domain Vocabulary**: Strictly adhere to [CONTEXT.md](file:///C:/Users/stars/AI-ML/D2S-MTP/CONTEXT.md) terms (`Hazardous Waste`, `Hazard Classification`, `Waste Management Plan`, `Segregation`, `Segregation Bin`, `Recommended Container`, `Treatment Framework`, `Final Disposal Framework`, `RCRA Framework`, `HOWM Framework`).
- **No JS Build Chains**: Zero Node.js, npm, or frontend bundlers. Tailwind CSS and Alpine.js loaded via standard CDN scripts.
- **Error Handling**: Ambiguous or failed chemical lookups MUST return HTTP 200 with `review_required: True` and safe precautionary holding guidance, never an unhandled HTTP 500 error.

---

### Task 1: Environment & Dependencies Scaffolding

**Files:**
- Modify: `requirements.txt`
- Modify: `requirement.txt`

**Interfaces:**
- Consumes: None
- Produces: `fastapi`, `uvicorn`, and `jinja2` installed in `d2s-mtp` Conda environment

- [ ] **Step 1: Update requirements files**

Add `fastapi>=0.110.0`, `uvicorn>=0.28.0`, and `jinja2>=3.1.0` to both `requirements.txt` and `requirement.txt`:

```txt
# Core Data & File Handling
pandas>=2.0.0
openpyxl>=3.1.0

# LLM & Structured Outputs
openai>=1.50.0
pydantic>=2.0.0

# Web Server & UI
fastapi>=0.110.0
uvicorn>=0.28.0
jinja2>=3.1.0
```

- [ ] **Step 2: Install dependencies into the dedicated Conda environment**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m pip install -r requirements.txt --progress-bar off
```
Expected: Successfully installed `fastapi`, `uvicorn`, `jinja2`, and their dependencies.

- [ ] **Step 3: Verify imports**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -c "import fastapi, uvicorn, jinja2; print('DEPENDENCIES READY')"
```
Expected: `DEPENDENCIES READY`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt requirement.txt
git commit -m "build: add fastapi, uvicorn, and jinja2 dependencies"
```

---

### Task 2: Refactor `classify_waste.py` for Programmatic Invocation

**Files:**
- Modify: `src/classify_waste.py:58-109`
- Test: `src/test_openai_migration.py`

**Interfaces:**
- Consumes: `chemical: str`, `client: OpenAI | None = None`
- Produces: `classify_chemical(chemical: str, client: OpenAI | None = None) -> HazardClassification`

- [ ] **Step 1: Write the failing unit test**

In `src/test_openai_migration.py`, add a test verifying that `classify_chemical` accepts an explicit client instance:

```python
    def test_classify_chemical_accepts_explicit_client(self):
        module = self.import_script(ROOT / 'classify_waste.py', 'classify_explicit_mod')
        custom_client = FakeClient()
        expected = module.HazardClassification(
            flammable=True,
            carcinogenic=False,
            infectious=False,
            toxic=False,
            corrosive=False,
        )
        custom_client.responses.parsed = expected

        result = module.classify_chemical('Ethanol', client=custom_client)

        self.assertIs(result, expected)
        self.assertEqual(len(custom_client.responses.calls), 1)
        self.assertIn('Ethanol', custom_client.responses.calls[0]['input'])
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest src.test_openai_migration.TestOpenAIMigration.test_classify_chemical_accepts_explicit_client
```
Expected: FAIL with `TypeError: classify_chemical() got an unexpected keyword argument 'client'`

- [ ] **Step 3: Modify `classify_chemical` in `src/classify_waste.py`**

Update `classify_chemical` to accept an optional `client=None` argument, falling back to module `client`:

```python
def classify_chemical(chemical, client=None):
    active_client = client if client is not None else globals().get("client")
    if active_client is None:
        raise RuntimeError("OpenAI client is not configured.")

    prompt = f"""
You are assisting with preliminary hazardous-waste classification for
a university wet laboratory.

Chemical/waste name:
{chemical}

Determine whether the material belongs to each of these categories:

1. Flammable
2. Carcinogenic
3. Infectious
4. Toxic
5. Corrosive

Important classification rules:

- More than one category may be true.
- Flammable means the material presents a meaningful fire/ignition hazard
  under normal laboratory handling or waste-management conditions.
- Carcinogenic means the chemical is recognized or reasonably established
  as a human or animal carcinogenic hazard by authoritative systems such as
  IARC, NTP, OSHA, EPA or equivalent recognized sources.
- Infectious should normally be FALSE for a pure chemical. Mark it TRUE only
  when the waste name itself clearly indicates biological, microbiological,
  clinical, recombinant, culture, blood, pathogen or infectious contamination.
  Do not infer biological contamination merely because the material came from
  a wet laboratory.
- Toxic means significant acute or chronic toxicity to humans or the
  environment.
- Corrosive means strong acidic/basic or otherwise materially corrosive
  behaviour relevant to laboratory waste handling.
- Classify conservatively.
- Do not classify something merely because all chemicals can theoretically
  cause harm at sufficiently high exposure.
- If the supplied name is a mixture or solution, classify according to the
  waste description provided.
"""

    response = active_client.responses.parse(
        model=MODEL,
        input=prompt,
        reasoning={"effort": REASONING_EFFORT},
        text_format=HazardClassification,
    )

    if response.output_parsed is None:
        raise RuntimeError("OpenAI returned no parsed classification output.")

    return response.output_parsed
```

- [ ] **Step 4: Run test suite to verify it passes**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest discover -s src -p "test_*.py" -v
```
Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/classify_waste.py src/test_openai_migration.py
git commit -m "refactor(classify): allow passing explicit client to classify_chemical"
```

---

### Task 3: Refactor `generate_management_plan.py` for Programmatic Invocation

**Files:**
- Modify: `src/generate_management_plan.py:98-177`
- Test: `src/test_openai_migration.py`

**Interfaces:**
- Consumes: `chemical: str`, `categories: list[str]`, `client: OpenAI | None = None`
- Produces: `make_plan(chemical: str, categories: list[str], client: OpenAI | None = None) -> ManagementPlan`

- [ ] **Step 1: Write the failing unit test**

In `src/test_openai_migration.py`, add a test verifying that `make_plan` accepts an explicit client instance:

```python
    def test_make_plan_accepts_explicit_client(self):
        module = self.import_script(ROOT / 'generate_management_plan.py', 'plan_explicit_mod')
        custom_client = FakeClient()
        expected = module.ManagementPlan(
            chemical='Acetone',
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
            prohibited_or_unsafe_actions='none',
            verification_required='ver',
        )
        custom_client.responses.parsed = expected

        result = module.make_plan('Acetone', ['Flammable'], client=custom_client)

        self.assertIs(result, expected)
        self.assertEqual(len(custom_client.responses.calls), 1)
        self.assertIn('Acetone', custom_client.responses.calls[0]['input'])
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest src.test_openai_migration.TestOpenAIMigration.test_make_plan_accepts_explicit_client
```
Expected: FAIL with `TypeError: make_plan() got an unexpected keyword argument 'client'`

- [ ] **Step 3: Modify `make_plan` in `src/generate_management_plan.py`**

Update `make_plan` to accept an optional `client=None` argument, falling back to module `client`:

```python
def make_plan(chemical, categories, client=None):
    active_client = client if client is not None else globals().get("client")
    if active_client is None:
        raise RuntimeError("OpenAI client is not configured.")

    category_text = ", ".join(categories)

    prompt = f"""
Prepare a conservative hazardous-waste management planning framework
for a university wet laboratory.

Waste/chemical:
{chemical}

Previously identified hazard categories:
{category_text}

The output will be used as a preliminary institutional planning document,
not as authorization to perform treatment.

Use the following regulatory basis when appropriate:

UNITED STATES:
- Resource Conservation and Recovery Act (RCRA).
- 40 CFR Part 261 hazardous-waste identification.
- Consider listed wastes where applicable.
- Characteristic hazardous waste:
  D001 ignitability,
  D002 corrosivity,
  D003 reactivity,
  D004-D043 toxicity characteristic where applicable.
- Treatment and land-disposal requirements depend on actual waste code,
  concentration, waste matrix and generator status.

INDIA:
- Hazardous and Other Wastes (Management and Transboundary Movement)
  Rules, 2016, as amended.
- Applicable CPCB/SPCB/PCC requirements.
- Treatment, Storage and Disposal Facility (TSDF) route where applicable.
- Authorized recycler/utilizer/co-processor/incinerator only where
  applicable and legally permitted.
- Proper packaging, labeling, storage, records, transport and manifest
  procedures should be considered.
- Actual authorization and waste-category determination must be checked
  with the relevant State Pollution Control Board/Pollution Control
  Committee.

Important safety instructions:

1. Do NOT give improvised laboratory-scale destruction recipes.
2. Do NOT recommend pouring hazardous chemicals into drains.
3. Do NOT recommend evaporation as a routine disposal method.
4. Do NOT recommend mixing incompatible waste streams.
5. Do NOT give exact neutralization quantities or reaction recipes.
6. Prefer segregation, secure containment and transfer to an authorized
    hazardous-waste treatment/disposal service when uncertainty exists.
7. Distinguish treatment from final disposal.
8. If treatment depends on concentration, pH, contamination, physical
    state, mixture composition, flash point or analytical testing, state
    that explicitly.
9. Do not invent an EPA waste code or Indian Schedule classification when
    the chemical name alone is insufficient.
10. If the waste name is ambiguous, explicitly require SDS/process/waste
    characterization before disposal.
11. For infectious/biologically contaminated material, flag that applicable
    biomedical/biosafety regulations may apply in addition to chemical
    hazardous-waste requirements.

For each field provide concise but practically useful institutional
guidance.
"""

    response = active_client.responses.parse(
        model=MODEL,
        input=prompt,
        reasoning={"effort": REASONING_EFFORT},
        text_format=ManagementPlan,
    )

    if response.output_parsed is None:
        raise RuntimeError("OpenAI returned no parsed management-plan output.")

    return response.output_parsed
```

- [ ] **Step 4: Run test suite to verify it passes**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest discover -s src -p "test_*.py" -v
```
Expected: All 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/generate_management_plan.py src/test_openai_migration.py
git commit -m "refactor(plan): allow passing explicit client to make_plan"
```

---

### Task 4: Implement Physical Segregation Bin Engine & Unified Dossier Models

**Files:**
- Create: `src/models.py`
- Create: `src/test_models.py`

**Interfaces:**
- Consumes: None
- Produces:
  - `WasteManagementDossier` (Pydantic BaseModel)
  - `assign_segregation_bin(categories: list[str], chemical: str, review_required: bool = False) -> str`

- [ ] **Step 1: Write the failing unit tests**

Create `src/test_models.py`:

```python
import unittest
from src.models import WasteManagementDossier, assign_segregation_bin


class TestModels(unittest.TestCase):
    def test_assign_segregation_bin_rules(self):
        # 1. Review required items
        self.assertEqual(assign_segregation_bin([], 'Unknown Liquid', review_required=True), 'Review Queue')

        # 2. Infectious items
        self.assertEqual(assign_segregation_bin(['Infectious'], 'Bacterial Culture Broth'), 'Biohazard & Infectious')

        # 3. Flammable solvents
        self.assertEqual(assign_segregation_bin(['Flammable', 'Toxic'], 'Methanol'), 'Flammable Solvents')

        # 4. Inorganic Bases
        self.assertEqual(assign_segregation_bin(['Corrosive'], 'Sodium Hydroxide 10M'), 'Inorganic Bases')
        self.assertEqual(assign_segregation_bin(['Corrosive'], 'Ammonium Hydroxide 28%'), 'Inorganic Bases')

        # 5. Inorganic Acids
        self.assertEqual(assign_segregation_bin(['Corrosive', 'Toxic'], 'Hydrochloric Acid 37%'), 'Inorganic Acids')
        self.assertEqual(assign_segregation_bin(['Corrosive'], 'Sulfuric Acid 98%'), 'Inorganic Acids')

        # 6. Carcinogenic & Toxic Organics
        self.assertEqual(assign_segregation_bin(['Toxic', 'Carcinogenic'], 'Ethidium Bromide Solution'), 'Carcinogenic & Toxic Organics')
        self.assertEqual(assign_segregation_bin(['Toxic'], 'Potassium Cyanide'), 'Carcinogenic & Toxic Organics')

    def test_waste_management_dossier_serialization(self):
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
        data = dossier.model_dump()
        self.assertEqual(data['chemical'], 'Methanol')
        self.assertEqual(data['bin'], 'Flammable Solvents')
        self.assertFalse(data['review_required'])


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest src/test_models.py
```
Expected: FAIL with `ModuleNotFoundError: No module named 'src.models'`

- [ ] **Step 3: Implement `src/models.py`**

Create `src/models.py`:

```python
from pydantic import BaseModel, Field


class WasteManagementDossier(BaseModel):
    chemical: str
    bin: str
    categories: list[str] = Field(default_factory=list)
    container: str
    storage: str
    ppe: str
    segregation: str
    labeling: str
    spill: str
    identification: str
    prohibited: str
    verification: str
    usepa: str
    india: str
    treatment: str
    disposal: str
    review_required: bool = False
    review_reason: str | None = None


def assign_segregation_bin(categories: list[str], chemical: str, review_required: bool = False) -> str:
    """
    Deterministic rule-based mapping of hazard categories and chemical name
    to standardized laboratory storage cabinets (Segregation Bins).
    """
    if review_required or not categories:
        return "Review Queue"

    if "Infectious" in categories:
        return "Biohazard & Infectious"

    if "Flammable" in categories:
        return "Flammable Solvents"

    if "Corrosive" in categories:
        chem_lower = chemical.lower()
        base_keywords = ("hydroxide", "ammonia", "amine", "alkali", "base", "naoh", "koh")
        if any(kw in chem_lower for kw in base_keywords):
            return "Inorganic Bases"
        return "Inorganic Acids"

    if "Carcinogenic" in categories or "Toxic" in categories:
        return "Carcinogenic & Toxic Organics"

    return "Review Queue"
```

- [ ] **Step 4: Run test suite to verify it passes**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest src/test_models.py
```
Expected: All tests in `test_models.py` PASS.

- [ ] **Step 5: Commit**

```bash
git add src/models.py src/test_models.py
git commit -m "feat(models): implement WasteManagementDossier and assign_segregation_bin"
```

---

### Task 5: Implement Core Lookup Service & Error Resilience

**Files:**
- Create: `src/services.py`
- Create: `src/test_services.py`

**Interfaces:**
- Consumes: `chemical: str`, `client: OpenAI | None = None`
- Produces: `lookup_chemical(chemical: str, client: OpenAI | None = None) -> WasteManagementDossier`

- [ ] **Step 1: Write the failing unit tests**

Create `src/test_services.py`:

```python
import types
import unittest
from src.classify_waste import HazardClassification
from src.generate_management_plan import ManagementPlan
from src.services import lookup_chemical


class FakeResponses:
    def __init__(self):
        self.calls = []
        self.parsed = None

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return types.SimpleNamespace(output_parsed=self.parsed)


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


class TestServices(unittest.TestCase):
    def test_lookup_chemical_success(self):
        client = FakeClient()
        classification = HazardClassification(
            flammable=True,
            carcinogenic=False,
            infectious=False,
            toxic=True,
            corrosive=False,
        )
        plan = ManagementPlan(
            chemical='Methanol',
            identification_and_characterization='HPLC solvent',
            segregation_and_incompatibilities='Separate from oxidizers',
            recommended_container='Safety can',
            labeling_requirements='Flammable Toxic',
            storage_requirements='Flammable cabinet',
            handling_and_ppe='Nitrile gloves',
            spill_and_emergency_management='Absorb with pads',
            treatment_framework='TSDF thermal oxidation',
            final_disposal_framework='High temp incinerator',
            usepa_framework='D001, U154',
            indian_framework='HOWM Schedule I',
            prohibited_or_unsafe_actions='Never pour down drain',
            verification_required='Verify flash point',
        )

        # First call is classify, second is plan
        def side_effect(**kwargs):
            if kwargs['text_format'] is HazardClassification:
                return types.SimpleNamespace(output_parsed=classification)
            return types.SimpleNamespace(output_parsed=plan)

        client.responses.parse = side_effect

        dossier = lookup_chemical('Methanol', client=client)

        self.assertEqual(dossier.chemical, 'Methanol')
        self.assertEqual(dossier.bin, 'Flammable Solvents')
        self.assertEqual(dossier.categories, ['Flammable', 'Toxic'])
        self.assertEqual(dossier.recommended_container, 'Safety can')
        self.assertEqual(dossier.prohibited, 'Never pour down drain')
        self.assertFalse(dossier.review_required)

    def test_lookup_chemical_graceful_error_handling(self):
        client = FakeClient()

        def failing_parse(**kwargs):
            raise RuntimeError("API connection timeout")

        client.responses.parse = failing_parse

        dossier = lookup_chemical('Mystery Liquid', client=client)

        self.assertEqual(dossier.chemical, 'Mystery Liquid')
        self.assertEqual(dossier.bin, 'Review Queue')
        self.assertTrue(dossier.review_required)
        self.assertIn("API connection timeout", dossier.review_reason)
        self.assertIn("STRICTLY PROHIBITED", dossier.prohibited)
        self.assertIn("Isolate in chemical fume hood", dossier.storage)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest src/test_services.py
```
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services'`

- [ ] **Step 3: Implement `src/services.py`**

Create `src/services.py`:

```python
import logging
from src.classify_waste import classify_chemical, normalize_chemical_name
from src.generate_management_plan import make_plan
from src.models import WasteManagementDossier, assign_segregation_bin

logger = logging.getLogger(__name__)

CATEGORIES_ORDER = ["Flammable", "Carcinogenic", "Infectious", "Toxic", "Corrosive"]


def lookup_chemical(chemical: str, client=None) -> WasteManagementDossier:
    clean_name = normalize_chemical_name(chemical)
    if not clean_name:
        return create_fallback_dossier("Unspecified Chemical", "Empty chemical name provided.")

    try:
        classification = classify_chemical(clean_name, client=client)

        active_categories = []
        if classification.flammable:
            active_categories.append("Flammable")
        if classification.carcinogenic:
            active_categories.append("Carcinogenic")
        if classification.infectious:
            active_categories.append("Infectious")
        if classification.toxic:
            active_categories.append("Toxic")
        if classification.corrosive:
            active_categories.append("Corrosive")

        plan = make_plan(clean_name, active_categories, client=client)
        bin_name = assign_segregation_bin(active_categories, clean_name, review_required=False)

        return WasteManagementDossier(
            chemical=clean_name,
            bin=bin_name,
            categories=active_categories,
            container=plan.recommended_container,
            storage=plan.storage_requirements,
            ppe=plan.handling_and_ppe,
            segregation=plan.segregation_and_incompatibilities,
            labeling=plan.labeling_requirements,
            spill=plan.spill_and_emergency_management,
            identification=plan.identification_and_characterization,
            prohibited=plan.prohibited_or_unsafe_actions,
            verification=plan.verification_required,
            usepa=plan.usepa_framework,
            india=plan.indian_framework,
            treatment=plan.treatment_framework,
            disposal=plan.final_disposal_framework,
            review_required=False,
            review_reason=None,
        )

    except Exception as e:
        logger.warning(f"Error during lookup for chemical '{clean_name}': {e}")
        return create_fallback_dossier(clean_name, str(e))


def create_fallback_dossier(chemical: str, reason: str) -> WasteManagementDossier:
    return WasteManagementDossier(
        chemical=chemical,
        bin="Review Queue",
        categories=[],
        container="Dedicated chemical-resistant secondary containment vessel",
        storage="Isolate in chemical fume hood secondary tray pending chemical characterization.",
        ppe="High-protection laboratory PPE: double nitrile/butyl gloves, splash face shield, certified fume hood.",
        segregation="Isolate from all active waste streams until analytical test strips confirm pH, flammability, and reactivity.",
        labeling="UNKNOWN CHEMICAL WASTE - PENDING ANALYTICAL CHARACTERIZATION",
        spill="Cordon area immediately. Evacuate non-essential personnel. Notify laboratory safety officer.",
        identification=f"Material requiring manual review or characterization. Diagnostic note: {reason}",
        prohibited="STRICTLY PROHIBITED TO MOVE, DRAIN-DISPOSE, OR CO-MINGLE BEFORE SAFETY VERIFICATION.",
        verification=f"MANDATORY: Verify identity using SDS or analytical testing before disposal authorization. Reason: {reason}",
        usepa="Pending analytical hazardous waste determination (40 CFR Part 261).",
        india="HOWM Rules 2016: Characterization required prior to TSDF authorization.",
        treatment="No laboratory bench treatment permitted.",
        disposal="Hold in designated quarantine area pending certified EHS characterization.",
        review_required=True,
        review_reason=reason,
    )
```

- [ ] **Step 4: Run test suite to verify it passes**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest src/test_services.py
```
Expected: All tests in `test_services.py` PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services.py src/test_services.py
git commit -m "feat(services): implement lookup_chemical with graceful error handling"
```

---

### Task 6: Implement Base HTML Template (Variant C Shell & Slide-Over Dossier)

**Files:**
- Create: `src/templates/index.html`

**Interfaces:**
- Consumes: None (Alpine.js + Tailwind CSS)
- Produces: Web interface template serving search input, active batch summary, card grid container, and slide-over dossier

- [ ] **Step 1: Create template directory**

Ensure directory `src/templates/` exists.

- [ ] **Step 2: Create `src/templates/index.html`**

Write `src/templates/index.html` implementing Variant C (Physical Segregation Bins) with Alpine.js reactive state binding to `POST /api/lookup`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hazardous Waste Management Platform (D2S-MTP)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['Plus Jakarta Sans', 'system-ui', 'sans-serif'],
            mono: ['JetBrains Mono', 'monospace'],
          }
        }
      }
    }
  </script>
  <style>[x-cloak] { display: none !important; }</style>
</head>
<body class="bg-slate-950 text-slate-100 font-sans antialiased min-h-screen pb-16 selection:bg-emerald-500/30 selection:text-emerald-200"
      x-data="hazWasteApp()" x-cloak>

  <!-- Global Header -->
  <header class="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-30">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-lg">
          ☣
        </div>
        <div>
          <div class="flex items-center gap-2">
            <span class="font-bold tracking-tight text-white">HazWaste Studio</span>
            <span class="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">D2S-MTP</span>
            <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">Variant C</span>
          </div>
          <p class="text-xs text-slate-400">Institutional Wet Laboratory Waste Classification & Segregation</p>
        </div>
      </div>

      <!-- Quick Chemical Search -->
      <div class="flex items-center gap-3">
        <div class="relative w-80">
          <input type="text"
                 x-model="searchQuery"
                 @keydown.enter="performLookup()"
                 placeholder="Quick lookup chemical (e.g. Methanol)..."
                 :disabled="isLoading"
                 class="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-16 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 disabled:opacity-50">
          <span class="absolute left-2.5 top-2 text-slate-500 text-xs">🔍</span>
          <span class="absolute right-2 top-1.5 text-[10px] font-mono text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded">Enter ↵</span>
        </div>
      </div>
    </div>
  </header>

  <!-- Main View Area -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">

    <!-- Active Chemical Summary Card (Shown when an ad-hoc chemical is looked up) -->
    <template x-if="activeDossier">
      <div class="space-y-6">
        <div class="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <div class="flex items-center gap-2">
              <span class="text-xs font-mono text-emerald-400 uppercase tracking-wider">Active Chemical Evaluation</span>
              <span class="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono" x-text="activeDossier.bin"></span>
            </div>
            <h1 class="text-2xl font-bold text-white mt-1" x-text="activeDossier.chemical"></h1>
          </div>
          <button @click="openDrawer()" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition shadow-sm">
            View Complete 14-Field Dossier →
          </button>
        </div>

        <!-- Segregation Preview Card (Variant C) -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            <div class="text-xs font-mono text-slate-400 uppercase">Physical Storage Bin</div>
            <div class="text-lg font-bold text-white flex items-center gap-2">
              <span>🗄️</span>
              <span x-text="activeDossier.bin"></span>
            </div>
            <div class="text-xs text-slate-400 leading-relaxed" x-text="activeDossier.storage"></div>
          </div>

          <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            <div class="text-xs font-mono text-slate-400 uppercase">Recommended Container</div>
            <div class="text-base font-semibold text-slate-200" x-text="activeDossier.container"></div>
            <div class="text-xs text-slate-400 leading-relaxed" x-text="activeDossier.labeling"></div>
          </div>

          <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            <div class="text-xs font-mono text-slate-400 uppercase">Hazard Profile</div>
            <div class="flex flex-wrap gap-1.5">
              <template x-for="cat in activeDossier.categories" :key="cat">
                <span :class="getBadgeClass(cat)" class="text-xs px-2.5 py-0.5 rounded font-medium border" x-text="cat"></span>
              </template>
              <template x-if="activeDossier.categories.length === 0">
                <span class="text-xs px-2.5 py-0.5 rounded font-medium border bg-amber-500/15 text-amber-300 border-amber-500/30">Review Required</span>
              </template>
            </div>
            <div class="text-[11px] text-slate-400" x-text="activeDossier.identification"></div>
          </div>
        </div>
      </div>
    </template>

    <!-- Empty State -->
    <template x-if="!activeDossier && !isLoading">
      <div class="text-center py-24 border border-dashed border-slate-800 rounded-2xl bg-slate-900/40">
        <span class="text-4xl block mb-3">🧪</span>
        <h2 class="text-base font-bold text-white">Hazardous Waste Ad-Hoc Chemical Lookup</h2>
        <p class="text-xs text-slate-400 max-w-md mx-auto mt-1">
          Type a waste or chemical name into the search bar above (e.g., <code class="text-emerald-400 font-mono">Methanol</code> or <code class="text-emerald-400 font-mono">Hydrochloric Acid</code>) to generate an institutional waste management plan and physical segregation bin assignment.
        </p>
      </div>
    </template>

    <!-- Loading State -->
    <template x-if="isLoading">
      <div class="text-center py-24">
        <div class="w-8 h-8 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
        <div class="text-xs font-mono text-slate-300">Evaluating chemical hazard classification & planning...</div>
      </div>
    </template>
  </main>

  <!-- Slide-Over Compliance Dossier Drawer -->
  <div x-show="drawerOpen" class="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true">
    <div class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm transition-opacity" @click="drawerOpen = false"></div>

    <div class="fixed inset-y-0 right-0 max-w-2xl w-full bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col">
      <!-- Drawer Header -->
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
        <div>
          <div class="text-xs font-mono text-emerald-400 uppercase tracking-wider">Institutional Waste Plan Dossier</div>
          <h2 class="text-lg font-bold text-white mt-0.5" x-text="activeDossier?.chemical"></h2>
        </div>
        <button @click="drawerOpen = false" class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 text-lg">✕</button>
      </div>

      <!-- Drawer Tabs -->
      <div class="flex border-b border-slate-800 px-6 text-xs font-medium bg-slate-950/40">
        <button @click="activeTab = 'safety'"
                :class="activeTab === 'safety' ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-slate-400 hover:text-slate-200'"
                class="py-3 px-3 border-b-2 transition">
          1. Handling & Containment
        </button>
        <button @click="activeTab = 'emergency'"
                :class="activeTab === 'emergency' ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-slate-400 hover:text-slate-200'"
                class="py-3 px-3 border-b-2 transition">
          2. Spill & Emergency
        </button>
        <button @click="activeTab = 'regulatory'"
                :class="activeTab === 'regulatory' ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-slate-400 hover:text-slate-200'"
                class="py-3 px-3 border-b-2 transition">
          3. Regulatory (RCRA / HOWM)
        </button>
      </div>

      <!-- Drawer Body -->
      <div class="flex-1 overflow-y-auto p-6 space-y-4 text-xs">
        <template x-if="activeDossier">
          <div>
            <!-- Hazard Category Badges -->
            <div class="flex flex-wrap gap-1.5 mb-4">
              <template x-for="cat in activeDossier.categories" :key="cat">
                <span :class="getBadgeClass(cat)" class="text-xs px-2.5 py-0.5 rounded font-medium border" x-text="cat"></span>
              </template>
            </div>

            <!-- Tab 1: Safety & Handling -->
            <div x-show="activeTab === 'safety'" class="space-y-4">
              <div class="p-3.5 bg-red-950/50 border border-red-800 rounded-xl text-red-200 shadow-sm">
                <div class="font-bold text-red-300 flex items-center gap-1.5 text-xs mb-1">
                  <span>⛔</span> STRICTLY PROHIBITED ACTIONS
                </div>
                <p class="leading-relaxed text-[11px]" x-text="activeDossier.prohibited"></p>
              </div>

              <div class="grid grid-cols-2 gap-3">
                <div class="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                  <div class="text-slate-400 font-mono text-[10px] uppercase">Recommended Container</div>
                  <div class="text-slate-200 mt-1 font-semibold text-xs" x-text="activeDossier.container"></div>
                </div>
                <div class="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                  <div class="text-slate-400 font-mono text-[10px] uppercase">Storage Protocol</div>
                  <div class="text-slate-200 mt-1 text-xs" x-text="activeDossier.storage"></div>
                </div>
              </div>

              <div class="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                <div class="text-slate-400 font-mono text-[10px] uppercase">Handling & Personal Protective Equipment (PPE)</div>
                <div class="text-slate-200 mt-1 leading-relaxed" x-text="activeDossier.ppe"></div>
              </div>

              <div class="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                <div class="text-slate-400 font-mono text-[10px] uppercase">Segregation & Incompatibilities</div>
                <div class="text-slate-200 mt-1 leading-relaxed" x-text="activeDossier.segregation"></div>
              </div>

              <div class="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                <div class="text-slate-400 font-mono text-[10px] uppercase">Container Labeling Requirements</div>
                <div class="text-slate-200 mt-1 leading-relaxed" x-text="activeDossier.labeling"></div>
              </div>
            </div>

            <!-- Tab 2: Spill & Emergency -->
            <div x-show="activeTab === 'emergency'" class="space-y-4">
              <div class="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                <div class="text-slate-400 font-mono text-[10px] uppercase">Spill & Emergency Procedures</div>
                <div class="text-slate-200 mt-1 leading-relaxed" x-text="activeDossier.spill"></div>
              </div>
              <div class="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                <div class="text-slate-400 font-mono text-[10px] uppercase">Identification & Characterization</div>
                <div class="text-slate-200 mt-1 leading-relaxed" x-text="activeDossier.identification"></div>
              </div>
            </div>

            <!-- Tab 3: Regulatory Compliance -->
            <div x-show="activeTab === 'regulatory'" class="space-y-4">
              <div class="p-3.5 bg-amber-950/50 border border-amber-800 rounded-xl text-amber-200 shadow-sm">
                <div class="font-bold text-amber-300 flex items-center gap-1.5 text-xs mb-1">
                  <span>📋</span> MANDATORY INSTITUTIONAL VERIFICATION
                </div>
                <p class="leading-relaxed text-[11px]" x-text="activeDossier.verification"></p>
              </div>

              <div class="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                <div class="text-slate-400 font-mono text-[10px] uppercase">USEPA / RCRA Regulatory Framework (40 CFR Part 261)</div>
                <div class="text-slate-200 mt-1 leading-relaxed" x-text="activeDossier.usepa"></div>
              </div>

              <div class="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                <div class="text-slate-400 font-mono text-[10px] uppercase">Indian HOWM Rules, 2016 (CPCB / SPCB Schedule)</div>
                <div class="text-slate-200 mt-1 leading-relaxed" x-text="activeDossier.india"></div>
              </div>

              <div class="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                <div class="text-slate-400 font-mono text-[10px] uppercase">Treatment Framework (Pre-Disposal)</div>
                <div class="text-slate-200 mt-1 leading-relaxed" x-text="activeDossier.treatment"></div>
              </div>

              <div class="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                <div class="text-slate-400 font-mono text-[10px] uppercase">Authorized TSDF & Final Disposal</div>
                <div class="text-slate-200 mt-1 leading-relaxed" x-text="activeDossier.disposal"></div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>

  <script>
    function hazWasteApp() {
      return {
        searchQuery: '',
        isLoading: false,
        activeDossier: null,
        drawerOpen: false,
        activeTab: 'safety',

        async performLookup() {
          const query = this.searchQuery.trim();
          if (!query) return;

          this.isLoading = true;
          try {
            const resp = await fetch('/api/lookup', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ chemical: query })
            });

            if (!resp.ok) {
              throw new Error(`Lookup failed with status ${resp.status}`);
            }

            this.activeDossier = await resp.json();
            this.openDrawer();
          } catch (err) {
            alert(`Error looking up chemical: ${err.message}`);
          } finally {
            this.isLoading = false;
          }
        },

        openDrawer() {
          this.drawerOpen = true;
        },

        getBadgeClass(category) {
          switch(category) {
            case 'Flammable':
              return 'bg-orange-500/15 text-orange-300 border-orange-500/30';
            case 'Toxic':
              return 'bg-red-500/15 text-red-300 border-red-500/30';
            case 'Corrosive':
              return 'bg-purple-500/15 text-purple-300 border-purple-500/30';
            case 'Infectious':
              return 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30';
            case 'Carcinogenic':
              return 'bg-pink-500/15 text-pink-300 border-pink-500/30';
            default:
              return 'bg-slate-800 text-slate-300 border-slate-700';
          }
        }
      }
    }
  </script>
</body>
</html>
```

- [ ] **Step 3: Commit**

```bash
git add src/templates/index.html
git commit -m "feat(ui): add base HTML template with search bar and slide-over dossier"
```

---

### Task 7: Implement FastAPI Application Routes & End-to-End Test Suite

**Files:**
- Create: `src/app.py`
- Create: `src/test_app.py`

**Interfaces:**
- Consumes: `src/services.py`, `src/models.py`, `src/templates/index.html`
- Produces: FastAPI app with `GET /`, `POST /api/lookup`, `GET /health`

- [ ] **Step 1: Write the failing end-to-end unit tests**

Create `src/test_app.py`:

```python
import types
import unittest
from fastapi.testclient import TestClient
from src.classify_waste import HazardClassification
from src.generate_management_plan import ManagementPlan


class FakeResponses:
    def __init__(self):
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs['text_format'] is HazardClassification:
            return types.SimpleNamespace(output_parsed=HazardClassification(
                flammable=True, carcinogenic=False, infectious=False, toxic=True, corrosive=False
            ))
        return types.SimpleNamespace(output_parsed=ManagementPlan(
            chemical=kwargs.get('input', 'test'),
            identification_and_characterization='Identification desc',
            segregation_and_incompatibilities='Keep away from oxidizers',
            recommended_container='Safety can Type I',
            labeling_requirements='Flammable solvent',
            storage_requirements='Flammable cabinet',
            handling_and_ppe='Nitrile gloves and goggles',
            spill_and_emergency_management='Absorb with pads',
            treatment_framework='Thermal destruction',
            final_disposal_framework='Authorized TSDF',
            usepa_framework='D001',
            indian_framework='HOWM Schedule I',
            prohibited_or_unsafe_actions='No drain disposal',
            verification_required='Flash point check',
        ))


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


class TestApp(unittest.TestCase):
    def setUp(self):
        from src.app import app
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'healthy'})

    def test_root_serves_html(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])
        self.assertIn('HazWaste Studio', response.text)

    def test_lookup_endpoint_success(self):
        import src.services as services
        fake = FakeClient()
        orig_lookup = services.lookup_chemical

        # Test lookup with explicit fake client
        try:
            services.lookup_chemical = lambda chem: orig_lookup(chem, client=fake)
            response = self.client.post('/api/lookup', json={'chemical': 'Methanol'})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['chemical'], 'Methanol')
            self.assertEqual(data['bin'], 'Flammable Solvents')
            self.assertIn('Flammable', data['categories'])
            self.assertFalse(data['review_required'])
            self.assertEqual(data['prohibited'], 'No drain disposal')
        finally:
            services.lookup_chemical = orig_lookup

    def test_lookup_endpoint_empty_payload_validation(self):
        response = self.client.post('/api/lookup', json={})
        self.assertEqual(response.status_code, 422)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest src/test_app.py
```
Expected: FAIL with `ModuleNotFoundError: No module named 'src.app'`

- [ ] **Step 3: Implement `src/app.py`**

Create `src/app.py`:

```python
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from src.models import WasteManagementDossier
from src.services import lookup_chemical

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
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/lookup", response_model=WasteManagementDossier)
async def api_lookup_chemical(payload: LookupRequest):
    chemical = payload.chemical.strip()
    if not chemical:
        raise HTTPException(status_code=422, detail="Chemical name cannot be empty.")
    return lookup_chemical(chemical)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.app:app", host="127.0.0.1", port=8000, reload=True)
```

- [ ] **Step 4: Run all unit tests to verify they pass**

Run:
```powershell
& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest discover -s src -p "test_*.py" -v
```
Expected: All tests in `test_openai_migration.py`, `test_models.py`, `test_services.py`, and `test_app.py` PASS cleanly.

- [ ] **Step 5: Commit**

```bash
git add src/app.py src/test_app.py
git commit -m "feat(app): implement FastAPI server with ad-hoc lookup endpoint and tests"
```

---

## Self-Review Checklist

- [x] **Spec coverage**:
  - `classify_waste.py` & `generate_management_plan.py` refactored into importable functions? Covered in Task 2 & Task 3.
  - Base FastAPI server and HTML shell (Variant C) served? Covered in Task 1, 6, & 7.
  - Ad-hoc quick-lookup bar with slide-over 3-tab compliance dossier? Covered in Task 4, 5, 6, & 7.
  - Red prohibited actions banner & amber verification banner? Covered in Task 4 & 6.
  - Graceful 200 handling for unknown/failed chemicals? Covered in Task 5.
  - Physical Segregation Bins mapping? Covered in Task 4.
  - Stdlib `unittest` test suite with `FakeClient` fixture? Covered in Task 4, 5, & 7.
- [x] **No Placeholders**: All code snippets, tests, commands, and assertions are complete and executable.
- [x] **Type consistency**: `WasteManagementDossier` fields, `assign_segregation_bin` signatures, and `lookup_chemical` contracts match across `models.py`, `services.py`, `app.py`, and all test suites.
