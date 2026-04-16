from app.models.evidence import GuidelineReference


class GuidelineService:
    def __init__(self) -> None:
        self._guidelines = [
            GuidelineReference(
                organization="NCCN",
                cancer_type="NSCLC",
                treatment="Pembrolizumab + platinum doublet",
                version="2026.1",
                last_updated="2026-01-15",
            ),
            GuidelineReference(
                organization="ESMO",
                cancer_type="breast",
                treatment="Trastuzumab + pertuzumab + taxane",
                version="2025.4",
                last_updated="2025-11-10",
            ),
            GuidelineReference(
                organization="ASCO",
                cancer_type="colorectal",
                treatment="Pembrolizumab for MSI-H/dMMR metastatic disease",
                version="2025.3",
                last_updated="2025-09-01",
            ),
        ]

    def search(self, cancer_type: str | None = None, treatment: str | None = None) -> list[GuidelineReference]:
        results = self._guidelines
        if cancer_type:
            results = [g for g in results if g.cancer_type.lower() == cancer_type.lower()]
        if treatment:
            needle = treatment.lower()
            results = [g for g in results if needle in g.treatment.lower()]
        return results
