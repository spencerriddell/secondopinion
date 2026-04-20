import asyncio
import threading
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import aiohttp

from app.models.evidence import PubMedArticle


class PubMedService:
    REQUEST_INTERVAL_SECONDS = 1.0
    _request_lock_init_guard = threading.Lock()
    _request_lock: asyncio.Lock | None = None
    _request_lock_loop: asyncio.AbstractEventLoop | None = None
    _next_request_time = 0.0

    def __init__(self, email: str, api_key: str | None = None, ttl_seconds: int = 600) -> None:
        self.email = email
        self.api_key = api_key
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[float, list[PubMedArticle]]] = {}

    async def search(self, query: str, max_results: int = 3) -> list[PubMedArticle]:
        cache_hit = self._cache.get(query)
        if cache_hit and (time.time() - cache_hit[0] < self.ttl_seconds):
            return cache_hit[1]

        api_key_param = f"&api_key={quote_plus(self.api_key)}" if self.api_key else ""
        term = quote_plus(f"{query} oncology")
        search_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pubmed&retmode=json&retmax={max_results}&term={term}&email={quote_plus(self.email)}{api_key_param}"
        )

        async with aiohttp.ClientSession() as session:
            body = await self._rate_limited_get_json(session, search_url)

            ids = body.get("esearchresult", {}).get("idlist", [])
            if not ids:
                self._cache[query] = (time.time(), [])
                return []

            id_csv = ",".join(ids)
            fetch_url = (
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
                f"?db=pubmed&id={id_csv}&retmode=xml&email={quote_plus(self.email)}{api_key_param}"
            )
            xml_text = await self._rate_limited_get_text(session, fetch_url)

        articles = self._parse_xml(xml_text)
        self._cache[query] = (time.time(), articles)
        return articles

    async def fetch_by_pmid(self, pmid: str) -> PubMedArticle | None:
        results = await self.search(pmid, max_results=1)
        return results[0] if results else None

    async def _rate_limited_get_json(self, session: aiohttp.ClientSession, url: str) -> dict:
        await self._wait_for_rate_limit()
        async with session.get(url, timeout=20) as response:
            response.raise_for_status()
            return await response.json()

    async def _rate_limited_get_text(self, session: aiohttp.ClientSession, url: str) -> str:
        await self._wait_for_rate_limit()
        async with session.get(url, timeout=20) as response:
            response.raise_for_status()
            return await response.text()

    async def _wait_for_rate_limit(self) -> None:
        request_lock = self._get_request_lock()
        wait_seconds = 0.0
        async with request_lock:
            now = time.monotonic()
            scheduled_at = max(now, self.__class__._next_request_time)
            self.__class__._next_request_time = (
                scheduled_at + self.__class__.REQUEST_INTERVAL_SECONDS
            )
            wait_seconds = scheduled_at - now

        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

    @classmethod
    def _get_request_lock(cls) -> asyncio.Lock:
        running_loop = asyncio.get_running_loop()
        with cls._request_lock_init_guard:
            if cls._request_lock is None or cls._request_lock_loop is not running_loop:
                cls._request_lock = asyncio.Lock()
                cls._request_lock_loop = running_loop
        return cls._request_lock

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
