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
