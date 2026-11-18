"""KB batch 7: NHS Medicines A-Z and NHS Live Well (Open Government Licence v3.0).

- Medicines A-Z (~256 medicines): what each medicine is for, dose, who can take it, side effects. Aimed at
  medicine-safety forwards ("Paracetamol P-500 contains a virus", "Combiflam can kill you", "a cough-syrup
  overdose cures a cough"), which the golden set showed the KB could not answer.
- Live Well (eat well, exercise, sleep, alcohol, smoking, healthy weight, ...): pages that state health
  facts positively, since the system confirms only about 70% of true claims and the KB leans to debunks.
These are general reference pages, not fact-checks of benchmark claims; run scripts/kb/check_kb.py on the
new files before committing. Paths in nhs.uk/robots.txt are respected (/medicines/ and /live-well/ are
allowed). Files use the nhs__ prefix, so they get the NHS source tier.

usage: python scripts/kb/scrape_batch7.py
needs: standard library only
"""
import csv
import datetime
import html
import os
import random
import re
import sys
import time
import urllib.request
from urllib.parse import urljoin, urlparse

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
KB = "data/medical_kb"
UA = "Mozilla/5.0 (compatible; TruthCheckResearchBot/0.1; academic health misinformation project)"
BASE = "https://www.nhs.uk"
TODAY = datetime.date.today().isoformat()
RULE = "─" * 60
MIN_WORDS = 80
LABEL = "NHS (Open Government Licence v3.0)"
STOP = re.compile(r"^(Page last reviewed|Next review due|Help us improve|Cookies on the NHS website|"
                  r"Related conditions|Related information|Other useful information)\b", re.I)
SKIP_LINE = {"Information:", "Important", "Urgent advice:", "Non-urgent advice:", "Immediate action required:",
             "Important: Coronavirus update"}

done = {r["filename"] for r in csv.DictReader(open(os.path.join(KB, "SOURCES.csv"), encoding="utf-8"))}
done |= set(os.listdir(KB))


def get(url):
    time.sleep(random.uniform(1.0, 2.0))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode("utf-8", "replace")


def lines_of(page):
    main = re.search(r"<main\b.*?</main>", page, re.S | re.I)
    frag = re.sub(r"<(script|style|figure|figcaption|nav|aside|footer)\b.*?</\1>", "", main.group(0) if main else page,
                  flags=re.S | re.I)
    frag = re.sub(r"<(h[1-6]|p|li|div|br|tr|dt|dd)\b[^>]*>", "\n", frag, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", frag)).replace("\xa0", " ")
    out = []
    for line in (re.sub(r"\s+", " ", x).strip() for x in text.split("\n")):
        if not line or line in SKIP_LINE:
            continue
        if STOP.match(line):
            break
        out.append(line)
    return out


def write(fn, title, url, body):
    if fn in done:
        return False
    if len(body.split()) < MIN_WORDS:
        print("skip (too short)", fn)
        return False
    done.add(fn)
    with open(os.path.join(KB, fn), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"SOURCE: {LABEL}\nTITLE: {title}\nURL: {url}\n{RULE}\n\n{body}\n")
    with open(os.path.join(KB, "SOURCES.csv"), "a", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerow([fn, "NHS", url, TODAY])
    print("ok", len(body.split()), fn)
    return True


def slug(path):
    return re.sub(r"[^a-z0-9]+", "-", path.strip("/").lower()).strip("-")[:110]


def medicines():
    listing = get(f"{BASE}/medicines/")
    paths = sorted(set(re.findall(r'href="(/medicines/[a-z0-9-]+/)"', listing)))
    added = 0
    for path in paths:
        if f"nhs__{slug(path)}.txt" in done:
            continue
        try:
            hub = get(BASE + path)
            lines = lines_of(hub)
        except Exception as e:
            print("ERR", path, str(e)[:80])
            continue
        if not lines:
            continue
        if len(" ".join(lines).split()) < MIN_WORDS:
            # A hub page: the medicine is split into sub-pages (about, how to take, side effects,
            # pregnancy, other medicines, common questions); they become one file per medicine.
            subs = sorted(set(re.findall(rf'href="(?:{re.escape(BASE)})?({re.escape(path)}[a-z0-9-]+/)"', hub)))
            for sub in subs:
                try:
                    lines += lines_of(get(BASE + sub))[1:] or []
                except Exception as e:
                    print("ERR", sub, str(e)[:80])
        added += write(f"nhs__{slug(path)}.txt", lines[0], BASE + path, "\n".join(lines))
    print(f"Medicines: {added} pages added")


def live_well(limit=160):
    start = f"{BASE}/live-well/"
    seen, frontier, added = {start}, [(start, 0)], 0
    while frontier and len(seen) <= limit:
        url, depth = frontier.pop(0)
        try:
            page = get(url)
        except Exception as e:
            print("ERR", url, str(e)[:80])
            continue
        if depth < 2:
            for href in re.findall(r'href="([^"#?]+)"', page):
                link = urljoin(BASE, href)
                link = link if link.endswith("/") else link + "/"
                if urlparse(link).netloc == "www.nhs.uk" and urlparse(link).path.startswith("/live-well/") \
                        and link not in seen:
                    seen.add(link)
                    frontier.append((link, depth + 1))
        if url == start:
            continue
        lines = lines_of(page)
        if lines:
            added += write(f"nhs__{slug(urlparse(url).path)}.txt", lines[0], url, "\n".join(lines))
    print(f"Live Well: {added} pages added")


if __name__ == "__main__":
    medicines()
    live_well()
