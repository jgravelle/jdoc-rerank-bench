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
import re
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
        "key_env": None,
        # Pinned by J. 2026-09-20. ⚠ `:latest` FLOATS — `ollama pull` re-points it
        # and the labels would stop reproducing with nothing in the record moving.
        # The digest below is what was actually served, and `--require-digest`
        # refuses to draft against anything else.
        "model": "gemma4:latest",
        "digest": "c6eb396dbd5992bbe3f5cdb9",  # sha256 prefix, 8.0B, Q4_K_M
        "price": (0.0, 0.0),  # local
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
PROVIDER = "ollama"
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


def call(task_text: str, retries: int = 5, model: str | None = None,
         timeout: int = 900) -> tuple[dict, int, int]:
    # ⚠ `model` exists so a CANDIDATE grader can be validated against the human
    # grades without touching the drafting default. It never changes what a
    # drafting run uses, and the grader-mixing guard in draft_dir still keys on
    # MODEL, so a validation run cannot leak a second grader into a label set.
    payload = {
        "model": model or MODEL,
        "temperature": 0,
        "seed": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": task_text}],
    }
    if PROVIDER == "ollama":
        # Hold the model in memory between tasks. Without it Ollama can unload
        # between calls and pay the load cost 268 times.
        payload["keep_alive"] = "30m"
    body = json.dumps(payload).encode("utf-8")
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
            # ⚠ 900 s, not 180. The largest task is 12,408 tokens and an 8B model
            # on the Mac Mini needs minutes for it; 180 s killed the first full run
            # after five pointless retries of a request that was simply slow.
            with urllib.request.urlopen(req, timeout=timeout) as r:
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
            # ⚠⚠ A rate-limited provider SAYS how long to wait, and exponential
            # backoff from 1s ignores it. Groq's free tier is 8,000 TPM and
            # answers "Please try again in 53.6325s"; 1, 2, 4 burns every retry
            # inside the window that is still closed. Honour the stated wait.
            if e.code == 429:
                m = re.search(r"try again in ([0-9.]+)s", detail)
                wait = min(float(m.group(1)) + 1, 120) if m else 20.0
                time.sleep(wait)
                continue
            if e.code not in (429, 500, 502, 503, 529):
                raise SystemExit(f"non-retryable {last}")
        except Exception as e:  # noqa: BLE001 - transport errors are retryable
            last = repr(e)
        time.sleep(2 ** attempt)
    raise SystemExit(f"gave up after {retries}: {last}")


def verify_digest() -> str:
    """Confirm the tag still resolves to the digest these labels were drafted at.

    ⚠⚠ `gemma4:latest` is a MOVING tag. A re-pull would change the grader without
    changing one character of the record, and the labels are the confirmatory
    study's ground truth. This is the same failure mode as a floating API alias,
    and it is why the digest is pinned rather than the tag alone.
    """
    want = PROVIDERS[PROVIDER].get("digest")
    if not want:
        return ""
    host = ENDPOINT.split("/v1/")[0]
    with urllib.request.urlopen(f"{host}/api/tags", timeout=30) as r:
        tags = json.loads(r.read().decode("utf-8"))
    got = {m["name"]: m.get("digest", "") for m in tags.get("models", [])}
    have = got.get(MODEL, "")
    if not have.startswith(want):
        raise SystemExit(
            f"{MODEL} now resolves to digest {have[:24]!r}, pinned {want!r}. "
            "The grader changed; do not mix labels across digests.")
    return have


def draft_dir(d: Path, limit: int = 0, force: bool = False) -> dict:
    keymap = json.loads((d / "keymap.json").read_text(encoding="utf-8"))
    qids = list(keymap)
    if limit:
        qids = qids[:limit]
    hist, tok_in, tok_out, done, skipped = collections.Counter(), 0, 0, 0, 0
    failed: list[str] = []
    for qid in qids:
        dest = d / f"{qid}.labels.json"
        if dest.exists() and not force:
            # ⚠⚠ Reuse is only safe if the SAME grader produced it. A resumed run
            # that silently keeps another model's labels yields one label set with
            # two graders in it, which no later audit could separate — the Groq
            # smoke task was exactly this case.
            side = d / f"{qid}.notes.json"
            prev = (json.loads(side.read_text(encoding="utf-8")).get("_model")
                    if side.exists() else None)
            if prev != MODEL:
                raise SystemExit(
                    f"{qid}: already drafted by {prev!r}, now running {MODEL!r}. "
                    "Delete that dir's .labels.json/.notes.json and redraft; "
                    "never mix graders in one label set.")
            skipped += 1
            hist.update(json.loads(dest.read_text(encoding="utf-8")).values())
            continue
        task = (d / f"{qid}.md").read_text(encoding="utf-8")
        # ⚠ A local 8B model occasionally drops a key or emits a non-integer
        # grade. RE-ASK on a malformed reply — up to 3 times — rather than
        # defaulting the missing grade. ⚠⚠ Re-asking is not the same as
        # softening: a grade is never inferred, and after 3 attempts it still
        # fails loudly, because a silent 0 is indistinguishable from a judged 0
        # and would bias every metric downward on the hardest passages.
        # ⚠⚠ THE RE-ASK NAMES THE MISSING KEYS, and that is the whole point.
        # At temperature 0 with a fixed seed the model is deterministic, so
        # re-sending the identical prompt returns the identical malformed reply.
        # Measured on the 2026-09-21 full pass: three tasks spent all three
        # attempts on byte-identical failures, every one of them on the LAST
        # candidate. Changing the ask is what makes a retry a retry.
        # ⚠ Valid cells ACCUMULATE across attempts, so a second ask only has to
        # produce the keys still missing — never a whole task over again.
        grades: dict[str, int] = {}
        notes: dict[str, str] = {}
        bad = None
        for attempt in range(3):
            need = [k for k in keymap[qid] if k not in grades]
            ask = task if attempt == 0 else (
                task + "\n\n---\nYour previous reply did not grade every "
                "passage. Reply with a JSON object whose keys are EXACTLY "
                + ", ".join(need) + " and nothing else. Each value is "
                '{"g": 0|1|2, "n": "<one short sentence>"}. '
                "The grade must be the integer 0, 1 or 2.")
            try:
                out, ti, to = call(ask)
            except SystemExit as e:
                # ⚠⚠ One slow or malformed task must not end a 268-task run. It is
                # RECORDED and skipped, never faked: no label file is written, so
                # `labeling collect` reports it as missing and the gap is loud.
                # This is the opposite of defaulting a grade to 0.
                print(f"    FAILED {qid}: {e}", flush=True)
                failed.append(qid)
                break
            tok_in += ti
            tok_out += to
            got = out.get("grades", out)
            bad = None
            for k in need:
                cell = got.get(k)
                if isinstance(cell, dict):
                    g, n = cell.get("g"), cell.get("n", "")
                else:
                    g, n = cell, ""
                if g not in (0, 1, 2):
                    # ⚠ Record the first bad key and KEEP GOING: a reply that
                    # drops one cell still carries good grades for the rest.
                    if bad is None:
                        bad = f"{qid}/{k}: grade {g!r} is not 0, 1 or 2"
                    continue
                grades[k], notes[k] = int(g), str(n)[:200]
            if not bad:
                break
            print(f"    retry {attempt + 1}/3 — {bad}", flush=True)
        else:
            print(f"    FAILED {qid}: {bad}", flush=True)
            failed.append(qid)
        if qid in failed:
            continue
        dest.write_text(json.dumps({k: grades[k] for k in keymap[qid]}),
                        encoding="utf-8")
        (d / f"{qid}.notes.json").write_text(
            json.dumps({"_model": MODEL, "_temperature": 0, "notes": notes}), encoding="utf-8")
        hist.update(grades.values())
        done += 1
        print(f"  {qid}: {dict(sorted(collections.Counter(grades.values()).items()))}", flush=True)
    return {"dir": d.name, "drafted": done, "reused": skipped, "hist": hist,
            "tok_in": tok_in, "tok_out": tok_out, "failed": failed}


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
    digest = verify_digest()
    print(f"provider {PROVIDER} | endpoint {ENDPOINT}")
    print(f"model {MODEL}" + (f" | digest {digest[:24]}" if digest else "")
          + f" | temperature 0 | {len(dirs)} dir(s)")
    total, ti, to, all_failed = collections.Counter(), 0, 0, []
    for d in dirs:
        r = draft_dir(d, a.limit, a.force)
        total.update(r["hist"])
        ti += r["tok_in"]
        to += r["tok_out"]
        all_failed += r["failed"]
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
    if all_failed:
        print(f"\n{len(all_failed)} task(s) FAILED and have no label file: {all_failed}")
        print("Re-run to retry them; `labeling collect` will report them missing.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
