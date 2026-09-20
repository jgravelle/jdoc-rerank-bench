# A6 tightened grade-1 rubric

**Status:** frozen for confirmatory labels under `results/LABEL-DESIGN-A6.md`.
**Applies to:** draft LLM labels and human audit of A6-dev / A6-test only.
**Does not change:** grade 0 or grade 2 wording below (carried from `bench/labeling.py` GUIDELINES, still sound).

---

## Unchanged grades (0 and 2)

Copied from `bench/labeling.py` GUIDELINES so the audit sheet stays self-contained:

```
Grade each passage for the query. Judge only what the passage itself says.

2 = directly answers: states information a reader could cite to answer the query.
0 = not useful: shares topic or vocabulary but does not help answer the query;
    or is navigational, boilerplate, a heading with no content, or release notes.

Same words as the query is not evidence of relevance. Most passages are 0.
If the documentation cannot answer the query at all, every passage is 0.
```

Grade **2** stays as above. Do **not** rewrite it toward Jev A3 `true`
("The passage states information that directly helps answer the query. A reader
could cite it in an answer.") — that near-paraphrase is why A3 flagged
shared-method bias. Confirmatory ship comparison is vs the non-LLM baseline;
rubric wording for grade 2 must remain the pre-A3 labelling text, not Jev's
schema.

---

## Tightened grade 1 (replaces the old one-liner)

**Old (noisy; 43% exact agreement in the 2026-09-19 second-model audit):**

> 1 = partially useful: gives real but incomplete help (a needed building block,
> a closely related mechanism the answer depends on).

**New (A6):**

> **1 = necessary but incomplete.** The passage supplies at least one concrete
> fact, API, constraint, or step that a correct answer to the query **must use
> or obey**, but it does **not** by itself state a citable answer to the query
> (so it is not 2). A competent reader who had *only* this passage would still
> need at least one other passage (or outside knowledge the docs expect) to
> finish the answer.

### Positive tests (grade 1) — all must hold

1. **Necessity:** Removing the passage's specific content would force a wrong
   or incomplete answer (missing a required parameter, flag, error code,
   ordering constraint, security caveat, or named API).
2. **Substance:** The passage contains more than a heading, TOC, nav chrome,
   version banner, or "see also" list — it states a usable rule or mechanism.
3. **Incompleteness:** The passage alone does not fully answer the query
   (otherwise grade 2).

### Negative tests (not grade 1 — usually 0)

Mark **0**, not 1, when any of these apply:

- **Topic-only overlap:** same product/area/vocabulary as the query, but no
  fact the answer depends on (background, motivation, history, marketing).
- **Adjacent feature:** documents a sibling feature that is not required to
  answer this query.
- **Example without the rule:** shows code that happens to use a related API
  without stating the constraint the query asks about.
- **Navigational / boilerplate / empty heading / release notes** (same as 0).
- **"Would be nice" context:** helpful for understanding the ecosystem but not
  load-bearing for *this* answer.

### Boundary with grade 2

- If a reader could cite **this passage alone** to answer the query → **2**.
- If the passage is load-bearing but still leaves a required gap → **1**.
- When unsure between 1 and 2, prefer **1** (do not inflate 2).
- When unsure between 0 and 1, prefer **0** (do not inflate 1). This is the
  main fix for the noisy stratum: partial credit requires necessity, not
  topical warmth.

### Boundary with grade 0

- Same words as the query ≠ relevance.
- A correct-looking code sample that does not address the asked failure mode
  is **0**.
- If the corpus cannot answer the query at all, every passage is **0**
  (including superficially related ones).

### Worked sketches (illustrative; not labelled items)

| Query gist | Passage gist | Grade | Why |
|---|---|---|---|
| How to hide request body on 422 | Explains `RequestValidationError.body` exists and can be logged/returned | 1 | Needed mechanism; does not say how to *suppress* it |
| How to hide request body on 422 | Full handler override that omits `body` from the response | 2 | Citable complete answer |
| How to hide request body on 422 | Generic "FastAPI has exception handlers" intro | 0 | Topic only |
| Pin a dependency version in pyproject | Spec of `[project] dependencies` version specifiers | 1 or 2 | 2 if it fully answers pin syntax for the asked tool; 1 if it only covers one required half (e.g. PEP 508) |
| Pin a dependency version in pyproject | History of `setup.py` | 0 | Not load-bearing |

---

## Forbidden paraphrases (shared-method bias guard)

Do **not** use any of the following as grade-1 or grade-2 wording in prompts,
audit sheets, or Jev schemas for A6:

- "directly helps answer the query"
- "useful evidence for answering it"
- "a reader could cite it in an answer" *(allowed only inside the frozen
  grade-2 GUIDELINES line above, which predates Jev — do not copy it into a
  new Jev `true` criterion)*

A6 Jev question wording (when scoring begins later) must be a **different
schema id** from `jev-relevance-v1` and must **not** paraphrase this rubric.
That wording is locked in a later checklist step, after labels freeze — not
here.

---

## How labelers apply this

1. Read query and passage only (blind export from `bench.labeling` — no ranks,
   no arm names, no Jev scores).
2. Decide 2 vs not-2 using the unchanged grade-2 line.
3. If not 2, apply the **necessity** test for 1; else 0.
4. When drafting with an LLM, put this full grade-1 section in the system
   prompt; keep grades 0/2 as in GUIDELINES; temperature 0; one grade + short
   note per passage.
