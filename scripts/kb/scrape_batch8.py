"""KB batch 8: CDC consumer health pages across all CDC topic sections (US government work, public domain).

Batch 3 took CDC pages for about 25 infectious-disease sections only (covid, vaccines, flu, measles, ...).
The golden set's English claims abstain mostly where the KB has no page on the topic (ticks, sleep, lead,
inhalants, ear infections, cancer risks, ...). This batch walks every section in CDC's sitemap index and
keeps only consumer pages (not pages about CDC's own divisions, funding,
partners or data systems): its about / signs-symptoms / causes / risk-factors /
prevention / treatment / testing / FAQ pages, at most PER_SECTION per section. Program, grant, data,
surveillance, training and Spanish-language sections are skipped. These are general reference pages,
picked by source and page type, not by test claim; run scripts/kb/check_kb.py and
evaluation/golden_set_kb_overlap.py on the new files before committing.

robots.txt: https://www.cdc.gov/robots.txt allows these paths (it disallows /travel/, /migration/ and
template paths, which are skipped). Files use the cdc_ prefix like batch 3.

usage: python scripts/kb/scrape_batch8.py
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

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
KB = "data/medical_kb"
UA = "Mozilla/5.0 (compatible; TruthCheckResearchBot/0.1; academic health misinformation project)"
TODAY = datetime.date.today().isoformat()
RULE = "─" * 60
MIN_WORDS = 120
PER_SECTION = 8
LABEL = "CDC (U.S. government work, public domain)"

# Sections that are programs, data, funding, training, labs or not in English.
SKIP_SECTION = re.compile(
    r"(^|-)(data|grants?|funding|budget|training|surveillance|lab|labs|laboratory|conference|fellowships?|"
    r"academy|program|programs|partners|toolkit|network|networks|registries|statistics|report|reports|"
    r"atlas|forecast|forecasting|modeling|informatics|elective|course|manual|handbook|vaxview)(-|$)|"
    r"^(about|budget|cdc-info|cdc-train|contracts|foia|finance|media|mmwr|pcd|library|museum|search|spanish|"
    r"es|dejar|movernos|tratamientoscovid|ecigarrillos|e-cigarrillos|ecigarillos|other|wcms.*|travel|"
    r"migration|yellow-book|pinkbook|regulations|policy|ethics|priorities|readiness|washington|os|ocio|"
    r"oeeo|right-to-know|executive-secretariat|faca|hicpac|acip.*|cliac|nchs|niosh|nndss|nhsn|brfss|"
    r"yrbs|prams|nisvs|nvdrs|epiinfo|eis.*|phifp|phap|phlp|cerc|si|span|tips.*)$")
KEEP_PATH = re.compile(r"/(about[^/]*|signs-symptoms[^/]*|symptoms[^/]*|causes[^/]*|risk-factors[^/]*|"
                       r"prevention[^/]*|prevent[^/]*|treatment[^/]*|testing[^/]*|faq[^/]*|facts[^/]*|"
                       r"health-effects[^/]*|risks?[^/]*)(/|$)")
SKIP_PATH = re.compile(r"/(hcp/training|training|communication-resources|data-research|php|media|resources|"
                       r"site|es|spanish|partners|programs?|funding|toolkits?)/")
STOP = re.compile(r"^(Sources|Resources|Related Pages|Page last reviewed|Content Source|On This Page)$", re.I)
# The page's last-updated date often sits above the heading; it is dropped so the heading becomes the title.
DATE = re.compile(r"^(January|February|March|April|May|June|July|August|September|October|November|December) "
                  r"\d{1,2}, \d{4}$")
# Pages about CDC itself (divisions, funding, partners, data systems, staff training), not about health.
ADMIN = re.compile(r"\b(Division|Divisions|Office|Offices|Centers? of Excellence|NOFO|Funding|Funded|Awardees?|Grants?|"
                   r"Grantees?|Recipients|Continuing Education|News and Events|(?<!Intimate )Partners?|Partnerships?|"
                   r"What CDC Is Doing|CDC'?s (Role|Work|Response|Approach)|Programs?|Data|Surveillance|Network|"
                   r"Toolkits?|Training|Webinars?|Laboratory|Laboratories|Strategic|Strategy|Initiative|Our Work|"
                   r"Mission|Leadership|Staff|Contact Us|Publications|Reports?|Evaluation|Framework|Jurisdictions?|"
                   r"Health Departments?|Healthcare Providers|Clinicians|Employers|Workers)\b", re.I)
ADMIN_PATH = re.compile(r"(divisions-offices|organization|awardees|funded|nofo|-data|data-|wastewater|nwss|comec|vams|"
                        r"zohu|set-net|-ce$|what-cdc-is-doing|partners|program)")

done_files = {r["filename"] for r in csv.DictReader(open(os.path.join(KB, "SOURCES.csv"), encoding="utf-8"))}
done_files |= set(os.listdir(KB))
done_urls = {r["url"].rstrip("/") for r in csv.DictReader(open(os.path.join(KB, "SOURCES.csv"), encoding="utf-8"))
             if r.get("url")}


def get(url):
    time.sleep(random.uniform(1.0, 2.0))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read().decode("utf-8", "replace")


def locs(url):
    try:
        return [u.strip() for u in re.findall(r"<loc>([^<]+)</loc>", get(url))]
    except Exception as e:
        print("ERR", url, str(e)[:80])
        return []


def lines_of(page):
    main = re.search(r"<main\b.*?</main>", page, re.S | re.I)
    frag = re.sub(r"<(script|style|figure|figcaption|nav|aside|footer|button|form)\b.*?</\1>", "",
                  main.group(0) if main else page, flags=re.S | re.I)
    frag = re.sub(r"<(h[1-6]|p|li|div|br|tr|dt|dd)\b[^>]*>", "\n", frag, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", frag)).replace("\xa0", " ")
    out = []
    for line in (re.sub(r"\s+", " ", x).strip() for x in text.split("\n")):
        if not line or DATE.match(line):
            continue
        if STOP.match(line):
            break
        if out and line == out[-1]:
            continue
        out.append(line)
    return out


def filename(url):
    path = re.sub(r"(/index)?\.html$", "", url.split("cdc.gov/", 1)[1]).strip("/")
    return "cdc_" + re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")[:110] + ".txt"


def main():
    sitemaps = locs("https://www.cdc.gov/wcms-auto-sitemap-index.xml")
    added = 0
    for sm in sitemaps:
        section = sm.split("/")[3]
        if SKIP_SECTION.search(section) or not re.fullmatch(r"[a-z0-9-]+", section):
            continue
        urls = [u for u in locs(sm) if u.endswith(".html") and KEEP_PATH.search(u) and not SKIP_PATH.search(u)]
        urls.sort(key=lambda u: (u.count("/"), len(u)))  # section index and about pages first
        kept = 0
        for url in urls:
            if kept >= PER_SECTION:
                break
            fn = filename(url)
            if fn in done_files or url.rstrip("/") in done_urls:
                continue
            try:
                lines = lines_of(get(url))
            except Exception as e:
                print("ERR", url, str(e)[:80])
                continue
            body = "\n".join(lines[1:])
            if not lines or len(body.split()) < MIN_WORDS:
                continue
            if ADMIN.search(lines[0]) or ADMIN_PATH.search(fn[4:-4]):
                continue
            done_files.add(fn)
            with open(os.path.join(KB, fn), "w", encoding="utf-8", newline="\n") as f:
                f.write(f"SOURCE: {LABEL}\nTITLE: {lines[0]}\nURL: {url}\n{RULE}\n\n{body}\n")
            with open(os.path.join(KB, "SOURCES.csv"), "a", encoding="utf-8", newline="") as f:
                csv.writer(f, lineterminator="\n").writerow([fn, "CDC", url, TODAY])
            kept += 1
            added += 1
            print("ok", section, len(body.split()), fn)
    print(f"CDC: {added} pages added")


if __name__ == "__main__":
    main()
