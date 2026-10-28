import datetime
import io
import json
import logging
from pathlib import Path
import pandas as pd
from src.classify_waste import classify_chemical, normalize_chemical_name
from src.generate_management_plan import make_plan
from src.models import BatchRunResponse, WasteManagementDossier, assign_segregation_bin

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
