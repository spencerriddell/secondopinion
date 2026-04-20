import asyncio

import pytest

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


@pytest.fixture(autouse=True)
def reset_pubmed_rate_limit_state():
    PubMedService._request_lock = None
    PubMedService._request_lock_loop = None
    PubMedService._next_request_time = 0.0
    yield
    PubMedService._request_lock = None
    PubMedService._request_lock_loop = None
    PubMedService._next_request_time = 0.0


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

    service = PubMedService(email="test@example.com", api_key="test-api-key")
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
    recorded_sleep_durations: list[float] = []
    # Two initial 100.0 values model back-to-back request timestamps; later values advance time.
    monotonic_values = iter([100.0, 100.0, 100.5, 101.0, 101.5])

    def _fake_monotonic() -> float:
        return next(monotonic_values, 102.0)

    async def _fake_sleep(duration: float) -> None:
        recorded_sleep_durations.append(duration)

    monkeypatch.setattr(
        "app.services.pubmed_service.aiohttp.ClientSession",
        lambda: _MockSession(responses, seen_urls),
    )
    monkeypatch.setattr("app.services.pubmed_service.time.monotonic", _fake_monotonic)
    monkeypatch.setattr("app.services.pubmed_service.asyncio.sleep", _fake_sleep)

    service = PubMedService(email="test@example.com")
    asyncio.run(service.search("nsclc"))

    assert len(seen_urls) == 2
    assert len(recorded_sleep_durations) == 1
    assert 0 < recorded_sleep_durations[0] <= PubMedService.REQUEST_INTERVAL_SECONDS
