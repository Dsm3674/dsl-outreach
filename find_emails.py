#!/usr/bin/env python3
"""Fill in missing emails in leads.csv by checking each business's own website.

For every row with an empty 'email', this fetches the site's homepage and its
contact/about page (2 pages max per site) and looks for the email address the
business publishes there. Your other edits (personal_note, send, deleted rows)
are preserved.

Usage:
    python3 find_emails.py
"""

import csv
import html
import pathlib
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).parent
LEADS = HERE / "leads.csv"
USER_AGENT = "Mozilla/5.0 (compatible; DSL-Development-contact-finder/1.0)"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
# "info [at] business [dot] com" style obfuscation
OBFUSCATED_RE = re.compile(
    r"([A-Za-z0-9._%+-]+)\s*[\[(]\s*at\s*[\])]\s*([A-Za-z0-9-]+(?:\s*[\[(]\s*dot\s*[\])]\s*[A-Za-z0-9-]+)+)",
    re.IGNORECASE,
)
CONTACT_LINK_RE = re.compile(r'href=["\']([^"\'#]*(?:contact|about|kontakt)[^"\'#]*)["\']', re.IGNORECASE)

# Addresses that are never a real inbox for the business.
JUNK_PARTS = (
    "example.", "sentry", "wixpress", "godaddy", "no-reply", "noreply",
    "donotreply", "@2x", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    "your@", "@email", "@domain", "@yourdomain", "u003e",
)


def fetch(url: str) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False  # small-business sites often have sloppy certs
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        if "text/html" not in resp.headers.get("Content-Type", "text/html"):
            return ""
        return resp.read(1_500_000).decode("utf-8", errors="replace")


def emails_in(page: str) -> list[str]:
    page = html.unescape(page)
    found = []
    # mailto: links are the most reliable signal
    for m in re.finditer(r'mailto:([^"\'?>\s]+)', page, re.IGNORECASE):
        found.append(urllib.parse.unquote(m.group(1)).strip().rstrip("."))
    found.extend(m.group(0) for m in EMAIL_RE.finditer(page))
    for m in OBFUSCATED_RE.finditer(page):
        domain = re.sub(r"\s*[\[(]\s*dot\s*[\])]\s*", ".", m.group(2))
        found.append(f"{m.group(1)}@{domain}")
    cleaned = []
    for e in found:
        e = e.strip().strip(".,;:").lower()
        if EMAIL_RE.fullmatch(e) and not any(j in e for j in JUNK_PARTS):
            cleaned.append(e)
    return cleaned


def best_email(candidates: list[str], site_domain: str) -> str:
    if not candidates:
        return ""
    site_domain = site_domain.lower().removeprefix("www.")

    def score(e: str) -> tuple:
        local, _, domain = e.partition("@")
        return (
            domain == site_domain or domain.endswith("." + site_domain),
            local in ("info", "contact", "hello", "office", "sales", "admin"),
            -candidates.index(e),
        )

    return max(dict.fromkeys(candidates), key=score)


def contact_page_url(page: str, base_url: str) -> str:
    m = CONTACT_LINK_RE.search(page)
    return urllib.parse.urljoin(base_url, m.group(1)) if m else ""


def find_site_email(website: str) -> str:
    if not website.startswith(("http://", "https://")):
        website = "https://" + website
    domain = urllib.parse.urlparse(website).netloc
    candidates = []
    try:
        home = fetch(website)
    except Exception as e:
        print(f"    couldn't load site ({type(e).__name__})")
        return ""
    candidates += emails_in(home)
    if not candidates:
        contact_url = contact_page_url(home, website)
        if contact_url:
            try:
                candidates += emails_in(fetch(contact_url))
            except Exception:
                pass
    return best_email(candidates, domain)


def main() -> None:
    if not LEADS.exists():
        sys.exit("leads.csv not found — run find_businesses.py first.")
    with open(LEADS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = reader.fieldnames

    todo = [r for r in rows if r.get("website") and not r.get("email", "").strip()]
    print(f"{len(todo)} of {len(rows)} businesses are missing an email. Checking their websites...\n")

    found = 0
    for i, row in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {row.get('company', '?')}")
        email = find_site_email(row["website"].strip())
        if email:
            row["email"] = email
            found += 1
            print(f"    found: {email}")
        else:
            print("    no email published on the site")
        time.sleep(1)  # be polite: one site per second

    with open(LEADS, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone: found emails for {found} more businesses. leads.csv updated.")
    print("Rows it couldn't fill either don't publish an email (use their contact")
    print("form instead) or blocked the request — spot-check a few by hand.")


if __name__ == "__main__":
    main()
