r"""A6 §9 step 10: draft labels for the blind tasks with a non-Jev LLM.

Reads `label_tasks/<dir>/<qid>.md` — the blind task, which already carries the
query, the A6 rubric and the shuffled passages — and writes
`<qid>.labels.json` for `bench.labeling collect`, plus a `<qid>.notes.json`
sidecar.

⚠⚠ **Never TypeSafe/Jev.** These labels are the ground truth the confirmatory
study is scored against; grading them with the system under test is the
circularity A6 exists to avoid. The model is pinned to a dated snapshot and
`temperature=0` so a re-run reproduces the labels.

⚠ Notes go in a SEPARATE file because `labeling.collect` rejects any key outside
the keymap — a note stored beside the grades would fail the collect it is meant
to document.

    python -m bench.a6_draft --dir label_tasks/django-a6dev --limit 1     # smoke
    python -m bench.a6_draft --dir label_tasks/django-a6dev --limit 30    # dry-run
    python -m bench.a6_draft --all
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Providers, in the order J. pinned on 2026-09-20. ⚠ Prefer a DATED snapshot over
# a floating alias: an alias re-points and the labels stop being reproducible
# without anything in the record changing.
#
# ⚠⚠ `ollama` is FIRST BY PREFERENCE AND UNREACHABLE AS CONFIGURED. The Mac Mini
# answers on Tailscale (2-6 ms) but Ollama's own port 11434 is closed — it binds
# 127.0.0.1 by default — and the Open WebUI 0.8.8 in front of it on :8080 reports
# `"enable_api_keys": false`, so there is no programmatic route in. Fixing it is
# either `launchctl setenv OLLAMA_HOST 0.0.0.0` plus an Ollama restart, or
# switching API keys on in Open WebUI. Left in the table so the preferred route
# is one flag away once that is done.
PROVIDERS = {
    "ollama": {
        "endpoint": "http://gravelles-mac-mini.tail5b29f8.ts.net:11434/v1/chat/completions",
        "key_env": None, "model": None,  # set --model to the exact `ollama list` tag
        "price": (0.0, 0.0),
    },
    "openai": {
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "key_env": "OPENAI_API_KEY", "model": "gpt-4o-mini-2024-07-18",
        # developers.openai.com/api/docs/pricing, read 2026-09-20
        "price": (0.15, 0.60),
    },
    "groq": {
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY", "model": "openai/gpt-oss-120b",
        "price": (0.0, 0.0),  # not priced here; see the memo
    },
}
PROVIDER = "groq"
MODEL = PROVIDERS[PROVIDER]["model"]
ENDPOINT = PROVIDERS[PROVIDER]["endpoint"]
PRICE_IN, PRICE_OUT = PROVIDERS[PROVIDER]["price"]

SYSTEM = """\
You are grading documentation passages for retrieval relevance. The user message \
contains the query, the grading rubric, and the candidate passages under opaque \
keys (c01, c02, ...).

Apply the rubric in the message exactly as written. It is authoritative; do not \
substitute your own notion of relevance, and do not reward a passage for sharing \
vocabulary with the query.

Reply with JSON only, no prose outside it, in this shape:

{"grades": {"c01": {"g": 0, "n": "why, <=15 words"}, "c02": {"g": 2, "n": "..."}}}

Every key present in the message must appear exactly once. `g` is the integer 0, \
1, or 2. Grade every passage on its own merits; there is no quota and no required \
distribution."""


def call(task_text: str, retries: int = 5) -> tuple[dict, int, int]:
    body = json.dumps({
        "model": MODEL,
        "temperature": 0,
        "seed": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": task_text}],
    }).encode("utf-8")
    key_env = PROVIDERS[PROVIDER]["key_env"]
    key = os.environ.get(key_env) if key_env else None
    if key_env and not key:
        raise SystemExit(f"{key_env} is not set")
    last = None
    for attempt in range(retries):
        # ⚠ Groq sits behind Cloudflare, which answers urllib's default
        # `Python-urllib/3.x` with HTTP 403 code 1010 (browser-signature block).
        # The same request through curl passed, which is how the UA was isolated.
        headers = {"Content-Type": "application/json",
                   "User-Agent": "jdoc-rerank-bench/a6 (+labels)"}
        if key:
            # ⚠ Read from the environment and never logged. Nothing here prints a
            # header, and the error path prints status and body only.
            headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request(ENDPOINT, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read().decode("utf-8"))
            u = d.get("usage", {})
            return (json.loads(d["choices"][0]["message"]["content"]),
                    u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            last = f"HTTP {e.code}: {detail}"
            # ⚠⚠ A 429 is not always a rate limit. OpenAI returns 429 for
            # `insufficient_quota` / `credit_balance_exhausted`, which no amount of
            # backoff fixes — the first run here spent 5 attempts and ~60 s
            # rediscovering that an account had no credits. Retry the transient
            # 429s and fail fast on the terminal ones.
            if e.code == 429 and ("insufficient_quota" in detail
                                  or "credit_balance_exhausted" in detail):
                raise SystemExit(f"terminal {last}")
            if e.code not in (429, 500, 502, 503, 529):
                raise SystemExit(f"non-retryable {last}")
        except Exception as e:  # noqa: BLE001 - transport errors are retryable
            last = repr(e)
        time.sleep(2 ** attempt)
    raise SystemExit(f"gave up after {retries}: {last}")


def draft_dir(d: Path, limit: int = 0, force: bool = False) -> dict:
    keymap = json.loads((d / "keymap.json").read_text(encoding="utf-8"))
    qids = list(keymap)
    if limit:
        qids = qids[:limit]
    hist, tok_in, tok_out, done, skipped = collections.Counter(), 0, 0, 0, 0
    for qid in qids:
        dest = d / f"{qid}.labels.json"
        if dest.exists() and not force:
            skipped += 1
            hist.update(json.loads(dest.read_text(encoding="utf-8")).values())
            continue
        task = (d / f"{qid}.md").read_text(encoding="utf-8")
        out, ti, to = call(task)
        tok_in += ti
        tok_out += to
        got = out.get("grades", out)
        grades, notes = {}, {}
        for k in keymap[qid]:
            cell = got.get(k)
            if isinstance(cell, dict):
                g, n = cell.get("g"), cell.get("n", "")
            else:
                g, n = cell, ""
            if g not in (0, 1, 2):
                # ⚠ A missing or out-of-range grade is NOT defaulted to 0. A
                # silent 0 is indistinguishable from a judged 0 and would bias
                # every metric downward on exactly the passages the model found
                # hardest. It fails loudly instead.
                raise SystemExit(f"{qid}/{k}: grade {g!r} is not 0, 1 or 2")
            grades[k], notes[k] = int(g), str(n)[:200]
        dest.write_text(json.dumps(grades), encoding="utf-8")
        (d / f"{qid}.notes.json").write_text(
            json.dumps({"_model": MODEL, "_temperature": 0, "notes": notes}), encoding="utf-8")
        hist.update(grades.values())
        done += 1
        print(f"  {qid}: {dict(sorted(collections.Counter(grades.values()).items()))}", flush=True)
    return {"dir": d.name, "drafted": done, "reused": skipped, "hist": hist,
            "tok_in": tok_in, "tok_out": tok_out}


def main(argv=None) -> int:
    global PROVIDER, MODEL, ENDPOINT, PRICE_IN, PRICE_OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=None)
    ap.add_argument("--all", action="store_true", help="every label_tasks/*-a6* dir")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true", help="re-draft tasks already done")
    ap.add_argument("--provider", choices=list(PROVIDERS), default=PROVIDER)
    ap.add_argument("--model", default=None, help="override the provider's pinned model tag")
    a = ap.parse_args(argv)

    PROVIDER = a.provider
    ENDPOINT = PROVIDERS[PROVIDER]["endpoint"]
    MODEL = a.model or PROVIDERS[PROVIDER]["model"]
    PRICE_IN, PRICE_OUT = PROVIDERS[PROVIDER]["price"]
    if not MODEL:
        raise SystemExit(f"--model is required for provider {PROVIDER}")

    dirs = ([Path(a.dir)] if a.dir else
            [Path(p) for p in sorted(glob.glob(str(ROOT / "label_tasks" / "*-a6*")))])
    if not dirs:
        raise SystemExit("no task dirs")
    print(f"model {MODEL} | temperature 0 | {len(dirs)} dir(s)")
    total, ti, to = collections.Counter(), 0, 0
    for d in dirs:
        r = draft_dir(d, a.limit, a.force)
        total.update(r["hist"])
        ti += r["tok_in"]
        to += r["tok_out"]
        n = sum(r["hist"].values())
        print(f"{r['dir']}: drafted {r['drafted']}, reused {r['reused']} | "
              f"grades {dict(sorted(r['hist'].items()))}"
              + (f" | grade1 {r['hist'][1] / n:.1%}" if n else ""), flush=True)
    n = sum(total.values())
    print(f"\nTOTAL {n} pairs | grades {dict(sorted(total.items()))}")
    if n:
        for g in (0, 1, 2):
            print(f"  grade {g}: {total[g]:5d}  {total[g] / n:6.1%}")
    cost = ti / 1e6 * PRICE_IN + to / 1e6 * PRICE_OUT
    print(f"tokens in {ti} out {to} | cost ${cost:.4f} at ${PRICE_IN}/${PRICE_OUT} per Mtok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
