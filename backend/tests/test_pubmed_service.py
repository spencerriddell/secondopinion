import asyncio

from app.services.pubmed_service import PubMedService


class _MockResponse:
    def __init__(self, json_data=None, text_data: str = "") -> None:
        self._json_data = json_data or {}
        self._text_data = text_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def raise_for_status(self) -> None:
        return None

    async def json(self):
        return self._json_data

    async def text(self) -> str:
        return self._text_data


class _MockSession:
    def __init__(self, responses: list[_MockResponse], seen_urls: list[str]) -> None:
        self._responses = responses
        self._seen_urls = seen_urls

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def get(self, url: str, timeout: int = 20):
        self._seen_urls.append(url)
        return self._responses.pop(0)


def _sample_pubmed_xml() -> str:
    return """
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>12345</PMID>
          <Article>
            <ArticleTitle>Sample Trial</ArticleTitle>
            <Abstract><AbstractText>Sample abstract</AbstractText></Abstract>
          </Article>
        </MedlineCitation>
      </PubmedArticle>
    </PubmedArticleSet>
    """


def test_pubmed_service_defaults_to_three_results_and_adds_api_key(monkeypatch):
    seen_urls: list[str] = []
    responses = [
        _MockResponse(json_data={"esearchresult": {"idlist": ["12345"]}}),
        _MockResponse(text_data=_sample_pubmed_xml()),
    ]
    monkeypatch.setattr(
        "app.services.pubmed_service.aiohttp.ClientSession",
        lambda: _MockSession(responses, seen_urls),
    )
    PubMedService._next_request_time = 0.0

    service = PubMedService(email="swr2118@cumc.columbia.edu", api_key="test-api-key")
    articles = asyncio.run(service.search("egfr"))

    assert len(articles) == 1
    assert "retmax=3" in seen_urls[0]
    assert "api_key=test-api-key" in seen_urls[0]
    assert "api_key=test-api-key" in seen_urls[1]


def test_pubmed_service_rate_limits_requests(monkeypatch):
    seen_urls: list[str] = []
    responses = [
        _MockResponse(json_data={"esearchresult": {"idlist": ["12345"]}}),
        _MockResponse(text_data=_sample_pubmed_xml()),
    ]
    sleep_calls: list[float] = []

    async def _fake_sleep(duration: float) -> None:
        sleep_calls.append(duration)

    monkeypatch.setattr(
        "app.services.pubmed_service.aiohttp.ClientSession",
        lambda: _MockSession(responses, seen_urls),
    )
    monkeypatch.setattr("app.services.pubmed_service.time.monotonic", lambda: 100.0)
    monkeypatch.setattr("app.services.pubmed_service.asyncio.sleep", _fake_sleep)
    PubMedService._next_request_time = 0.0

    service = PubMedService(email="swr2118@cumc.columbia.edu")
    asyncio.run(service.search("nsclc"))

    assert len(seen_urls) == 2
    assert sleep_calls == [1.0]
