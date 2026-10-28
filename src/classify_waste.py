import os
import time
import pandas as pd
from openai import OpenAI
from pydantic import BaseModel


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

INPUT_FILE = "C:\\Users\\sdhan\\OneDrive\\Desktop\\MTP - 1\\Code Test\\src\\Hazardous Waste.xlsx"
OUTPUT_FILE = "classified_hazardous_waste.xlsx"
MODEL = "gpt-6-luna"
REASONING_EFFORT = "medium"


class HazardClassification(BaseModel):
    flammable: bool
    carcinogenic: bool
    infectious: bool
    toxic: bool
    corrosive: bool


api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError(
        "OPENAI_API_KEY environment variable is not set."
    )

client = OpenAI(api_key=api_key)


def normalize_chemical_name(value):
    return " ".join(str(value).strip().split())


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


def main():
    df = pd.read_excel(INPUT_FILE)

    if "Hazardous Waste" not in df.columns:
        raise ValueError(
            "The Excel file must contain a column named 'Hazardous Waste'."
        )

    values = (
        df["Hazardous Waste"]
        .dropna()
        .map(normalize_chemical_name)
    )

    values = [x for x in values if x]

    unique = {}
    for chemical in values:
        key = chemical.casefold()
        if key not in unique:
            unique[key] = chemical

    chemicals = list(unique.values())

    print(f"Unique waste entries found: {len(chemicals)}")

    result = {
        "Flammable": [],
        "Carcinogenic": [],
        "Infectious": [],
        "Toxic": [],
        "Corrosive": [],
    }

    failed = []

    for i, chemical in enumerate(chemicals, start=1):
        print(f"[{i}/{len(chemicals)}] Classifying: {chemical}")

        try:
            classification = classify_chemical(chemical)

            if classification.flammable:
                result["Flammable"].append(chemical)

            if classification.carcinogenic:
                result["Carcinogenic"].append(chemical)

            if classification.infectious:
                result["Infectious"].append(chemical)

            if classification.toxic:
                result["Toxic"].append(chemical)

            if classification.corrosive:
                result["Corrosive"].append(chemical)

            time.sleep(0.2)

        except Exception as e:
            print(f"ERROR for {chemical}: {e}")
            failed.append(chemical)

    max_length = max(
        max((len(v) for v in result.values()), default=0),
        1
    )

    output = {}

    for category, chemicals_list in result.items():
        output[category] = chemicals_list + [
            None
        ] * (max_length - len(chemicals_list))

    output_df = pd.DataFrame(output)

    with pd.ExcelWriter(
        OUTPUT_FILE,
        engine="openpyxl"
    ) as writer:
        output_df.to_excel(
            writer,
            sheet_name="Classification",
            index=False
        )

        if failed:
            pd.DataFrame(
                {"Unclassified": failed}
            ).to_excel(
                writer,
                sheet_name="Review Required",
                index=False
            )

    print()
    print(f"Finished.")
    print(f"Output: {OUTPUT_FILE}")

    for category, items in result.items():
        print(f"{category}: {len(items)}")


if __name__ == "__main__":
    main()