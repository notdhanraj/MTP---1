import os
import time
import pandas as pd
from pydantic import BaseModel
from src.llm_client import (
    get_openrouter_client,
    generate_structured_output,
    get_model_name,
)



def load_env_file(env_path=None):
    if env_path is None:
        env_path = os.path.join(os.path.dirname(__file__), ".env")

    if not os.path.exists(env_path):
        return

    with open(env_path, encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = [part.strip() for part in line.split("=", 1)]

            if key and key not in os.environ:
                os.environ[key] = value.strip("\"'")


load_env_file()

INPUT_FILE = "classified_hazardous_waste.xlsx"
OUTPUT_FILE = "hazardous_waste_management_plan.xlsx"
MODEL = get_model_name()
REASONING_EFFORT = "medium"
client = None

CATEGORIES = [
    "Flammable",
    "Carcinogenic",
    "Infectious",
    "Toxic",
    "Corrosive",
]


class ManagementPlan(BaseModel):
    chemical: str
    identification_and_characterization: str
    segregation_and_incompatibilities: str
    recommended_container: str
    labeling_requirements: str
    storage_requirements: str
    handling_and_ppe: str
    spill_and_emergency_management: str
    treatment_framework: str
    final_disposal_framework: str
    usepa_framework: str
    indian_framework: str
    prohibited_or_unsafe_actions: str
    verification_required: str





def get_unique_chemicals(df):
    chemicals = {}

    for column in CATEGORIES:
        if column not in df.columns:
            continue

        for value in df[column].dropna():
            name = " ".join(str(value).strip().split())

            if not name:
                continue

            key = name.casefold()

            if key not in chemicals:
                chemicals[key] = {
                    "name": name,
                    "categories": []
                }

            chemicals[key]["categories"].append(column)

    return list(chemicals.values())


def make_plan(chemical, categories, client=None):
    active_client = client if client is not None else get_openrouter_client()

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

    return generate_structured_output(
        client=active_client,
        model=get_model_name(),
        prompt=prompt,
        response_model=ManagementPlan,
    )


def main():
    df = pd.read_excel(
        INPUT_FILE,
        sheet_name="Classification"
    )

    chemical_records = get_unique_chemicals(df)

    print(
        f"Unique chemicals requiring management plans: "
        f"{len(chemical_records)}"
    )

    rows = []
    failed = []

    for i, record in enumerate(chemical_records, start=1):
        chemical = record["name"]
        categories = record["categories"]

        print(
            f"[{i}/{len(chemical_records)}] "
            f"Generating plan: {chemical}"
        )

        try:
            plan = make_plan(
                chemical,
                categories
            )

            rows.append({
                "Chemical": chemical,
                "Hazard Categories": ", ".join(categories),
                "Identification / Characterization":
                    plan.identification_and_characterization,
                "Segregation / Incompatibilities":
                    plan.segregation_and_incompatibilities,
                "Recommended Container":
                    plan.recommended_container,
                "Labeling":
                    plan.labeling_requirements,
                "Storage":
                    plan.storage_requirements,
                "Handling / PPE":
                    plan.handling_and_ppe,
                "Spill / Emergency Management":
                    plan.spill_and_emergency_management,
                "Treatment Framework":
                    plan.treatment_framework,
                "Final Disposal Framework":
                    plan.final_disposal_framework,
                "USEPA / RCRA Framework":
                    plan.usepa_framework,
                "Indian HOWM / CPCB Framework":
                    plan.indian_framework,
                "Prohibited / Unsafe Actions":
                    plan.prohibited_or_unsafe_actions,
                "Verification Required":
                    plan.verification_required,
            })

            time.sleep(0.2)

        except Exception as e:
            print(f"ERROR for {chemical}: {e}")
            failed.append({
                "Chemical": chemical,
                "Error": str(e)
            })

    output_df = pd.DataFrame(rows)

    with pd.ExcelWriter(
        OUTPUT_FILE,
        engine="openpyxl"
    ) as writer:

        output_df.to_excel(
            writer,
            sheet_name="Management Plan",
            index=False
        )

        if failed:
            pd.DataFrame(failed).to_excel(
                writer,
                sheet_name="Review Required",
                index=False
            )

    print()
    print("Finished.")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()