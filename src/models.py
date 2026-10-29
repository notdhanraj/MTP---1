from pydantic import BaseModel, Field, model_validator


class WasteManagementDossier(BaseModel):
    chemical: str
    bin: str = ""
    segregation_bin: str = ""
    categories: list[str] = Field(default_factory=list)
    flammable: bool = False
    carcinogenic: bool = False
    infectious: bool = False
    toxic: bool = False
    corrosive: bool = False
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

    @model_validator(mode="after")
    def _sync_fields(self) -> "WasteManagementDossier":
        if self.segregation_bin and not self.bin:
            self.bin = self.segregation_bin
        elif self.bin and not self.segregation_bin:
            self.segregation_bin = self.bin

        for cat in self.categories:
            cat_l = cat.lower()
            if hasattr(self, cat_l):
                setattr(self, cat_l, True)

        for flag in ["flammable", "carcinogenic", "infectious", "toxic", "corrosive"]:
            if getattr(self, flag, False) and flag.capitalize() not in self.categories:
                self.categories.append(flag.capitalize())

        return self

    @property
    def recommended_container(self) -> str:
        return self.container


class BatchRunResponse(BaseModel):
    run_id: str
    filename: str
    total_count: int
    bin_counts: dict[str, int] = Field(default_factory=dict)
    items: list[WasteManagementDossier] = Field(default_factory=list)


class BatchQueuedResponse(BaseModel):
    run_id: str
    filename: str
    total_count: int
    chemicals: list[str]
    pause_after_classification: bool = False
    status: str = "queued"


class RetryItemRequest(BaseModel):
    original_name: str
    new_name: str


class RetryItemResponse(BaseModel):
    status: str = "success"
    chemical: str
    original_name: str
    dossier: WasteManagementDossier
    bin_counts: dict[str, int]


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
