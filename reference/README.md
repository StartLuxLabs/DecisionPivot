# Rebuilding reference tasks from their sources

For 13 of the 35 reference tasks, these scripts rebuild the items from the official files of each source. The items of all 35 tasks are also in
the dataset, under the licences of their sources. Everything here is for evaluation only: the rebuilt
items must never be used as training data or put into the prompts of a model that is being trained.

```bash
python3 reference/rebuild.py --list                                     # the 13 tasks, their sizes and inputs
python3 reference/rebuild.py paws ~/decisionpivot-cache                   # release 1.1 into data/tasks/paws/
python3 reference/rebuild.py paws ~/decisionpivot-cache --version 1.3     # release 1.3 (the items the paper scores)
python3 reference/rebuild.py paws --no-build --version 1.3 --out data_v13   # reuse the raw output of an earlier build
```

`rebuild.py` runs the build script of the task (its raw output goes to `generated/reference/tasks/<task>/`), drops the items that the
release does not hold, and compares the number of items and the SHA-256 with the task card of the release in `releases/`. Only if both
agree does it write `data/tasks/<task>/` (or `--out DIR`): `items.jsonl`, the task card as `task.json` and the README of the build script.
The dropped items are those found in the training data of the authors' models (`releases/v1.1/build_drops.json`, scan of 7 October 2026,
and `releases/v1.3/dropped_from_v1.1.json`, scan of 10 October 2026), and those dropped with them to keep the classes balanced.

## Inputs

Most build scripts take a download folder (`CACHE_DIR`): every source file is fetched from a pinned commit or address when it is not
there yet, and its SHA-256 is checked, so a changed source stops the build instead of giving other items. They need network access;
three need `pyarrow` to read Parquet files. The terms of each source apply to what it downloads; the task card names the licence.

| task | script | source files | input |
|---|---|---|---|
| `freshqa_premise` | `build_freshqa_premise.py` | FreshQA (github.com/freshllms/freshqa): the CSV export of the Google Sheet "FreshQA April 21, 2026", tab `freshqa` | CACHE_DIR |
| `faithbench` | `build_faithbench.py` | github.com/vectara/FaithBench at commit `cf89797`: `data_for_release/batch_*.json`, `FaithBench.csv` | CACHE_DIR |
| `rewardbench` | `build_rewardbench.py` | huggingface.co/datasets/allenai/reward-bench at commit `168d848`: the `filtered` split | CACHE_DIR, pyarrow |
| `agentreward_success` | `build_agentreward_success.py` | huggingface.co/datasets/McGill-NLP/agent-reward-bench at commit `b6d17e6`: `data/annotations.csv` and the 1,302 judge files of one judge (text only) | CACHE_DIR |
| `mind2web_element` | `build_mind2web_element.py` | huggingface.co/datasets/osunlp/Multimodal-Mind2Web at commit `1b4c6a8`: eight Parquet shards of the test splits, up to 300 MB each (text columns only) | CACHE_DIR, pyarrow |
| `label_errors` | `build_label_errors.py` | github.com/cleanlab/label-errors at commit `6d5d6b3` (annotations) and the 2,403 text files they name on labelerrors.com | CACHE_DIR |
| `entity_match_abt_buy` | `build_entity_match_abt_buy.py` | the DeepMatcher version of Abt-Buy (archive listed in github.com/anhaidgroup/deepmatcher, Datasets.md) | CACHE_DIR |
| `entity_match_amazon_google` | `build_entity_match_amazon_google.py` | the DeepMatcher version of Amazon-Google (same archive host) | CACHE_DIR |
| `paws` | `build_paws.py` | huggingface.co/datasets/google-research-datasets/paws at commit `161ece9`: `labeled_final` test split | CACHE_DIR, pyarrow |
| `rerank_nfcorpus`, `rerank_scifact` | `build_rerank.py` | the item file of the reranking test, see below | RR_ITEMS |
| `cap_boundary_card`, `cap_boundary_record` | `build_cap_boundary.py` | the pilot file of the capability-boundary tasks, see below | PILOT |

The full commit hashes, file names and SHA-256 values are in the scripts (constants at the top) and in the `source` field of each task
card.

### The two reranking tasks

The candidates come from the public reranking test github.com/dchristopoulos/system1-rerank-bench (MIT): 100 test queries each of BEIR
SciFact and NFCorpus with the 50 hybrid-search candidates that every system of that test reranked. The texts and relevance judgments come
from BEIR.

```bash
git clone https://github.com/dchristopoulos/system1-rerank-bench REPO_DIR
# BEIR_DIR/scifact/ and BEIR_DIR/nfcorpus/: corpus.jsonl, queries.jsonl and qrels/test.tsv of the two BEIR data sets
python3 reference/build/rr_build.py REPO_DIR BEIR_DIR rr_items.json
python3 reference/rebuild.py rerank_scifact rr_items.json --version 1.3
python3 reference/rebuild.py rerank_nfcorpus --no-build --version 1.3      # the same build wrote both tasks
```

`rr_build.py` checks the SHA-256 of the BEIR files against the manifest of the reranking test. The test repository was read on 6 October
2026 and is not pinned to a commit; if it has changed since, the hash check of `rebuild.py` reports a mismatch.

### The two capability-boundary tasks

Their label is a success rate: the share of 16 or 32 sampled answers of a named public chat model (Gemma 3 4B, Gemma 3 12B, Phi-4-mini,
Phi-4) that match the gold answer of an evaluation question (NQ, PopQA, WebQuestions, TriviaQA; BBH tasks, StrategyQA, FOLIO,
ProofWriter, DROP; SVAMP, ASDiv, GSM-Hard, GSM-Plus, MAWPS). The sampled answers are our own runs of those models and are not part of this
repository, so these two tasks cannot be rebuilt from public files alone. `build/capb_build.py` documents how the pilot file was made from
the question files and the stored samples (`--questions DIR --samples DIR`), and `build/build_cap_boundary.py` turns the pilot file into
the two tasks:

```bash
python3 reference/build/capb_build.py PILOT_DIR --questions QUESTIONS_DIR --samples SAMPLES_DIR
python3 reference/rebuild.py cap_boundary_card PILOT_DIR/capb_items.jsonl
python3 reference/rebuild.py cap_boundary_record --no-build
```

## What has been checked

The selection and hash check of `rebuild.py` reproduces releases 1.1 and 1.3 of `rerank_nfcorpus`, `rerank_scifact`, `label_errors` and
`entity_match_amazon_google` from the converted items of release 1.0. The build scripts are the ones that produced release 1.0 (only their
output folder changed); they were not run again from this repository, because that needs the downloads above.
