# Literature Baseline

Source: Ramar, G., Sivasakthivel, R., Stephen, R., Siva Balan, R.V., Sahu, M. "Modern Approaches For
Automatic Question Paper Generator." 2025 International Conference on Computing Technologies & Data
Communication (ICCTDC), Hassan, India, Jul 2025. IEEE. (Christ University, Seed Money Scheme
CU-ORS-SM-24/87.)

This document summarizes what the reference paper actually claims, so later design decisions can be
checked against it rather than against assumption. It is a **survey paper**, not a system paper: it
contains no original model, no code, and no dataset of its own. It reviews and tabulates ~25 prior
studies across five technique families, all evaluated on question *generation* (not paper assembly)
using BLEU-4 / METEOR / ROUGE-L against the SQuAD reading-comprehension dataset.

## 1. The five approach families it surveys

### A. Rule-based
Semantic role labelling, dependency parsing, POS tagging (NLTK, Stanford NER, Porter Stemmer),
hand-written transformation rules (e.g. S-V-ARGM-CAU → causal question). Strengths: structured,
predictable, no training data needed. Weaknesses (explicit in the paper): fail to provide variety and
flexibility, syntactic rigidity, poor generalization across subjects. Best reported metric: SRL-based
[8], METEOR 25.01 on SQuAD.

### B. Encoder–decoder (Seq2Seq)
LSTM/GRU/BiGRU/BiLSTM sequence-to-sequence models, later augmented with attention, copy/coverage
mechanisms, and graph encoders (GA-Seq2Seq [13] fuses a graph encoder with sequence encoder to capture
structure the sequence-only view misses). Trained end-to-end on paired (passage, question) data.
Requires large parallel corpora. Best reported: GA-Seq2Seq [13] on MS MARCO, BLEU-4 21.79.

### C. Generative Adversarial Networks (GAN)
Generator/discriminator competition (Goodfellow et al. [15], foundational, not QG-specific) applied to
QG for diversity: "seq2seq + z + c + GAN" [17] adds a latent diversity variable and an observed
type-control variable; DoubAN [18] uses two discriminators (domain classifier + QA model) for
cross-domain QG when labelled target-domain data is scarce. Explicit paper finding: GAN performance is
**inconsistent** across studies (BLEU-4 ranges 5.48–17.61 in Table I), and the paper explicitly notes
BLEU alone is insufficient to judge grammaticality/relevance for these models.

### D. Reinforcement Learning (RL)
Motivated by exposure bias in MLE-trained Seq2Seq. Task-specific reward models: fluency via LM
perplexity, relevance via a BERT classifier, answerability via a SpanBERT QA model [22]; graph-to-seq +
RL with a Deep Alignment Network for answer-awareness [19]; answer-driven RL with Graph Attention
Networks for multi-hop reasoning [21]. Explicit paper caveat: **answerability rewards can introduce
bias** — optimizing directly for a QA model's success does not guarantee the reward matches human
judgment of question quality [22].

### E. Transformer-based
Self-attention removes recurrence (Vaswani et al. [23], foundational). T5 and GPT-2 fine-tuning
dominate this category: T5 for multi-format QA-pair generation (subjective/boolean/fill-blank/MCQ)
[24][27]; GPT-2 causal-LM fine-tuning with nucleus sampling [25]; GPT-2(generator)+BERT(QA feedback)
hybrids [26]; IRT-conditioned T5/BERT for difficulty-controlled generation via computerized adaptive
testing [28]; genetic-algorithm-tuned T5 with BERT+c-TF-IDF topic modelling for conversational QG [29].
Best reported: T5 [24], BLEU-4 18.87 / METEOR 25.24, and Transformer-Seq2Seq [27], ROUGE-L 49.66.
**The paper's own conclusion ranks transformer-based approaches highest** on these metrics among the
five families.

## 2. Cross-cutting findings the paper states explicitly

- **Metrics used throughout**: BLEU-4, ROUGE-L, METEOR, almost exclusively on SQuAD (a
  reading-comprehension QA dataset, not an exam/question-paper dataset).
- **Focus-area classification (Table II)**: most papers optimize fluency & accuracy and contextual
  relevance; question variability is the next most common focus (mostly GAN/RL papers); computational
  efficiency is addressed by only a few; **"Expert & user assessment" is the least explored dimension**
  of all — only 2 of ~19 classified papers report any human/expert evaluation.
  - Reference to Christ University's own prior seed-money-funded output is worth reading in that
    light: absence of human evaluation as an industry-wide gap directly motivates §50 (human evaluation
    protocol) in this project's own design.
- **Stated conclusion**: "modern tools ... are not accurate and take much time," "some ... give
  irrelevant information," transformer models are the clear metric leader, and the paper's own
  suggested future work is **"context-aware question generation and human-in-the-loop evaluation."**

## 3. Scope boundary — what this paper does NOT cover

Explicitly absent from the survey (confirmed by close reading, not inferred):

- No curriculum/syllabus modeling, no unit/topic/learning-outcome structure.
- No treatment of an entire **question paper** as the unit of generation — every technique reviewed
  generates one question (optionally with an answer) from one passage. Assembling many questions into
  a constrained, balanced paper is out of scope.
- No Bloom's taxonomy or Webb's DOK classification anywhere in the review.
- No difficulty modeling, psychometric modeling (IRT is mentioned once, in [28], as a way to condition
  *generation* on a target difficulty — not as an evaluation or calibration framework).
- No novelty/repetition detection against a historical corpus.
- No multi-objective constraint optimization over marks/units/cognitive levels.
- No adversarial validation of generated content for hallucination, ambiguity, or answer leakage.
- No teacher feedback loop or preference learning.
- No treatment of institutional historical exam papers as a dataset type (all reviewed work uses
  SQuAD/MS MARCO/HotpotQA/TyDiQA/CoQA — generic reading-comprehension corpora, not exam archives).

This scope boundary is the basis for [`RESEARCH_GAP.md`](RESEARCH_GAP.md): every item in that list is a
component this project must design and justify independently, because the cited literature is silent
on it.
