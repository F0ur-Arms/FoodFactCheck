"""List the knowledge-base fact-check articles a golden set's claims were taken from, so a golden run
can leave them out (TRUTHCHECK_EXCLUDE_SOURCES_FILE) instead of answering a claim by finding its own
fact-check.

The KB holds fact-check articles (Vishvas News, THIP, Times of India, ...) and the golden set's Indian
claims come from the same sites. A fact-check file is listed when, for a true/false golden row,
- it is the row's gold_evidence_source, or
- it contains the row's gold_evidence_quote word for word (quotes of 5+ words), or
- it shares at least --claim-share of the claim's word 4-grams.
Reference pages (NHS, WHO, NIH, ...) are never listed: a claim answered from a general page is the
system working. Rows whose gold quote is in such a page are reported separately by merge_shards.py
(quote_in_kb).

usage: python evaluation/golden_set_kb_overlap.py GOLDEN.csv [--out exclude.txt] [--claim-share 0.4]
"""
import argparse
import csv
import glob
import os
import re
from collections import Counter, defaultdict

FACT_CHECK_PREFIXES = ("vishvas", "thip", "toi", "foodfacts", "indianexpress")
SCORED = {"FALSE", "MOSTLY_FALSE", "MISLEADING", "SUPPORTED", "SUPPORTED_WITH_CAVEATS"}
N = 4


def tokens(text):
    return re.sub(r"[^\w ]+", " ", str(text).lower()).split()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("golden")
    ap.add_argument("--kb", default="data/medical_kb")
    ap.add_argument("--out", default="evaluation/golden_set_exclude.txt")
    ap.add_argument("--claim-share", type=float, default=0.4)
    args = ap.parse_args()

    fc = {os.path.basename(f): " ".join(tokens(open(f, encoding="utf-8", errors="replace").read()))
          for f in glob.glob(f"{args.kb}/*.txt") if os.path.basename(f).split("__")[0].split("_")[0] in FACT_CHECK_PREFIXES}
    grams = defaultdict(set)
    for name, text in fc.items():
        w = text.split()
        for i in range(len(w) - N + 1):
            grams[" ".join(w[i:i + N])].add(name)

    listed, rows_hit = set(), Counter()
    with open(args.golden, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["expected_verdict"] in SCORED]
    for r in rows:
        hits = set()
        if r["gold_evidence_source"] in fc:
            hits.add(r["gold_evidence_source"])
        quote = " ".join(tokens(r["gold_evidence_quote"]))
        if len(quote.split()) >= 5:
            hits |= {name for name, text in fc.items() if quote in text}
        w = tokens(r["claim_text"])
        gs = [" ".join(w[i:i + N]) for i in range(len(w) - N + 1)]
        if len(gs) >= 3:
            counts = Counter(name for g in gs for name in grams.get(g, ()))
            hits |= {name for name, n in counts.items() if n / len(gs) >= args.claim_share}
        if hits:
            rows_hit[r["language"]] += 1
            listed |= hits
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(f"# fact-check KB files matching claims of {os.path.basename(args.golden)} "
                f"(made by evaluation/golden_set_kb_overlap.py)\n")
        f.write("\n".join(sorted(listed)) + "\n")
    print(f"{len(rows)} true/false rows; {sum(rows_hit.values())} match a KB fact-check {dict(rows_hit)}")
    print(f"{len(listed)} of {len(fc)} fact-check files listed in {args.out}")


if __name__ == "__main__":
    main()
