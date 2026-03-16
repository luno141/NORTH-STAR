from __future__ import annotations

import argparse
import csv
import io
from datetime import datetime, timedelta, timezone
import time
from typing import Iterable

import requests

OPENPHISH_FEED = "https://openphish.com/feed.txt"
URLHAUS_RECENT = "https://urlhaus.abuse.ch/downloads/csv_recent/"
DEFAULT_RSS = [
    "https://www.cisa.gov/uscert/ncas/current-activity.xml",
    "https://www.kb.cert.org/vuls/rss",
]


def _csv_payload(rows: Iterable[dict[str, str]]) -> tuple[str, bytes]:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "indicator_type",
            "value",
            "tags",
            "timestamp",
            "confidence",
            "context_text",
            "evidence",
        ],
    )
    writer.writeheader()
    count = 0
    for row in rows:
        writer.writerow(row)
        count += 1
    return f"generated_{count}.csv", buf.getvalue().encode("utf-8")


def fetch_openphish(max_rows: int) -> list[dict[str, str]]:
    resp = requests.get(OPENPHISH_FEED, timeout=60)
    resp.raise_for_status()

    rows: list[dict[str, str]] = []
    fetched_at = datetime.now(timezone.utc)
    for idx, line in enumerate(resp.text.splitlines()):
        url = line.strip()
        if not url:
            continue
        rows.append(
            {
                "indicator_type": "url",
                "value": url,
                "tags": "phishing,openphish,real",
                "timestamp": (fetched_at - timedelta(seconds=idx)).isoformat().replace("+00:00", "Z"),
                "confidence": "84",
                "context_text": "OpenPhish live feed indicator",
                "evidence": "source=openphish_feed",
            }
        )
        if len(rows) >= max_rows:
            break
    return rows


def fetch_urlhaus(max_rows: int) -> list[dict[str, str]]:
    resp = requests.get(URLHAUS_RECENT, timeout=60)
    resp.raise_for_status()

    clean_lines = [line for line in resp.text.splitlines() if line and not line.startswith("#")]
    reader = csv.reader(io.StringIO("\n".join(clean_lines)))

    rows: list[dict[str, str]] = []
    for raw in reader:
        if len(raw) < 3:
            continue
        date_added = raw[1].strip() if len(raw) > 1 else ""
        url = raw[2].strip()
        threat = raw[5].strip().lower() if len(raw) > 5 else "malware_download"
        tags = raw[6].strip() if len(raw) > 6 else "malware,urlhaus"
        link = raw[7].strip() if len(raw) > 7 else "source=urlhaus"
        if not url:
            continue

        timestamp = date_added
        try:
            if date_added:
                timestamp = datetime.strptime(date_added, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        rows.append(
            {
                "indicator_type": "url",
                "value": url,
                "tags": f"{tags},urlhaus,real",
                "timestamp": timestamp,
                "confidence": "88",
                "context_text": f"URLhaus threat={threat}",
                "evidence": link,
            }
        )
        if len(rows) >= max_rows:
            break
    return rows


def post_csv(api_base: str, api_key: str, rows: list[dict[str, str]], label: str) -> None:
    filename, payload = _csv_payload(rows)
    last_exc: Exception | None = None
    for attempt in range(1, 6):
        try:
            resp = requests.post(
                f"{api_base.rstrip('/')}/api/ingest/csv",
                headers={"X-API-Key": api_key},
                files={"file": (filename, payload, "text/csv")},
                timeout=120,
            )
            print(f"[{label}] status={resp.status_code} body={resp.text}")
            resp.raise_for_status()
            return
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == 5:
                break
            wait_s = attempt * 2
            print(f"[{label}] request failed (attempt {attempt}/5), retrying in {wait_s}s...")
            time.sleep(wait_s)
    if last_exc:
        raise last_exc


def post_rss(api_base: str, api_key: str, rss_urls: list[str]) -> None:
    params: list[tuple[str, str]] = [("urls", u) for u in rss_urls]
    last_exc: Exception | None = None
    for attempt in range(1, 6):
        try:
            resp = requests.post(
                f"{api_base.rstrip('/')}/api/ingest/rss",
                headers={"X-API-Key": api_key},
                params=params,
                timeout=120,
            )
            print(f"[rss] status={resp.status_code} body={resp.text}")
            resp.raise_for_status()
            return
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == 5:
                break
            wait_s = attempt * 2
            print(f"[rss] request failed (attempt {attempt}/5), retrying in {wait_s}s...")
            time.sleep(wait_s)
    if last_exc:
        raise last_exc


def wait_for_backend(api_base: str, timeout_seconds: int = 120) -> None:
    deadline = time.time() + timeout_seconds
    health_url = f"{api_base.rstrip('/')}/api/health"
    while time.time() < deadline:
        try:
            resp = requests.get(health_url, timeout=5)
            if resp.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise RuntimeError(f"Backend health check did not pass within {timeout_seconds}s: {health_url}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest real threat intel feeds into PS13 backend")
    parser.add_argument("--api-base", default="http://backend:8000")
    parser.add_argument("--api-key", default="carl_contrib_key")
    parser.add_argument("--max-openphish", type=int, default=1500)
    parser.add_argument("--max-urlhaus", type=int, default=1500)
    parser.add_argument("--skip-rss", action="store_true")
    parser.add_argument("--wait-seconds", type=int, default=120)
    args = parser.parse_args()

    print("Waiting for backend health...")
    wait_for_backend(args.api_base, timeout_seconds=args.wait_seconds)

    print("Fetching OpenPhish...")
    openphish_rows = fetch_openphish(args.max_openphish)
    print(f"OpenPhish rows: {len(openphish_rows)}")

    print("Fetching URLhaus...")
    urlhaus_rows = fetch_urlhaus(args.max_urlhaus)
    print(f"URLhaus rows: {len(urlhaus_rows)}")

    if openphish_rows:
        post_csv(args.api_base, args.api_key, openphish_rows, "openphish")
    if urlhaus_rows:
        post_csv(args.api_base, args.api_key, urlhaus_rows, "urlhaus")
    if not args.skip_rss:
        post_rss(args.api_base, args.api_key, DEFAULT_RSS)

    print("Real feed ingestion finished.")


if __name__ == "__main__":
    main()
