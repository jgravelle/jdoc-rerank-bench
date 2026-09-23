# Candidate grader validation against the 440 human grades

The section-3 audit failed (`A6-AUDIT-RESULT-2026-09-22.md`). These runs score
candidate graders on the **same 440 passages the human judged**, before anyone
spends 4,020 calls on a relabel. Scored against HUMAN grades, never against the
old model's labels — those are the thing under suspicion.

⚠ Wired correctly by a CONTROL: scoring the existing 8B labels through this
harness reproduces the audit to the decimal (75.0% / 90.0% / 62.8%, 440 of 440
matched). Without it a mapping slip would have read as a grader result.

## Run 1 — gemma4:latest (8B), ONE passage per call — FAIL

Testing hypothesis B: that grading 15 siblings in one prompt induced relative
ranking, so the best-of-batch read as an answer. ⚠ Not idle speculation — this
repo already recorded the same hazard for the other reranker: "int8
cross-encoder scores depend on batch composition; one passage per call."

| | 8B batch (the audited labels) | 8B single |
|---|---|---|
| overall exact | 61.6% | 62.9% |
| **passages called 0** | **120** | **196** |
| **GATE 0** (floor 90%) | **75.0%** | **57.1% — worse** |
| passages called 2 | 140 | 129 |
| GATE 2 (floor 80%) | 90.0% | 92.2% |
| grade-1 exact | 62.8% | 74.1% |

437 of 440 graded, 4 unusable (2 transport timeouts, 1 `token repeat limit
reached`).

### ⚠⚠ Hypothesis B is dead, and it died in the informative direction

**Removing the siblings did not fix the 0/1 boundary. It moved the error to the
other side.** Isolated, the grader calls 196 passages useless where batch called
120, and the human confirms only 57% of them. It stopped over-crediting and
started over-rejecting.

So the batch context was not the defect — **it was doing real work.** The
siblings tell the model roughly what "relevant to this query" looks like in this
corpus. Without them it has no calibration and defaults to rejection.

⚠⚠ **The two configurations agree with EACH OTHER on only 64.1% of the same 437
passages.** Same weights, same temperature, same rubric, same passages, same
machine. **Over a third of this grader's "judgement" is an artifact of prompt
shape rather than of the passage.** Any future grader claim has to survive that
observation: a number produced in one prompt geometry does not transfer to
another.

⚠ **Overall exact agreement barely moved, 61.6% to 62.9%.** The total error is
near-constant while its DIRECTION changed completely — grades 1 and 2 both
improved as grade 0 collapsed. That is the signature of a fixed amount of
discrimination being slid along a threshold, not of a grader getting better or
worse. **A prompt change cannot buy discrimination the model does not have.**

That leaves hypothesis A, capacity, as the only one standing.

## Run 2 — gemma4:26b, batch (production shape) — IN PROGRESS

Same host, 25.8B against 8.0B, Q4_K_M both. 167 calls.

⚠ A smoke of the 26B in SINGLE mode over 3 queries put 8 of 13 passages at grade
0 with the human confirming none of them — consistent with run 1's finding that
isolation hurts regardless of model size. **Batch is therefore the configuration
worth testing at 26B**, and single mode at 26B is not queued.

## What a pass would and would not mean

⚠⚠ **A pass here is NOT a section-3 pass.** These are the 440 items the human
already judged. Relabelling still needs a FRESH audit draw, because re-auditing
these rows would measure the auditor's consistency and not the new labels.
