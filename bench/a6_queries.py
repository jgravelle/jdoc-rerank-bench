r"""A6 query sourcing: fetch top-voted Stack Overflow titles, exclude spent, draft classes.

`LABEL-DESIGN-A6.md` section 3 rules, implemented so the sourcing is reproducible
rather than described:

  - top-voted questions for a tag (Stack Exchange API, CC BY-SA)
  - exclude any qid already in `queries/**` or `labels/**` (the spent set)
  - exclude near-duplicate text: token Jaccard >= 0.85 against any spent query
  - provisional class from the TITLE ONLY

⚠⚠ `classify` is a keyword heuristic, not judgment. It exists so the draft is
reproducible and so a hand review can be diffed against it; the hand review in
`queries/_draft/a6-class-review.json` wins where the two disagree. Nothing here
reads retrieval, any reranker, or any Jev score.

    python -m bench.a6_queries --tag django --prefix dj6 --out queries/_draft/x.jsonl
    python -m bench.a6_queries reclassify --files queries/_draft/*.jsonl
"""

from __future__ import annotations

import argparse
import collections
import gzip
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.stackexchange.com/2.3/questions"

# Title-only signals. Precedence: Q6 > Q4 > Q5 > Q2 > Q3.
OUT_OF_SCOPE = re.compile(
    r"\b(heroku|vercel|netlify|aws|lambda|azure|gcp|nginx|apache|iis|docker|kubernetes|k8s|"
    r"vscode|vs code|visual studio|pycharm|jupyter|colab|conda|anaconda|"
    r"windows 1[01]|macos|os x|m1 mac|ubuntu \d|"
    r"celery|redis|rabbitmq|mongodb|mysqldb|jenkins|github actions|"
    r"react|vue|angular|next\.js|nuxt|youtube|openid|pylint)\b", re.I)
POLICY = re.compile(
    r"\b(should i|should you|best practic|best way|best solution|recommended|recommend|"
    r"correct way|correctly|proper way|properly|right way|"
    r"is it (safe|bad|ok|good|wrong|possible to)|when (to|should)|where to (store|put)|"
    r"do i need|worth|convention|idiomatic|prefer(red)?|good practice|anti-?pattern|"
    r"pros and cons|trade-?offs?|advisable|supposed to|directory structure)\b", re.I)
# ⚠⚠ A choice between two named options is a POLICY question ("which do I use"),
# not a multi-concept one. Moving these to Q4 is what thickens Q4 honestly.
CHOICE = re.compile(r"(\bvs\.?\b|\bversus\b|\bdifference between\b)", re.I)
MULTI = re.compile(
    r"(\bwhile also\b|\band also\b|\bboth\b.*\band\b|\bwithout breaking\b|"
    r"\bwhile (keeping|preserving|still)\b|\btogether\b|\bseparate\b.*\bfrom\b|"
    r"\bintegrate\b.*\bwith\b|\bat once\b|\bmultiple times\b)", re.I)
# ⚠⚠ The first version of LITERAL matched `[A-Z][a-z]+[A-Z]\w*`, which matches
# "FastAPI" itself, so 54 of 80 fastapi titles were classed Q2. A corpus's own
# name is never evidence of a literal API lookup: TOPIC_NAMES is stripped first.
LITERAL = re.compile(
    r"(`[^`]+`|--[a-z][\w-]+|\b[a-z]+_[a-z_]{2,}\b|\b[a-z]\w*\.[a-z_]+\(|"
    r"\b__\w+__\b|\b[A-Z][a-z]+[A-Z]\w*\b|\b[A-Z]{2,}_[A-Z_]+\b)")
TOPIC_NAMES = re.compile(
    r"\b(fastapi|fastapi's|django|django's|pytest|py\.test|pip|pip3|pypi|"
    r"python|python3|conftest\.py|setup\.py|uvicorn|pydantic)\b", re.I)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def toks(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def classify(title: str) -> str:
    """Provisional class from the title alone."""
    if OUT_OF_SCOPE.search(title):
        return "Q6"
    if POLICY.search(title) or CHOICE.search(title):
        return "Q4"
    if MULTI.search(title):
        return "Q5"
    if LITERAL.search(TOPIC_NAMES.sub(" ", title)):
        return "Q2"
    return "Q3"


def spent() -> tuple[set[str], list[set[str]]]:
    qids, texts = set(), set()
    for p in list(ROOT.glob("queries/**/*.jsonl")) + list(ROOT.glob("labels/**/*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if "qid" in r:
                qids.add(r["qid"])
            if r.get("query"):
                texts.add(norm(r["query"]))
    return qids, [toks(t) for t in texts]


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


def fetch(tag: str, pages: int) -> list[dict]:
    out = []
    for page in range(1, pages + 1):
        url = (f"{API}?order=desc&sort=votes&tagged={tag}&site=stackoverflow"
               f"&pagesize=100&page={page}")
        req = urllib.request.Request(
            url, headers={"Accept-Encoding": "gzip", "User-Agent": "jdoc-rerank-bench/a6"})
        with urllib.request.urlopen(req, timeout=60) as r:
            raw, enc = r.read(), r.headers.get("Content-Encoding")
        if enc == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        d = json.loads(raw.decode("utf-8"))
        out += d.get("items", [])
        print(f"  page {page}: +{len(d.get('items', []))} (quota_remaining={d.get('quota_remaining')})",
              flush=True)
        if not d.get("has_more"):
            break
        time.sleep(1.0)
    return out


def cmd_reclassify(a) -> int:
    """Re-apply the heuristic, then the hand review, in place."""
    review = {k: v for k, v in json.loads((ROOT / a.review).read_text(encoding="utf-8")).items()
              if not k.startswith("_")}
    before, after, changed, applied, seen = collections.Counter(), collections.Counter(), 0, 0, set()
    per_file = {}
    for name in a.files:
        p = ROOT / name
        rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
        for r in rows:
            before[r["class"]] += 1
            new = classify(r["query"])
            if r["qid"] in review:
                new, _ = review[r["qid"]], seen.add(r["qid"])
                applied += 1
            changed += new != r["class"]
            r["class"] = new
            after[new] += 1
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        per_file[Path(name).stem] = collections.Counter(r["class"] for r in rows)
    print("before:", dict(sorted(before.items())))
    print("after: ", dict(sorted(after.items())))
    print(f"changed {changed} of {sum(after.values())}; overrides applied {applied}")
    stale = sorted(set(review) - seen)
    if stale:
        print(f"⚠ {len(stale)} override qids matched no row (typo?): {stale[:8]}")
    for f, c in per_file.items():
        print(f"  {f}: {dict(sorted(c.items()))}")
    return 0


def cmd_fetch(a) -> int:
    sq, st = spent()
    print(f"spent: {len(sq)} qids, {len(st)} texts")
    items = fetch(a.tag, a.pages)
    print(f"fetched {len(items)} questions for tag {a.tag}")
    rows, drop_qid, drop_dup, seen = [], 0, 0, set()
    for it in items:
        if len(rows) >= a.want:
            break
        title = html.unescape(it["title"]).strip()
        qid = f"{a.prefix}{it['question_id']}"
        if qid in sq or qid in seen:
            drop_qid += 1
            continue
        t = toks(norm(title))
        if any(jaccard(t, s) >= 0.85 for s in st):
            drop_dup += 1
            continue
        seen.add(qid)
        rows.append({"qid": qid, "class": classify(title), "query": title,
                     "source": f"stackoverflow.com/q/{it['question_id']}",
                     "so_score": it.get("score"), "so_tags": it.get("tags", [])})
    dest = ROOT / a.out
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} -> {a.out}  (dropped {drop_qid} spent/dup-id, {drop_dup} near-dup text)")
    print("provisional classes:", dict(sorted(collections.Counter(r["class"] for r in rows).items())))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("reclassify")
    r.add_argument("--review", default="queries/_draft/a6-class-review.json")
    r.add_argument("--files", nargs="+", required=True)
    r.set_defaults(f=cmd_reclassify)
    f = sub.add_parser("fetch")
    f.add_argument("--tag", required=True)
    f.add_argument("--prefix", required=True)
    f.add_argument("--out", required=True)
    f.add_argument("--want", type=int, default=80)
    f.add_argument("--pages", type=int, default=5)
    f.set_defaults(f=cmd_fetch)
    a = ap.parse_args(argv)
    if not getattr(a, "f", None):
        ap.print_help()
        return 2
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
