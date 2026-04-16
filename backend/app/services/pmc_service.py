import time
from datetime import datetime
from urllib.parse import quote_plus

import aiohttp
import feedparser
from lxml import etree

from app.models.pmc import PMCArticle


class PMCService:
    # Keep extracted sections concise for prompt construction and payload size control.
    SECTION_TEXT_LIMIT = 1500

    def __init__(self, email: str, batch_size: int = 5, ttl_seconds: int = 600) -> None:
        self.email = email
        self.batch_size = batch_size
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[float, list[PMCArticle]]] = {}

    async def search(self, query: str, date_from: str | None = None, max_results: int = 10) -> list[PMCArticle]:
        limit = min(max_results, self.batch_size)
        cache_key = f"{query}:{date_from}:{limit}"
        cache_hit = self._cache.get(cache_key)
        if cache_hit and (time.time() - cache_hit[0] < self.ttl_seconds):
            return cache_hit[1]

        date_filter = ""
        if date_from:
            date_filter = f"+AND+{quote_plus(date_from)}[dp]"
        term = quote_plus(f"{query} open access[filter]") + date_filter
        search_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pmc&retmode=json&retmax={limit}&term={term}&email={quote_plus(self.email)}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, timeout=20) as response:
                response.raise_for_status()
                body = await response.json()

            pmc_ids = body.get("esearchresult", {}).get("idlist", [])
            if not pmc_ids:
                self._cache[cache_key] = (time.time(), [])
                return []

            records: list[PMCArticle] = []
            for pmc_id in pmc_ids[:limit]:
                metadata = await self._fetch_oai_metadata(session, pmc_id)
                full_text = await self.fetch_full_text(pmc_id, session=session)
                methodology, results, conclusions = self._extract_sections(full_text)
                records.append(
                    PMCArticle(
                        pmc_id=f"PMC{pmc_id}",
                        title=metadata.get("title", f"PMC {pmc_id}"),
                        authors=metadata.get("authors", []),
                        journal=metadata.get("journal"),
                        year=metadata.get("year"),
                        abstract=metadata.get("abstract"),
                        methodology=methodology,
                        results=results,
                        conclusions=conclusions,
                        relevance_score=self._relevance_score(query, full_text, metadata),
                        impact_score=self._impact_score(metadata.get("journal")),
                    )
                )

        self._cache[cache_key] = (time.time(), records)
        return records

    async def fetch_full_text(self, pmc_id: str, session: aiohttp.ClientSession | None = None) -> str:
        normalized = pmc_id if pmc_id.startswith("PMC") else f"PMC{pmc_id}"
        url = f"https://pmc.ncbi.nlm.nih.gov/articles/{normalized}/?format=xml"

        if session:
            async with session.get(url, timeout=20) as response:
                response.raise_for_status()
                return await response.text()

        async with aiohttp.ClientSession() as local_session:
            async with local_session.get(url, timeout=20) as response:
                response.raise_for_status()
                return await response.text()

    async def _fetch_oai_metadata(self, session: aiohttp.ClientSession, pmc_id: str) -> dict:
        oai_url = (
            "https://pmc.ncbi.nlm.nih.gov/tools/oai/oai.cgi"
            f"?verb=GetRecord&identifier=oai:pubmedcentral.nih.gov:{pmc_id}&metadataPrefix=oai_dc"
        )
        async with session.get(oai_url, timeout=20) as response:
            response.raise_for_status()
            body = await response.text()

        parsed = feedparser.parse(body)
        entry = parsed.entries[0] if len(parsed.entries) > 0 else {}
        title = self._first(entry.get("title"))
        authors = entry.get("authors", [])
        if isinstance(authors, list):
            author_names = [a.get("name", "") for a in authors if a.get("name")]
        else:
            author_names = []
        journal = self._first(entry.get("dc_source"))
        abstract = self._first(entry.get("summary"))
        year = self._parse_year(self._first(entry.get("published")))
        return {
            "title": title,
            "authors": author_names,
            "journal": journal,
            "abstract": abstract,
            "year": year,
        }

    def _extract_sections(self, xml_text: str) -> tuple[str | None, str | None, str | None]:
        if not xml_text.strip():
            return None, None, None
        parser = etree.XMLParser(recover=True)
        root = etree.fromstring(xml_text.encode("utf-8"), parser=parser)

        methodology = self._extract_section(root, {"methods", "methodology", "materials and methods"})
        results = self._extract_section(root, {"results"})
        conclusions = self._extract_section(root, {"conclusion", "conclusions", "discussion"})
        return methodology, results, conclusions

    def _extract_section(self, root: etree._Element, names: set[str]) -> str | None:
        for sec in root.xpath(".//*[local-name()='sec']"):
            title = " ".join(sec.xpath("./*[local-name()='title']//text()")).strip().lower()
            if any(name in title for name in names):
                text = " ".join(sec.xpath(".//*[local-name()='p']//text()")).strip()
                if text:
                    return text[: self.SECTION_TEXT_LIMIT]
        return None

    def _relevance_score(self, query: str, full_text: str, metadata: dict) -> float:
        corpus = " ".join(
            [query.lower(), full_text.lower(), str(metadata.get("title", "")).lower(), str(metadata.get("abstract", "")).lower()]
        )
        keywords = [token for token in query.lower().split() if token]
        if not keywords:
            return 0.0
        hits = sum(1 for token in keywords if token in corpus)
        return round(min(1.0, hits / max(1, len(keywords))), 3)

    def _impact_score(self, journal: str | None) -> float:
        if not journal:
            return 0.0
        known_high_impact = {"new england journal of medicine", "lancet", "jama", "nature medicine", "bmj"}
        lower = journal.lower()
        return 1.0 if any(name in lower for name in known_high_impact) else 0.5

    def _first(self, value: list[str] | str | None) -> str | None:
        if isinstance(value, list):
            return value[0] if value else None
        return value

    def _parse_year(self, published: str | None) -> int | None:
        if not published:
            return None
        try:
            return datetime.fromisoformat(published).year
        except ValueError:
            try:
                return datetime.fromisoformat(published.replace("Z", "+00:00")).year
            except ValueError:
                pass
            for token in published.split("-"):
                if token.isdigit() and len(token) == 4:
                    return int(token)
        return None
