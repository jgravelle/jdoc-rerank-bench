# The grader search is closed: four configurations, no pass, and the original was best

The A6 human audit failed section 3 on 2026-09-22 (grade-0 gate 75.0% against a
90% floor). This records the search for a grader that would clear it, why it
stopped, and what the results say about the study rather than about the models.

**Scored against the 440 human grades throughout, never against the old labels.**
The harness (`bench/a6_validate.py`) was proven wired correctly by a control
before any candidate ran: scoring the existing 8B labels through its own
(corpus, qid, section_id) mapping reproduced the audit to the decimal —
75.0% / 90.0% / 62.8% on 440 of 440 matched.

## Results

| configuration | grade-0 gate | grade-2 gate | overall exact | false zeros |
|---|---|---|---|---|
| **gemma4 8B, batch** (produced the labels) | **75.0%** | 90.0% | 61.6% | 25% |
| gemma4 8B, single | 57.1% | 92.2% | 62.9% | 43% |
| gemma4 26B, batch | 46.0% | 97.2% | 53.3% | 54% |
| gpt-oss-120B, single ⚠ partial | 45.7% | 97.0% | 54.1% | 54% |

Floor is 90% for grade 0 and 80% for grade 2. "False zeros" = the grader said 0
where the human said 1 or 2.

⚠ The 120B row is **181 of 440 passages and is NOT a measurement**: the run takes
queries in sorted order, so the sample is django 111 / fastapi 57 / packaging 11 /
pytest 2 — almost no pytest, which was the human audit's strongest corpus at 87%.
It is cited as corroboration of the 26B figure, never as a result.

## Hypothesis A — capacity — REFUTED

Tripling the parameters made every axis worse: grade-0 75.0% to 46.0%, overall
exact 61.6% to 53.3%, false zeros 25% to 54%. A 120B model from a different
family then landed at 45.7%, indistinguishable from the 26B.

## Hypothesis B — batch context — REFUTED, AND INVERTED

The prediction was that 15 visible siblings induce relative ranking, so
best-of-batch reads as an answer, and that isolating the passage would fix the
grade-0 gate. ⚠ **It did the opposite.** Stripped of siblings the 8B rejects far
more — 196 zeros against the human's 130 — and 43% of those rejections are
passages the human found useful, against 25% in batch.

**The siblings were supplying the scale: useful COMPARED TO WHAT.** Alone, the
model has no calibration for "does this help at all" and defaults to no.

⚠ This repo's own prior for the opposite conclusion was explicit — "int8
cross-encoder scores depend on batch composition; one passage per call" — and it
did not transfer. A hazard measured for a cross-encoder is not a hazard for a
generative judge.

## One direction, every time

Every intervention pushed the same way: **graders over-reject relative to a
human, and each change made it worse.** Alongside it, grade-2 precision rose
monotonically (90.0%, 92.2%, 97.2%) while grade-2 VOLUME collapsed (140, 129, 71
against the human's 111). Precision up, recall down, one dial.

## Two traps this search nearly fell into

⚠⚠ **A headline accuracy number hid the whole effect.** Overall exact agreement
moved 61.6% to 62.9% between the two 8B configurations — essentially flat — while
every cell of the confusion matrix redistributed underneath it. **Read the gates,
never the aggregate.**

⚠⚠ **Matching counts is not matching decisions.** The 8B batch grader called 120
items 0 and the human called 130 — a marginal distribution that reads as close
agreement. Only **90 are the same items.** Any metric reading the margins rather
than the pairs would have passed the original labels.

## Why the search stopped here, and not after one more run

**A fifth trial was available and was declined**, because the only remaining
configuration cannot be built:

- The question worth answering is whether a STRONG model clears the gate in
  **batch**, the sole configuration that ever came near the bar.
- ⚠ Groq's free tier caps at **8,000 TPM** while the largest batch task is
  **12,121 tokens**, so batch there is arithmetically impossible, not slow.
- OpenAI would sidestep it; probed 2026-09-24, the account returns
  `credit_balance_exhausted`.
- Finishing the 120B single run costs ~1.5 to 2 more days of Groq's 200,000/day
  cap (~1,100 tokens per passage) to complete a measurement **confounded by
  construction**: it holds mode constant at *single*, already shown inferior, so
  it can only report that a large model is bad in the bad mode.

⚠⚠ **A measurement that cannot change the decision is not worth its cost**, and
the partial value already matches the run above it.

## What this is evidence FOR

Four configurations, two model families, three sizes, two prompt modes. **All
fail, and the best is the one already in hand, 15 points short of the floor.**
That is a property of the task, not of a model choice: the grade-0 boundary —
*shares the topic, does not help* — is the exact discrimination a retrieval
benchmark exists to measure, so a generative judge that carries the confusion
cannot produce labels for one.

## ⚠⚠ The gate is NOT being lowered

Section 7's 90% was pre-registered before any label existed. Moving it now, with
the data in view, is the floor-shrinking this project already refused once during
sourcing — and it would be worse here, because it would be done knowing exactly
which number a pass requires. **The gate stands and the labels stay unusable.**

## Consequences

**The A6 draft labels are not evidence and will not become evidence by
relabelling with any grader tried here.** Arm C and Arm B remain unscorable
against them.

**Arm B stays held on both legs** — the terms question (TERMS addendum 2, where
the console login showed the MCA was never accepted) and the absence of valid
confirmatory labels. Even a written "yes, publish" from TypeSafe releases nothing.

**The 200-item dev audit pack stays suspended.** Same grader, same fate.

**The 440 human grades are the only sound labels the A6 work produced.** They are
too sparse for nDCG across 167 queries (mean 2.6 judged passages per query), so
the next question is what IS answerable with 440 gold judgements — a narrower
question than the confirmatory study was scoped for, and an honest one.

⚠ TypeSafe promo credits expire **2026-10-20** with $4.74 left. That deadline now
constrains nothing, because no arm B run can be scored.
