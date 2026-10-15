# Bloom (RBT) classification — measured results

Questions: 297 (13 papers, 8 subject families). Protocol: leave-one-subject-family-out. Labels: RBT levels assigned by the paper setters (noisy human labels).

| model | accuracy [95% CI] | within-±1 | macro-F1 [95% CI] | weighted-F1 |
|---|---|---|---|---|
| majority | 0.246 [0.199, 0.293] | 0.657 | 0.093 [0.072, 0.114] | 0.146 |
| verb_rule | 0.279 [0.226, 0.330] | 0.653 | 0.243 [0.181, 0.302] | 0.260 |
| tfidf_lr | 0.236 [0.189, 0.283] | 0.603 | 0.165 [0.129, 0.205] | 0.220 |
| MiniLM_lr | 0.219 [0.175, 0.269] | 0.623 | 0.169 [0.127, 0.214] | 0.211 |
| bge-smen_lr | 0.236 [0.185, 0.286] | 0.582 | 0.181 [0.137, 0.231] | 0.217 |
| mpnet-base-v2_lr | 0.229 [0.182, 0.276] | 0.603 | 0.184 [0.136, 0.233] | 0.224 |
| MiniLM_lr+marks | 0.209 [0.162, 0.256] | 0.593 | 0.146 [0.114, 0.179] | 0.200 |
| bge-smen_lr+marks | 0.222 [0.175, 0.269] | 0.579 | 0.156 [0.120, 0.187] | 0.202 |
| mpnet-base-v2_lr+marks | 0.215 [0.168, 0.263] | 0.576 | 0.157 [0.123, 0.190] | 0.210 |
| minilm_finetuned+marks | 0.256 [0.205, 0.306] | 0.626 | 0.167 [0.131, 0.204] | 0.231 |

## Best model by macro-F1: `verb_rule`

Per-class precision / recall / F1:

| level | precision | recall | F1 | support |
|---|---|---|---|---|
| L1 Remember | 0.29 | 0.36 | 0.32 | 58 |
| L2 Understand | 0.28 | 0.41 | 0.33 | 73 |
| L3 Apply | 0.34 | 0.30 | 0.32 | 80 |
| L4 Analyse | 0.06 | 0.02 | 0.03 | 50 |
| L5 Evaluate | 0.22 | 0.15 | 0.18 | 27 |
| L6 Create | 0.23 | 0.33 | 0.27 | 9 |

Confusion matrix (rows = true L1..L6, cols = predicted L1..L6):

```
  21   20    9    4    3    1
  19   30   15    6    3    0
  13   30   24    4    4    5
  10   17   16    1    4    2
   7    7    6    1    4    2
   2    3    1    0    0    3
```

## Paired bootstrap vs. TF-IDF baseline (macro-F1 difference, A − TF-IDF)

| model | mean diff | 95% CI | P(A not better) |
|---|---|---|---|
| majority | -0.072 | [-0.117, -0.031] | 1.000 |
| verb_rule | +0.075 | [+0.009, +0.142] | 0.014 |
| MiniLM_lr | +0.002 | [-0.049, +0.056] | 0.466 |
| bge-smen_lr | +0.015 | [-0.039, +0.072] | 0.308 |
| mpnet-base-v2_lr | +0.017 | [-0.041, +0.079] | 0.293 |
| MiniLM_lr+marks | -0.020 | [-0.064, +0.024] | 0.807 |
| bge-smen_lr+marks | -0.010 | [-0.051, +0.029] | 0.676 |
| mpnet-base-v2_lr+marks | -0.009 | [-0.056, +0.037] | 0.641 |
| minilm_finetuned+marks | +0.001 | [-0.047, +0.049] | 0.472 |