import time
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import aiohttp

from app.models.evidence import PubMedArticle


class PubMedService:
    def __init__(self, email: str, ttl_seconds: int = 600) -> None:
        self.email = email
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[float, list[PubMedArticle]]] = {}

    async def search(self, query: str, max_results: int = 5) -> list[PubMedArticle]:
        cache_hit = self._cache.get(query)
        if cache_hit and (time.time() - cache_hit[0] < self.ttl_seconds):
            return cache_hit[1]

        term = quote_plus(f"{query} oncology")
        search_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pubmed&retmode=json&retmax={max_results}&term={term}&email={quote_plus(self.email)}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, timeout=20) as response:
                response.raise_for_status()
                body = await response.json()

            ids = body.get("esearchresult", {}).get("idlist", [])
            if not ids:
                self._cache[query] = (time.time(), [])
                return []

            id_csv = ",".join(ids)
            fetch_url = (
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
                f"?db=pubmed&id={id_csv}&retmode=xml&email={quote_plus(self.email)}"
            )
            async with session.get(fetch_url, timeout=20) as response:
                response.raise_for_status()
                xml_text = await response.text()

        articles = self._parse_xml(xml_text)
        self._cache[query] = (time.time(), articles)
        return articles

    async def fetch_by_pmid(self, pmid: str) -> PubMedArticle | None:
        results = await self.search(pmid, max_results=1)
        return results[0] if results else None

    def _parse_xml(self, xml_text: str) -> list[PubMedArticle]:
        root = ET.fromstring(xml_text)
        records: list[PubMedArticle] = []

        for article in root.findall(".//PubmedArticle"):
            pmid = article.findtext(".//PMID", default="")
            title = article.findtext(".//ArticleTitle", default="Untitled")
            abstract = " ".join(
                node.text or "" for node in article.findall(".//Abstract/AbstractText")
            ).strip() or None
            journal = article.findtext(".//Journal/Title")
            year_raw = article.findtext(".//PubDate/Year")
            doi = None
            for aid in article.findall(".//ArticleId"):
                if aid.attrib.get("IdType") == "doi":
                    doi = aid.text
            authors = []
            for author in article.findall(".//Author"):
                last = author.findtext("LastName")
                initials = author.findtext("Initials")
                if last:
                    authors.append(f"{last} {initials or ''}".strip())

            mesh_terms = [m.text for m in article.findall(".//MeshHeading/DescriptorName") if m.text]
            records.append(
                PubMedArticle(
                    pmid=pmid,
                    doi=doi,
                    title=title,
                    authors=authors,
                    journal=journal,
                    year=int(year_raw) if year_raw and year_raw.isdigit() else None,
                    abstract=abstract,
                    mesh_terms=mesh_terms,
                )
            )

        return records
