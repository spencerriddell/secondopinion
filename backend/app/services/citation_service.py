from app.models.recommendation import Citation


class CitationService:
    def format_citation(self, citation: Citation, style: str = "Vancouver") -> str:
        authors = ", ".join(citation.authors)
        year = citation.year or "n.d."
        journal = citation.journal or "Unknown Journal"

        if style.upper() == "APA":
            return f"{authors} ({year}). {citation.title}. {journal}. doi:{citation.doi or 'N/A'}"
        if style.upper() == "MLA":
            return f"{authors}. \"{citation.title}.\" {journal}, {year}. DOI: {citation.doi or 'N/A'}."
        if style.upper() == "BIBTEX":
            key = f"pmid{citation.pmid}"
            return (
                f"@article{{{key}, title={{ {citation.title} }}, author={{ {authors} }}, "
                f"journal={{ {journal} }}, year={{ {year} }}, doi={{ {citation.doi or ''} }} }}"
            )
        return f"{authors}. {citation.title}. {journal}. {year}. PMID:{citation.pmid}."

    def bibliography(self, citations: list[Citation], style: str = "Vancouver") -> list[str]:
        return [self.format_citation(c, style=style) for c in citations]
