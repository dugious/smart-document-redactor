# Evaluation protocol and observed results

## Scope

Synthetic English text detection only. **Not a measurement of PDF extraction/redaction performance, legal compliance or real-world accuracy.** Data authored with inline gold tags in `build_dataset.py`, not labeled using detector predictions. 6 dev documents and 24 test documents; test has 1,440 characters and 35 gold entities. No training/fine-tuning, so no train split. Person names and complete texts differ across splits; structural patterns are still related and not statistically independent. Names are fictional scenario identifiers, not actual customer records; coincidental real-name matches are possible. Email example domains, fictional phone ranges and sandbox card numbers only.

Frozen initial test includes known unsupported cases (international/unformatted phones, full postal addresses, lowercase address and PO box), deliberately retained as false negatives rather than excluded for better scores. Complete address gold includes city/state/postcode when present; partial street prediction is one FP and one FN under exact matching. No confidence threshold tuning or detector changes after reading test scores. Dataset is small, manually authored by the same developer and not independently annotated; not a blind or representative production test.

## Metrics

Match `(type, start, end)` exactly within each document. Deduplicate identical predictions. A boundary/label mismatch counts FP + FN. Aggregate counts before computing micro scores. Zero denominator -> 0. Report support; no claim about unsupported/absent classes from a zero score. PERSON PER/PERSON normalized by existing adapter; no LOC -> ADDRESS. Same regex and priority resolution for both models.

## Reproduction

From project root, after installing NLP extras and local models per README:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe evaluation/run.py --backend spacy --dataset evaluation/test.jsonl --repeats 3
.\.venv\Scripts\python.exe evaluation/run.py --backend transformers --dataset evaluation/test.jsonl --repeats 3
```

Do not regenerate/change test to improve scores. Use `--dataset evaluation/dev.jsonl` for future development; mark future test scores as reused test rather than unseen evaluation. Each invocation replaces the report for that split/backend. Raw text and predictions are not copied into reports; reports include counts, dataset/source/model SHA256 hashes, package versions, provenance, machine and timings.

spaCy en_core_web_sm 3.8.0 with spaCy 3.8.16. Transformers 4.57.6 / torch 2.14.0 CPU, dslim/bert-base-NER commit `d1a3e8f13f8c3566299d95fcfc9a8d2382a9affc`, recovered from matching metadata for all five downloaded files; download script now pins this revision. File hashes in reports identify the actual loaded local artifacts (metadata alone is not an integrity guarantee).

## Observed initial run

Percentages, exact span/entity matching:

| Type | Support | spaCy P | spaCy R | spaCy F1 | Transformers P | Transformers R | Transformers F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| PERSON | 13 | 90.00 | 69.23 | 78.26 | 100.00 | 100.00 | 100.00 |
| EMAIL | 5 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 |
| PHONE | 6 | 100.00 | 66.67 | 80.00 | 100.00 | 66.67 | 80.00 |
| CREDIT_CARD | 4 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 |
| ADDRESS | 7 | 80.00 | 57.14 | 66.67 | 80.00 | 57.14 | 66.67 |
| **Micro** | **35** | **92.86** | **74.29** | **82.54** | **96.77** | **85.71** | **90.91** |

PERSON 100% here means only 13 of 13 tiny synthetic examples matched; **not 100% accuracy in general**. spaCy PERSON has TP9/FP1/FN4. Transformers PERSON TP13/FP0/FN0. Structured counts are identical as intended.

| Backend | Model load seconds | Median detection seconds, entire 24-doc set |
|---|---:|---:|
| spaCy | 4.825 | 0.150 |
| Transformers CPU | 8.943 | 2.405 |

Windows 11 build 26200, Python 3.13.14; CPU reported by OS `Intel64 Family 6 Model 126 Stepping 5, GenuineIntel`, 8 logical CPUs; physical RAM reported 12,640,931,840 bytes (~11.77 GiB). CPU only. Model load measured once; detection has one fixed warmup excluded and median of 3 sequential full-dataset runs. Detection includes both NER and regex/overlap, excludes model load, dataset reading, file hashing, PDF handling and UI. No cross-run CPU-load control or statistical confidence intervals; speed varies by machine/background work.

Evidence: `results/test-spacy.json` and `results/test-transformers.json`. These are real executed results, not targets.
