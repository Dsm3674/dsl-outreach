#!/usr/bin/env python3
"""Review your leads one at a time, right in the terminal — no spreadsheet needed.

For each business it opens their website in your browser and asks whether to
pitch them. If you ran scan_websites.py first, the problems it found are shown
too, and the first one is offered as a ready-made personal_note. Answers are
saved into leads.csv immediately, so you can quit any time with q and pick up
where you left off later.

Usage:
    python3 review.py
"""

import csv
import pathlib
import sys
import webbrowser

HERE = pathlib.Path(__file__).parent
LEADS = HERE / "leads.csv"


def save(rows: list[dict], fields: list[str]) -> None:
    with open(LEADS, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if not LEADS.exists():
        sys.exit("leads.csv not found — run find_businesses.py first.")
    with open(LEADS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = reader.fieldnames

    pending = [r for r in rows if not r.get("send", "").strip()]
    if not pending:
        done = sum(1 for r in rows if r.get("send", "").strip().upper() in ("YES", "Y"))
        print(f"All reviewed! {done} businesses are marked to pitch.")
        print('Next: python3 make_drafts.py --name "Your Name" --address "Your address"')
        return

    print(f"{len(pending)} businesses to review. Each website opens in your browser.")
    print("Answers:  y = pitch them   n = no   Enter = decide later   q = save & quit\n")

    for row in rows:
        if row.get("send", "").strip():
            continue  # already decided
        company = row.get("company", "?")
        print("─" * 60)
        print(f"{company}   ({row.get('category', '')})")
        print(f"  website: {row.get('website', '')}")
        print(f"  email:   {row.get('email', '').strip() or '(none found — check their site)'}")
        issues = [p.strip() for p in row.get("site_issues", "").split(";") if p.strip()]
        if issues == ["no obvious problems found"]:
            issues = []
            print("  scan:    no obvious problems found — is a pitch honest here?")
        for issue in issues:
            print(f"  scan:    {issue}")
        webbrowser.open(row.get("website", ""))

        ans = input("Pitch this business? [y/n/Enter/q] ").strip().lower()
        if ans == "q":
            break
        if ans == "n":
            row["send"] = "NO"
        elif ans == "y":
            if not row.get("email", "").strip():
                row["email"] = input("  Their email (from their site; Enter to skip this business): ").strip()
                if not row["email"]:
                    print("  No email — marking as skipped.")
                    row["send"] = "NO"
                    save(rows, fields)
                    continue
            note = row.get("personal_note", "").strip()
            if note:
                print(f"  Current note: {note}")
                new = input("  New note (Enter to keep current): ").strip()
                note = new or note
            suggestion = f"I noticed {issues[0]}." if issues else ""
            while not note:
                if suggestion:
                    note = input(f'  Note about THEIR site (Enter = "{suggestion}"): ').strip() or suggestion
                else:
                    note = input("  One honest sentence about THEIR website: ").strip()
            row["personal_note"] = note
            row["send"] = "YES"
            print(f"  ✓ {company} will get a draft.")
        # Enter/anything else: leave undecided for next time
        save(rows, fields)

    save(rows, fields)
    yes = sum(1 for r in rows if r.get("send", "").strip().upper() in ("YES", "Y"))
    left = sum(1 for r in rows if not r.get("send", "").strip())
    print("─" * 60)
    print(f"Saved. {yes} businesses marked to pitch, {left} still undecided.")
    if yes:
        print('Next: python3 make_drafts.py --name "Your Name" --address "Your street, City, TX ZIP"')
    if left:
        print("Run python3 review.py again anytime to continue where you left off.")


if __name__ == "__main__":
    main()
