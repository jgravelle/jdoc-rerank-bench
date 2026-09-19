provider: onnx-int8-b1  version: Xenova/ms-marco-MiniLM-L-6-v2:model_quantized:512:b1:t4  torch loaded: False

### Primary: graded labels (0/1/2)

| group | n | baseline nDCG@5 | oracle gain | delta, RRF k=60 [95% CI] | better | worse | worse % |
|---|---|---|---|---|---|---|---|
| Q3-Q5 pooled | 154 | 0.391 | +0.497 | +0.097 [+0.066, +0.126] | 87 | 23 | 14.9% |
| Q2 | 31 | 0.414 | +0.571 | +0.200 [+0.124, +0.282] | 24 | 2 | 6.5% |
| Q3 | 76 | 0.334 | +0.549 | +0.128 [+0.080, +0.172] | 44 | 10 | 13.2% |
| Q4 | 42 | 0.482 | +0.421 | +0.072 [+0.019, +0.123] | 24 | 6 | 14.3% |
| Q5 | 36 | 0.402 | +0.476 | +0.059 [+0.008, +0.113] | 19 | 7 | 19.4% |
| django-test (Q3-Q5) | 43 | 0.417 | +0.517 | +0.078 [+0.023, +0.132] | 22 | 10 | 23.3% |
| fastapi-test (Q3-Q5) | 32 | 0.397 | +0.497 | +0.062 [-0.020, +0.129] | 17 | 6 | 18.8% |
| k8s-test (Q3-Q5) | 43 | 0.371 | +0.528 | +0.106 [+0.061, +0.154] | 25 | 3 | 7.0% |
| packaging-test (Q3-Q5) | 36 | 0.377 | +0.436 | +0.138 [+0.073, +0.205] | 23 | 4 | 11.1% |

### Sensitivity: only grade 2 counts as relevant

| group | n | baseline nDCG@5 | oracle gain | delta, RRF k=60 [95% CI] | better | worse | worse % |
|---|---|---|---|---|---|---|---|
| Q3-Q5 pooled | 154 | 0.312 | +0.368 | +0.093 [+0.060, +0.125] | 58 | 8 | 5.2% |
| Q2 | 31 | 0.364 | +0.430 | +0.194 [+0.104, +0.293] | 17 | 1 | 3.2% |
| Q3 | 76 | 0.255 | +0.421 | +0.116 [+0.063, +0.166] | 30 | 3 | 3.9% |
| Q4 | 42 | 0.441 | +0.288 | +0.088 [+0.032, +0.145] | 16 | 2 | 4.8% |
| Q5 | 36 | 0.280 | +0.350 | +0.053 [+0.002, +0.110] | 12 | 3 | 8.3% |
| django-test (Q3-Q5) | 43 | 0.351 | +0.393 | +0.088 [+0.032, +0.146] | 16 | 2 | 4.7% |
| fastapi-test (Q3-Q5) | 32 | 0.299 | +0.326 | +0.053 [-0.041, +0.131] | 10 | 2 | 6.2% |
| k8s-test (Q3-Q5) | 43 | 0.239 | +0.348 | +0.088 [+0.042, +0.139] | 14 | 2 | 4.7% |
| packaging-test (Q3-Q5) | 36 | 0.363 | +0.400 | +0.142 [+0.073, +0.211] | 18 | 2 | 5.6% |

### Latency, one pool of 20, CPU

p50 398 ms, p95 1251 ms, max 2019 ms (n=205)
- k8s-test: p50 289, p95 581
- fastapi-test: p50 511, p95 679
- packaging-test: p50 375, p95 973
- django-test: p50 828, p95 1671

### Out-of-corpus controls (reported, no threshold)

top reranked score, median: Q6 0.819 (n=20) vs answerable classes 0.980 (n=185)

### Section 6 checks

- PASS  6.1 pooled lower bound > 0 and point >= +0.04
- PASS  6.2 every corpus point > 0, none with interval entirely below zero
- FAIL  6.3 regressions <= 12% of queries (Q3-Q5 pooled)
- PASS  6.4 no class Q3-Q5 with interval entirely below zero
- FAIL  6.5 latency p95 <= 500 ms and p50 <= 300 ms
