from app.automation.lever import parse_lever_job_url


def test_parse_lever_job_url_global():
    parsed = parse_lever_job_url("https://jobs.lever.co/acme/abcd1234")
    assert parsed is not None
    assert parsed.site == "acme"
    assert parsed.posting_id == "abcd1234"
    assert parsed.region == "global"


def test_parse_lever_job_url_eu():
    parsed = parse_lever_job_url("https://jobs.eu.lever.co/acme/abcd1234")
    assert parsed is not None
    assert parsed.site == "acme"
    assert parsed.posting_id == "abcd1234"
    assert parsed.region == "eu"


def test_parse_lever_job_url_api():
    parsed = parse_lever_job_url("https://api.lever.co/v0/postings/acme/abcd1234")
    assert parsed is not None
    assert parsed.site == "acme"
    assert parsed.posting_id == "abcd1234"
    assert parsed.region == "global"
