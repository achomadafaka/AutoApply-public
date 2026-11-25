import argparse
import sys
from urllib.error import URLError, HTTPError
from urllib.request import urlopen, Request


def fetch_text(url: str) -> tuple[int, str]:
    req = Request(url, headers={"Accept": "text/html"})
    with urlopen(req, timeout=5) as resp:
        return resp.status, resp.read().decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Frontend smoke test")
    parser.add_argument("--base", default="http://localhost:5173", help="UI base URL")
    args = parser.parse_args()

    url = args.base.rstrip("/") + "/"
    try:
        status, body = fetch_text(url)
    except (URLError, HTTPError) as exc:
        print(f"[FAIL] {url} -> {exc}")
        return 1

    if status != 200:
        print(f"[FAIL] {url} -> status {status}")
        return 1

    # SvelteKit dev server should include sveltekit markers.
    if "data-sveltekit" not in body and "sveltekit" not in body:
        print(f"[FAIL] {url} -> unexpected response body")
        return 1

    print(f"[OK]   {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
