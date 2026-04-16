from app.services.pmc_service import PMCService


def test_pmc_service_extracts_full_text_sections():
    service = PMCService(email="test@example.com")
    xml = """
    <article>
      <body>
        <sec><title>Methods</title><p>Randomized controlled trial in stage IV NSCLC.</p></sec>
        <sec><title>Results</title><p>Improved progression-free survival with treatment.</p></sec>
        <sec><title>Conclusions</title><p>Therapy improved outcomes with manageable toxicity.</p></sec>
      </body>
    </article>
    """
    methodology, results, conclusions = service._extract_sections(xml)
    assert methodology and "Randomized" in methodology
    assert results and "progression-free survival" in results
    assert conclusions and "improved outcomes" in conclusions
