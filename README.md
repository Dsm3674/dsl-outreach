# DSL Development — client outreach kit

Finds local businesses that have websites, then generates a personalized email
draft for each one you approve. You review every draft and send it yourself
from your own email — that's what keeps this normal sales outreach instead of
spam, and it's also what gets replies.

No API keys needed. Uses OpenStreetMap's free public business directory.

## 1. Find businesses near you

```bash
python3 find_businesses.py --city "Dallas, TX" --radius 8
```

Creates `leads.csv` with company name, category, website, phone, and (when the
business publishes one) their contact email.

## 2. Auto-fill missing emails

```bash
python3 find_emails.py
```

Visits each business's own website (homepage + contact page, one per second)
and fills the `email` column with the address the business publishes there.
Tip: delete obvious bad-fit rows first so it doesn't waste time on them.
Existing emails and your other edits are never overwritten.

## 3. Scan their websites for problems DSL can fix

```bash
python3 scan_websites.py
```

Visits each lead's homepage (one per second) and fills a `site_issues` column
with concrete, honest problems a redesign fixes: not phone-friendly, no HTTPS,
slow load, broken certificate, stale copyright year, missing the SEO basics,
Flash/frames. Each finding is worded so it drops straight into the email as
"I noticed ...". Re-running only scans new rows; `--refresh` re-scans all.

## 4. Review the leads

```bash
python3 review.py
```

Opens each website in your browser, shows what the scanner found, and offers
the top finding as a ready-made `personal_note` — press Enter to accept it or
type your own sentence. (You can still do this step in Excel/Google Sheets
instead: write the note in `personal_note` and put `YES` in `send`.)

Either way, look at every site yourself before pitching: if it's already
great, or they're a big chain, skip them.

## 5. Generate drafts

```bash
python3 make_drafts.py
```

Drafts are signed as Divyanshu, DSL Development, 7322 Ridgepoint Drive,
Irving, TX 75063, and every draft links https://dsl.homes next to the
Instagram handle so prospects can see the quality of work first-hand.
Override any of these with `--name`, `--address`, or `--website`.

One `.txt` file per approved lead appears in `drafts/`. Read each one, copy it
into Gmail, and send.

## Rules that keep you out of trouble (and out of spam folders)

- **You press send.** Never wire this up to auto-send.
- **Small batches** — a handful a day. Gmail suspends accounts that blast.
- **Real name and mailing address** in every email, and honor any
  "unsubscribe" reply immediately. US law (CAN-SPAM) requires all three
  for commercial email.
- One follow-up max if they don't reply. Then move on.
