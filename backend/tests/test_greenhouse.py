from app.automation.greenhouse import parse_greenhouse_job_url


def test_parse_greenhouse_job_url_path():
    parsed = parse_greenhouse_job_url(
        "https://boards.greenhouse.io/acme/jobs/12345"
    )
    assert parsed is not None
    assert parsed.board_token == "acme"
    assert parsed.job_id == 12345


def test_parse_greenhouse_job_url_query():
    parsed = parse_greenhouse_job_url(
        "https://boards.greenhouse.io/acme?gh_jid=999"
    )
    assert parsed is not None
    assert parsed.board_token == "acme"
    assert parsed.job_id == 999


def test_parse_greenhouse_job_url_embed():
    parsed = parse_greenhouse_job_url(
        "https://boards.greenhouse.io/embed/job_app?for=acme&token=888"
    )
    assert parsed is not None
    assert parsed.board_token == "acme"
    assert parsed.job_id == 888


def test_parse_greenhouse_job_url_custom_domain():
    parsed = parse_greenhouse_job_url(
        "https://careers.example.com/jobs?gh_jid=777"
    )
    assert parsed is not None
    assert parsed.board_token is None
    assert parsed.job_id == 777
