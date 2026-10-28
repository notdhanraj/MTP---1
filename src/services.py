import datetime
import io
import json
import logging
from pathlib import Path
from typing import Iterator
import pandas as pd
from src.classify_waste import HazardClassification, classify_chemical, normalize_chemical_name
from src.generate_management_plan import make_plan
from src.models import (
    BatchQueuedResponse,
    BatchRunResponse,
    WasteManagementDossier,
    assign_segregation_bin,
)

logger = logging.getLogger(__name__)

DEFAULT_RUNS_DIR = Path(__file__).resolve().parent.parent / "data" / "runs"
MAX_BATCH_SIZE = 50

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
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
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


def _extract_active_categories(clf_obj_or_dict) -> list[str]:
    if isinstance(clf_obj_or_dict, dict):
        return [cat for cat in CATEGORIES_ORDER if clf_obj_or_dict.get(cat.lower(), False)]
    cats = []
    if getattr(clf_obj_or_dict, "flammable", False):
        cats.append("Flammable")
    if getattr(clf_obj_or_dict, "carcinogenic", False):
        cats.append("Carcinogenic")
    if getattr(clf_obj_or_dict, "infectious", False):
        cats.append("Infectious")
    if getattr(clf_obj_or_dict, "toxic", False):
        cats.append("Toxic")
    if getattr(clf_obj_or_dict, "corrosive", False):
        cats.append("Corrosive")
    return cats


def initialize_batch_run(
    file_bytes: bytes,
    filename: str,
    pause_after_classification: bool = False,
    runs_dir: Path | None = None,
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
        status="queued",
    )


def stream_batch_events(
    run_id: str,
    stage: str | None = None,
    runs_dir: Path | None = None,
    client=None,
) -> Iterator[dict]:
    target_runs_dir = runs_dir if runs_dir is not None else DEFAULT_RUNS_DIR
    run_dir = target_runs_dir / run_id
    meta_path = run_dir / "meta.json"

    if not meta_path.exists():
        raise FileNotFoundError(f"Run {run_id} not found.")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    chemicals: list[str] = meta.get("chemicals", [])
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

    def _save_meta():
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    execute_classification = (stage is None or stage == "classification") and stage != "planning"
    execute_planning = (stage == "planning") or (stage is None and not meta.get("pause_after_classification", False))

    # --- STAGE 1: CLASSIFICATION ---
    if execute_classification:
        meta["status"] = "classifying"
        _save_meta()

        yield {"type": "stage_start", "stage": "classification", "total": total}

        for idx, chem in enumerate(chemicals, start=1):
            if chem in classifications:
                clf_dict = classifications[chem]["classification"]
                bin_name = classifications[chem]["bin"]
            else:
                try:
                    clf_obj = classify_chemical(chem, client=client)
                    active_cats = _extract_active_categories(clf_obj)
                    bin_name = assign_segregation_bin(active_cats, chem, review_required=False)
                    clf_dict = clf_obj.model_dump()
                except Exception as e:
                    logger.warning(f"Error during classification for chemical '{chem}': {e}")
                    clf_dict = HazardClassification(
                        flammable=False, carcinogenic=False, infectious=False, toxic=False, corrosive=False
                    ).model_dump()
                    bin_name = "Review Queue"

                classifications[chem] = {
                    "classification": clf_dict,
                    "bin": bin_name,
                }
                bin_counts[bin_name] = bin_counts.get(bin_name, 0) + 1
                meta["classifications"] = classifications
                meta["bin_counts"] = bin_counts
                _save_meta()

            yield {
                "type": "item_progress",
                "stage": "classification",
                "index": idx,
                "total": total,
                "chemical": chem,
                "classification": clf_dict,
                "bin": bin_name,
            }

        yield {
            "type": "stage_complete",
            "stage": "classification",
            "total": total,
            "bin_counts": bin_counts,
        }

        if meta.get("pause_after_classification", False) and stage != "planning":
            meta["status"] = "paused_for_review"
            _save_meta()
            yield {
                "type": "stage_paused",
                "stage": "classification",
                "run_id": run_id,
                "total": total,
                "message": "Classification complete. Paused for review.",
            }
            return

    # --- STAGE 2: MANAGEMENT PLANNING ---
    if execute_planning:
        meta["status"] = "planning"
        _save_meta()

        yield {"type": "stage_start", "stage": "planning", "total": total}

        for idx, chem in enumerate(chemicals, start=1):
            if chem in dossiers:
                dossier_dict = dossiers[chem]
            else:
                clf_info = classifications.get(chem, {})
                clf_data = clf_info.get("classification", {})
                active_categories = _extract_active_categories(clf_data)
                bin_name = clf_info.get("bin") or assign_segregation_bin(active_categories, chem, review_required=False)

                try:
                    plan_obj = make_plan(chem, active_categories, client=client)
                    dossier = WasteManagementDossier(
                        chemical=chem,
                        bin=bin_name,
                        categories=active_categories,
                        container=plan_obj.recommended_container,
                        storage=plan_obj.storage_requirements,
                        ppe=plan_obj.handling_and_ppe,
                        segregation=plan_obj.segregation_and_incompatibilities,
                        labeling=plan_obj.labeling_requirements,
                        spill=plan_obj.spill_and_emergency_management,
                        identification=plan_obj.identification_and_characterization,
                        prohibited=plan_obj.prohibited_or_unsafe_actions,
                        verification=plan_obj.verification_required,
                        usepa=plan_obj.usepa_framework,
                        india=plan_obj.indian_framework,
                        treatment=plan_obj.treatment_framework,
                        disposal=plan_obj.final_disposal_framework,
                        review_required=(bin_name == "Review Queue"),
                        review_reason=None if bin_name != "Review Queue" else "Classification requires review",
                    )
                except Exception as e:
                    logger.warning(f"Error during planning for chemical '{chem}': {e}")
                    dossier = create_fallback_dossier(chem, reason=f"Plan generation error: {e}")

                dossier_dict = dossier.model_dump()
                dossiers[chem] = dossier_dict
                meta["dossiers"] = dossiers

                if dossier.bin != bin_name:
                    bin_counts[bin_name] = max(0, bin_counts.get(bin_name, 0) - 1)
                    bin_counts[dossier.bin] = bin_counts.get(dossier.bin, 0) + 1
                    meta["bin_counts"] = bin_counts

                _save_meta()

            yield {
                "type": "item_progress",
                "stage": "planning",
                "index": idx,
                "total": total,
                "chemical": chem,
                "dossier": dossier_dict,
            }

        meta["status"] = "completed"
        _save_meta()

        yield {
            "type": "complete",
            "status": "completed",
            "run_id": run_id,
            "total_count": total,
            "bin_counts": bin_counts,
            "items": [dossiers[c] for c in chemicals if c in dossiers],
        }

