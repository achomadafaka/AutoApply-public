import argparse
import json
import sys
from urllib.error import URLError, HTTPError
from urllib.request import urlopen, Request


def fetch_json(url: str) -> tuple[int, str]:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=5) as resp:
        return resp.status, resp.read().decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="API smoke test")
    parser.add_argument("--base", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()

    endpoints = ["/health", "/v1/settings", "/v1/jobs?limit=1", "/v1/ai/health"]

    for path in endpoints:
        url = f"{args.base}{path}"
        try:
            status, body = fetch_json(url)
        except (URLError, HTTPError) as exc:
            print(f"[FAIL] {url} -> {exc}")
            return 1

        if status != 200:
            print(f"[FAIL] {url} -> status {status}")
            return 1
        if path == "/v1/ai/health":
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                print(f"[FAIL] {url} -> invalid JSON")
                return 1
            if data.get("status") not in {"ok", "unavailable"}:
                print(f"[FAIL] {url} -> unexpected status {data.get('status')}")
                return 1
        print(f"[OK]   {url}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
