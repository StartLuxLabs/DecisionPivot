# DecisionPivot

**Evaluating decision models at the control points of LLM systems.**

DecisionPivot was called DecideBench until 14 October 2026. The items and their hashes did not change.

A *decision model* reads a case, the *state*, and a typed question with a fixed set of options, and returns a probability for every option
in one forward pass. LLM systems use such models to route requests, guard tool calls, check outputs and decide when a case goes to a
person. DecisionPivot measures whether these decisions are right, whether they stay right when one decisive detail of the case changes, and
how much of the work a model can take over at a fixed error rate.

This repository holds the code of the benchmark: the generators and independent solvers of the core track, the audits, the scorer, the
runners, rebuild scripts for 13 of the reference tasks, the task cards and hashes of every release, and tests.
The items themselves are distributed through the Hugging Face dataset (see [Get the items](#get-the-items)).

> **Evaluation only.** The items must never be used as training data or put into the prompts of a model that is being trained. Some
> reference tasks of layer B contain harmful text by design, as data to classify.

## The benchmark at a glance

| | core track | reference track |
|---|---|---|
| what | 13 program-generated families | 35 public test sets converted to the same request format |
| items | 7,800 (600 per family, 200 on each of three levels) | 34,104 in release 1.1, 32,233 in release 1.3 |
| answers | computed by the generator, re-derived by an independent solver | the labels of the source |
| structure | contrast groups: the same case two to four times, with one planted detail that changes the answer | as in the source |
| main scores | accuracy, pair accuracy, level-3 pair accuracy, automation at 5% error, accuracy at 0.90, calibration error | the metric of the source, chance-corrected, averaged per layer |

The 48 tasks follow the seven places where a decision sits in an LLM system:

| layer | decision point | core families | reference tasks |
|---|---|---|---:|
| A | before generation: can the request be answered, will a named model answer it | `answerable_facts` | 6 |
| B | guards: is the request allowed under written rules, is it unsafe | `perm_inherit`, `policy_case` | 7 |
| C | after generation: is the claim or the response right | `log_count_check` | 8 |
| D | agent loop: is the tool call valid, is the goal reached | `sched_conflict`, `state_goal`, `toolcall_valid`, `triage_order` | 3 |
| E | classification that needs reasoning | `clause_change`, `dep_resolve` | 4 |
| F | data pipelines: do the records obey the rules | `ledger_reconcile`, `record_rule` | 1 |
| G | search and matching | `filter_match` | 6 |

[`docs/TASKS.md`](docs/TASKS.md) lists every task with its question, size, labels, metric and licence status.

**Contrast groups and pair accuracy.** Every core item belongs to a contrast group whose members differ only in one planted detail, for
example a shipping fee that puts the price plus shipping one cent below or above a limit. *Pair accuracy* is the share of groups in which
every member is answered right. A model that answers from the surface of the case gets about half of the items of a yes/no pair right and
almost none of the pairs: saying yes to both members of every pair gives accuracy 50 and pair accuracy 0.

**Selective decisions.** A system acts on the probability a decision model returns. The scorer therefore also reports *automation at 5%*
(the largest share of the items a system can decide alone, most confident first, with at most 5% of those decisions wrong), *accuracy at
0.90* (accuracy, and share, of the items whose top probability is at least 0.90) and the calibration error. All scores are computed from
the model's own probabilities; nothing is fitted to the benchmark.

## Repository layout

```
generators/   one seeded generator per core family (<family>.py) and regenerate.py, which rebuilds and verifies them
solvers/      one independent solver per core family, written without reading the generator; it sees only state, question and options
audits/       validate.py (format), solve_all.py (solver agreement), audit.py and audit_v3.py (content-blind rules), key_balance.py
scoring/      score.py (all scores and tables), compare.py (paired comparison), check_data.py (hashes), derive_v13.py (release 1.3)
reference/    rebuild.py and build/: scripts that rebuild 13 reference tasks from their official sources
runner/       bench_http.py (typed-decision endpoint) and chat/ (chat models through an OpenAI-compatible API)
releases/     task cards (task.json) and SHA-256 hashes of releases 1.1 and 1.3, the lists of dropped item ids
docs/         TASKS.md, SCHEMA.md (item, task card and answer formats, every score), GENERATORS.md, AUDIT.md, CHANGES.md
tests/        unit tests of the scorer, tests on sample items (two contrast groups per family), a regeneration test
```

Everything runs with Python 3.9 or newer and the standard library (the published hashes were reproduced with Python 3.9.6); the commands
below are run from the repository root. Optional: `numpy` for `audits/audit_v3.py`, `pyarrow` for three reference rebuilds,
`huggingface_hub` to download the items.

## Get the items

The items are on the Hugging Face dataset [startlux-models/DecisionPivot](https://huggingface.co/datasets/startlux-models/DecisionPivot). Access is gated: open
the dataset page, request access and accept the conditions (evaluation only). Then download it into `data/`, the folder the scorer and
the runners read by default, and compare it with the published hashes:

```bash
pip install -U huggingface_hub
hf auth login                                   # with your own access token
hf download startlux-models/DecisionPivot --repo-type dataset --local-dir data
python3 scoring/check_data.py                   # release 1.1: SHA-256 and size of every items file
```

The dataset holds release 1.1: the core items and the items of all 35 reference tasks, which stay under the licences of their sources.
13 reference tasks can also be rebuilt from their official sources with `reference/rebuild.py` (see [below](#rebuild-reference-tasks-from-their-sources)).
The paper reports the reference track on release 1.3, which drops 1,871 items that were found in the training data of our final models;
derive it from release 1.1 with

```bash
python3 scoring/derive_v13.py --root data --out data_v13
python3 scoring/check_data.py --root data_v13 --version 1.3
```

The core track does not need the download at all: it can be generated again from the seeds.

## Generate the core items again and verify them

Every core family is a Python script without arguments or inputs. It draws a structured case from `random.Random(20261007)`, computes
the answer from the case, plants one detail per contrast group and renders the state. The generators assert their own invariants (class
and level balance, one planted detail per negative, no second reading, no class-marking vocabulary). For each family a second author who
had not read the generator wrote an independent solver that reads only the rendered state, the question and the options.

```bash
python3 generators/regenerate.py --check                         # all 13 families: about 5 minutes on a laptop
python3 generators/regenerate.py perm_inherit dep_resolve --check
python3 generators/perm_inherit.py                               # one family, written to generated/tasks/perm_inherit/
```

`regenerate.py` writes `generated/tasks/<family>/`, compares the SHA-256 of every items file with release 1.1 and, with `--check`, runs
the solver (all 600 answers must agree), the format check, the content-blind rules and the key balance. The output looks like this:

```
family                  seed seconds  items  release 1.1 hash  solver     validate audit    keys
perm_inherit       published     7.7    600  identical         600/600    OK         no flag    PASS
dep_resolve        published     2.5    600  identical         600/600    OK         no flag    PASS
ALL CHECKS PASSED
```

`--install data` copies the families that match the release into `data/tasks/` with their task cards, so the core track can be scored
without the download. The bag-of-words audit needs numpy and takes about ten minutes: `python3 audits/audit_v3.py` (default folder
`generated/`; `--root data` audits the downloaded items). [`docs/AUDIT.md`](docs/AUDIT.md) has the results for release 1.1, [`docs/GENERATORS.md`](docs/GENERATORS.md) the
design rules of the generators and of each family.

**Fresh draws.** Seven generators take a second seed (`clause_change`, `dep_resolve`, `ledger_reconcile`, `perm_inherit`, `record_rule`,
`sched_conflict`, `triage_order`). A new set of 600 items per family, with ids `<family>:s<K>:...`, is drawn and checked with

```bash
python3 generators/regenerate.py --seed 7 --check                # writes generated/seed_7/tasks/<family>/
```

The same is possible for one script: `BENCH_OUT=<dir> BENCH_SEED=<K> python3 generators/<family>.py` writes `<dir>/<family>/`. Such a
draw can serve as a sealed set when the published items may have leaked.

## Rebuild reference tasks from their sources

```bash
python3 reference/rebuild.py --list
python3 reference/rebuild.py paws ~/decisionpivot-cache                       # release 1.1
python3 reference/rebuild.py mind2web_element ~/decisionpivot-cache --version 1.3
```

Each build script fetches its source files from a pinned commit or address into the cache folder, checks their SHA-256, converts them,
and `rebuild.py` drops the items that the release does not hold, compares the result with the hash of the release and writes
`data/tasks/<task>/`. [`reference/README.md`](reference/README.md) gives the inputs of every task; the two reranking tasks need a checkout
of the reranking test and the BEIR files, and the two capability-boundary tasks need stored sampled answers of four public chat models,
which are not part of this repository.

## Run a model

A system receives one request per item: the item's `state` and `questions` (one typed question under the key `q`, with its options in the
order frozen in the file). These are the request fields of a typed-decision API, so a decision model reads them without a prompt template
of ours. The answer is a probability for every option:

```json
{"id": "policy_case:00007", "p": {"approve": 0.12, "deny": 0.80, "escalate": 0.08}}
```

One answer file per task, `runs/<system>/<task>.jsonl`. The answer object of a typed-decision API (`{"id", "answers": {"q": {...}}}`) is
read as well; a failed item gets `{"id", "error": "..."}`. A runner records the SHA-256 of every items file it ran on in
`runs/<system>/_items.json`, so that the scorer can refuse a run made on other items. [`runner/README.md`](runner/README.md) has the
details, the prompt for chat models and how to read out a model that thinks first.

```bash
# a decision model behind a typed-decision endpoint (POST <url>/v1/systemone)
python3 runner/bench_http.py --url http://127.0.0.1:9701 --model my-decider --out runs/my-decider
# the same against a hosted endpoint that needs a key (read from the environment, never stored)
python3 runner/bench_http.py --url https://decider.example.com --model my-decider --out runs/my-decider --api-key-env DECIDER_API_KEY
# a chat model through an OpenAI-compatible API, asked for a probability of every option (core track)
python3 runner/chat/run_api.py --keyfile path/to/keyfile --base-url https://api.example.com/v1 --model my-chat-model --reasoning off --out raw.jsonl
python3 runner/chat/collect.py raw.jsonl my-chat-model           # writes runs/my-chat-model/<family>.jsonl
```

## Score

```bash
python3 scoring/score.py my-decider=runs/my-decider             # every task found in data/tasks/
python3 scoring/score.py my-decider=runs/my-decider --root data_v13 --tasks perm_inherit,paws,xstest
python3 scoring/score.py --all --runs runs --systems systems.json --out results --jobs 8
python3 scoring/compare.py A=runs/model-a B=runs/model-b        # paired difference on the reference track
```

The single-call form prints, per task, the metric of the task with its 95% interval, the chance-corrected score, the coverage and the
selective scores, and the layer scores of the reference track. `--all` scores every folder of `runs/` and writes `scores.json`,
`report.md`, the tables T1 to T4 (CSV and LaTeX) and `MISSING_RUNS.md`; a system enters the tables when `systems.json` marks it
`"table": true` (for example `{"my-decider": {"name": "My Decider 4B", "table": true}}`).

| score | what it measures | what it catches |
|---|---|---|
| accuracy | items whose top option is right | wrong answers |
| pair accuracy | contrast groups with every member right | answers taken from the surface |
| level 3 | pair accuracy on the largest cases | losing track over several steps |
| pair direction | yes/no pairs whose yes member gets the higher probability of yes | a planted detail noticed but weighed too little |
| automation at 5% | the largest share of items decided alone, most confident first, with at most 5% wrong | probabilities that cannot be used to hand cases on |
| accuracy at 0.90 | accuracy (and share) of items with top probability of at least 0.90 | confident errors |
| calibration error | mean gap between stated probability and accuracy over 15 bins | probabilities too high or too low |

The core headline averages each score over the 13 families. A reference score is 100 x (value - chance) / (1 - chance), floored at 0,
averaged per layer; the reference total is the mean of the seven layers. Intervals are 95% percentile bootstraps over contrast groups
(seed 20261007, 1,000 resamples, the same resamples for every system). An unanswered item counts as wrong with the uniform distribution,
and a run that covers fewer than 99% of the items of a task, or was made on other items of a core family, does not count for that task.
[`docs/SCHEMA.md`](docs/SCHEMA.md) defines every score with a worked example.

## Tests

```bash
python3 tests/test_score.py          # 41 unit tests of the scorer, every expected value worked out by hand
python3 tests/test_samples.py        # format, independent solvers and scorer on the sample items (tests/samples/)
python3 tests/test_chat_parse.py     # the reader of chat-model replies
python3 tests/test_regenerate.py     # two families from the published seed and from seeds 1 and 2 (about 40 seconds)
```

## Versions

| release | date | what changed |
|---|---|---|
| 1.0 | 7 Oct 2026 | 13 generated families and 35 converted public test sets; reference items found in our training data removed |
| 1.1 | 8 Oct 2026 | ten core families rebuilt to remove defects found by two AI reviewers and the independent solvers; reference track unchanged. The items of the paper's core track and of the Hugging Face dataset |
| 1.2 | 10 Oct 2026 | items of 1.1 unchanged; four generated families of Open Decision Bench added as a separate set, reported in their own table (not part of the paper's core track or of this repository) |
| 1.3 | 10 Oct 2026 | 1,871 reference items found in the training data of the final StartLux-Decision-27B models removed (32,233 left); core unchanged. The reference track of the paper |

[`docs/CHANGES.md`](docs/CHANGES.md) gives the changes per family with the measured property before and after.

## Citation

```bibtex
@misc{startlux2026decisionpivot,
  title  = {DecisionPivot: A Diagnostic Benchmark for Decision Models in LLM Systems},
  author = {{StartLux Labs}},
  year   = {2026},
  note   = {Preprint}
}
```

## Licence

- **Code.** The code of this repository is released under the Apache License 2.0 ([`LICENSE`](LICENSE)).
- **Core items.** The generated items of the core track are written by the generators of this repository and contain no third-party text;
  they are released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), as stated on the [Hugging Face dataset card](https://huggingface.co/datasets/startlux-models/DecisionPivot). The
  sample items in `tests/samples/` are part of that release and are under the same terms.
- **Reference items.** The 35 reference tasks are not ours: they are public test sets created by other authors and converted to
  the item format. Their copyright stays with those authors, and each task follows the licence of its source, named with the source
  in the `licence` field of its task card. Please cite the original data sets when you use them.

See [`NOTICE`](NOTICE) for the attribution notices.
