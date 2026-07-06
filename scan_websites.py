#!/usr/bin/env python3
"""Scan each lead's website and note concrete things DSL could improve.

For every business in leads.csv this visits their homepage and checks for the
problems a $700 redesign actually fixes: not phone-friendly, no HTTPS, slow to
load, missing the basics Google looks for, stale copyright years, dead tech
like Flash or frames. Findings land in a new 'site_issues' column, phrased so
they can drop straight into the email ("I noticed ..."). review.py shows them
and offers the first one as a ready-made personal_note.

Only rows you haven't rejected are scanned, one site per second. Rows that
already have site_issues are skipped so re-runs are cheap; use --refresh to
re-scan everything.

Usage:
    python3 scan_websites.py
    python3 scan_websites.py --refresh
"""

import argparse
import csv
import pathlib
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).parent
LEADS = HERE / "leads.csv"
USER_AGENT = "Mozilla/5.0 (compatible; DSL-Development-site-checker/1.0)"

NO_ISSUES = "no obvious problems found"
SLOW_SECONDS = 5
CURRENT_YEAR = time.localtime().tm_year


def fetch(url: str, verify: bool) -> tuple[str, str]:
    """Return (page_html, final_url_after_redirects)."""
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
        return resp.read(1_500_000).decode("utf-8", errors="replace"), resp.geturl()


def load_page(url: str) -> tuple[str, str, list[str]]:
    """Fetch the homepage, downgrading gracefully. Returns (page, final_url, issues)."""
    try:
        page, final = fetch(url, verify=True)
        return page, final, []
    except urllib.error.URLError as e:
        if isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError):
            # Real cert problem — visitors see a browser security warning.
            page, final = fetch(url, verify=False)
            return page, final, [
                "the site's HTTPS certificate is broken, so browsers show visitors a security warning"
            ]
        raise


def html_issues(page: str, final_url: str) -> list[str]:
    """Checks on the homepage HTML, phrased to read naturally after 'I noticed ...'."""
    issues = []
    low = page.lower()

    if not re.search(r'<meta[^>]+name=["\']?viewport', low):
        issues.append(
            "the site isn't set up for phones (no mobile viewport), so it's hard to use on a phone screen"
        )
    if ".swf" in low or "<frameset" in low:
        issues.append("the site is built on outdated technology (Flash/frames) that modern browsers no longer support")
    if final_url.startswith("https://") and re.search(r'src=["\']http://', low):
        issues.append("the page loads some images/scripts insecurely, which browsers block or flag as unsafe")

    years = []
    for m in re.finditer(
        r"(?:©|&copy;|copyright)[^<>\d]{0,20}((?:19|20)\d{2})(?:\s*[-–]\s*((?:19|20)\d{2}))?",
        page, re.IGNORECASE,
    ):
        years.extend(int(y) for y in m.groups() if y)
    if years and max(years) < CURRENT_YEAR - 1:
        issues.append(f"the footer copyright still says {max(years)}, which makes the business look inactive")

    title = re.search(r"<title[^>]*>\s*(.*?)\s*</title>", page, re.IGNORECASE | re.DOTALL)
    if not title or not title.group(1).strip():
        issues.append("the page is missing a title tag, which hurts how it shows up on Google")
    if not re.search(r'<meta[^>]+name=["\']?description', low):
        issues.append("there's no meta description, so Google invents its own snippet for the site")
    if not re.search(r"<h1[\s>]", low):
        issues.append("the page has no main heading (h1), one of the basics Google looks for")

    imgs = re.findall(r"<img\b[^>]*>", low)
    if len(imgs) >= 3 and sum("alt=" not in i for i in imgs) > len(imgs) // 2:
        issues.append("most images are missing alt text, which hurts both Google ranking and accessibility")

    return issues


def scan(website: str) -> list[str]:
    if not website.startswith(("http://", "https://")):
        website = "https://" + website

    start = time.monotonic()
    try:
        page, final_url, issues = load_page(website)
    except Exception:
        # https dead? Some old sites only answer on plain http.
        if website.startswith("https://"):
            try:
                page, final_url, issues = load_page("http://" + website.removeprefix("https://"))
            except Exception:
                return ["the website didn't load at all when I visited"]
        else:
            return ["the website didn't load at all when I visited"]
    elapsed = time.monotonic() - start

    if final_url.startswith("http://"):
        issues.insert(0, "the site doesn't use a secure HTTPS connection, so browsers label it 'Not Secure'")
    if elapsed > SLOW_SECONDS:
        issues.append(f"the homepage took about {elapsed:.0f} seconds to load")

    # Mobile/security problems first — they make the strongest opening line.
    return (issues + html_issues(page, final_url))[:5]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh", action="store_true",
                    help="re-scan sites that already have site_issues filled in")
    args = ap.parse_args()

    if not LEADS.exists():
        sys.exit("leads.csv not found — run find_businesses.py first.")
    with open(LEADS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames or [])

    if "site_issues" not in fields:
        fields.insert(fields.index("personal_note") if "personal_note" in fields else len(fields),
                      "site_issues")
    for r in rows:
        r.setdefault("site_issues", "")

    def save() -> None:
        with open(LEADS, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    todo = [
        r for r in rows
        if r.get("website", "").strip()
        and r.get("send", "").strip().upper() != "NO"
        and (args.refresh or not r.get("site_issues", "").strip())
    ]
    if not todo:
        save()
        sys.exit("Nothing to scan — every lead already has site_issues (use --refresh to re-scan).")

    print(f"Scanning {len(todo)} websites for things DSL could improve...\n")
    found = 0
    for i, row in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {row.get('company', '?')}")
        issues = scan(row["website"].strip())
        if issues:
            row["site_issues"] = "; ".join(issues)
            found += 1
            for issue in issues:
                print(f"    - {issue}")
        else:
            row["site_issues"] = NO_ISSUES
            print(f"    {NO_ISSUES} — maybe not worth pitching")
        save()  # progress survives Ctrl-C
        time.sleep(1)  # be polite: one site per second

    print(f"\nDone: found improvable problems on {found} of {len(todo)} sites. leads.csv updated.")
    print("Next: python3 review.py — it shows each site's issues and offers them as")
    print("the personal_note, so writing the honest sentence takes one keypress.")


if __name__ == "__main__":
    main()
