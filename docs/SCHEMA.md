# Item format, task cards, answer files and scores

A **decision model** reads a **state** (a text, or a small structure) and one **typed question** (yes/no, one of several options, or a
level) and returns a probability for every option in one forward pass. A **system** is such a model together with the way it is run (in
one pass, or with a thought written before the read-out).

## Folder of a release

```
tasks/<task>/items.jsonl   one item per line
tasks/<task>/task.json     the task card
tasks/<task>/README.md     what the task is, how it was made, examples
```

The scorer reads the folder given by `--root` (default `data/`). Answer files live elsewhere, one folder per system:
`runs/<system>/<task>.jsonl`.

## items.jsonl: one request per line

```json
{"id": "<task>:<stable id>[:<variant>]",
 "state": "<string>" | {"...": "..."},
 "questions": {"q": {"type": "choice" | "score" | "noul",
                     "instructions": "<the question>",
                     "criteria": {"<key>": "<text>", "...": "..."} | ["level 0", "level 1", "..."]}},
 "gold": "<key of the correct option>" | <level index> | null,
 "soft": {"<key>": <probability>, "...": 0.0} | null,
 "group": "<id shared by the rows that belong together>" | null,
 "meta": {"source_id": "...", "level": 1, "deviation": "...", "...": "..."}}
```

- `state` and `questions` are exactly what is sent to a decision model (the request fields of a typed-decision API), one question per
  item, always under the key `q`. The options, their order and their wording are frozen in the file. Yes/no questions use the keys `yes`
  and `no`. For a list of level texts (`score` questions) the keys are `"0"`, `"1"`, ...
- `gold` is the key of the correct option. `soft` is used instead when the truth is a probability (the two capability-boundary tasks,
  whose label is the success rate of a named chat model); exactly one of the two is set.
- `group` ties together the items that are scored together. `group_kind` in the task card says which kind:
  - **contrast group** (`contrast`): the same case with one planted difference, for example a log with a claim that is right and the
    same log with a claim that is off by one. The members differ in what is true, not in how it is worded.
  - **ranking group** (`ranking`): all candidates of one query (the two reranking tasks).
- `meta` keeps what is needed to trace an item to its source. A core item also holds `level` (1, 2 or 3), `domain`, `deviation` (the kind
  of the planted difference, or null for the member without one), the option order and `spec`, the structured specification from which
  the generator rendered the text and computed the answer.

**Levels.** Every core family has 200 items on each of three levels. Level 1 has few elements of each kind; level 3 needs at least four
computation steps or three facts from different parts of the state ([`GENERATORS.md`](GENERATORS.md)).

## task.json: the task card

| field | meaning |
|---|---|
| `task`, `layer`, `title`, `decision` | name, layer (A to G), one-line title, what is decided in plain words |
| `source` | name, address, files, split and version of the source (for a core family: the generator and its seed) |
| `licence`, `redistribution` | the licence as the source states it; `items included`, `items included (share-alike)` or `rebuild script only` |
| `labels`, `item_source` | `human`, `programmatic` or `mixed: ...`; `public test set`, `new labels on public inputs` or `generated` |
| `metric`, `chance` | `accuracy`, `auroc`, `ndcg@10`, `pair_accuracy` or `mse_soft`, and its chance level |
| `rows`, `groups`, `options`, `question_type` | number of items, of groups, the largest number of options, the question type |
| `notes` | what a reader must know: label caveats, filtering, what was dropped and why |
| `track` | `core` or `reference` |
| `version`, `items_sha256` | version of the item set of the task and the SHA-256 of `items.jsonl`; a run made on other items does not count |
| `accepts_items_sha256` | release 1.3 only: hashes of earlier item sets of which this one is a subset; a run made on them still counts (read by id) |
| `group_kind` | `contrast`, `ranking`, or null |
| `exposure` | reference tasks: per system, whether its published training list names the source of the task or a data set of its family (`exposed`, `not_named`, `unknown`) |
| `skill`, `knobs` | core families: the skill in one line and the difficulty dials |
| `family_set` | release 1.3: `decidebench` for the 13 families of the core track (the identifier keeps the first name of the benchmark) |
| `build` | where the folder was assembled from and the checks that were applied |

## Answer files

One file per system and task, `runs/<system>/<task>.jsonl`, one line per item:

```json
{"id": "<item id>", "p": {"<key>": 0.7, "<key>": 0.3}}
{"id": "<item id>", "answers": {"q": {"type": "choice", "choice": "<key>", "probabilities": {"<key>": 0.7, "<key>": 0.3}}}}
{"id": "<item id>", "error": "<what went wrong>"}
```

- The first form is the short one. The second is the answer object of a typed-decision request (for `noul` questions
  `{"type": "noul", "noul": P(yes)}`; for `score` questions `{"type": "score", "score": ..., "probabilities": {"0": ..., "1": ...}}`).
- Probabilities are normalised over the options of the item, so unnormalised scores are fine; a missing key counts as 0.
- A line with `error`, and an item without a line, counts as unanswered: it gets the uniform distribution and is wrong.
- Extra fields are ignored. A run with a thought may add `tokens` (the length of the thought), `closed` (whether the thought ended by
  itself) and `thought` (whether the model thought on the item); the scorer reports their means.
- A run counts for a task only if at least 99% of its items have a line and, for a generated family, it was made on the items of this
  version: the runners write the SHA-256 of every items file they ran on into `runs/<system>/_items.json` (`{"<task>": "<sha256>"}`).
- Every item gets one answer from the model's own probabilities. Nothing is fitted to the benchmark.

## Scores

The **top option** of an item is the option with the largest probability (the first listed wins a tie) and the **top probability** is its
probability; an item is **right** when its top option is the gold option. Percentages are reported as points (x 100).

- **accuracy**: the share of items that are right. 7 of 10 items right: 70.0.
- **pair accuracy**: the share of contrast groups in which every member is right. Two pairs, both members right in the first and one in
  the second: accuracy 75.0, pair accuracy 50.0.
- **pair direction**: for yes/no pairs, the share of pairs in which the member whose truth is yes gets a higher P(yes) than the member
  whose truth is no (a tie does not count). P(yes) 0.8 against 0.3 counts, 0.4 against 0.6 does not: 50.0 for these two pairs.
- **accuracy and pair accuracy per level**: the same on the items of level 1, 2 and 3; *level 3* in the tables is the pair accuracy on
  level 3.
- **auto_at_5, auto_at_1**: the largest share of the items that can be decided automatically while the error rate among the decided items
  stays at or below 5% (1%). Items are sorted by top probability, highest first; items with the same probability enter together; the score
  is the longest prefix that meets the target. Ten items, the eight most confident without an error and the ninth wrong: the prefix of
  nine has 11% errors, so auto_at_5 is 80.0.
- **acc_at_090, share_at_090**: the accuracy among the items whose top probability is at least 0.90, and their share of all items. 5 of
  10 items reach 0.90 and 4 of those are right: acc_at_090 = 80.0 with share 50.0.
- **aurc**: area under the risk-coverage curve, the mean over the items of the error rate of the prefix in which the item enters (sorted
  as above). 0 is perfect. Right, right, wrong, right in the order of confidence: error rates 0, 0, 1/3, 1/4, aurc = 14.6.
- **trigger_recall_20**: the share of the errors that lie among the 20% of items with the lowest top probability.
- **calibration error**: 15 equal-width bins of the top probability; the sum over the bins of |sum of top probabilities - number right|,
  divided by the number of items. Every item at 0.90 and 70% right: 20.0.
- **Brier score, log score, AUROC, nDCG@10, skill**: per task as its metric needs. `mse_soft` tasks report the skill
  1 - mse / mse of the best constant, with the sampling noise of the label removed.
- **tokens, thought share**: mean thought length (0 for an item without a thought) and the share of items with a thought.

**Aggregates.** The core headline is the mean of each score over the 13 families. A reference task's value is put on a common scale,
score = 100 x (value - chance) / (1 - chance) (skill as it is); a layer score is the mean of the task scores floored at 0, and the
reference total is the mean of the seven layer scores.

**Intervals.** 95% percentile bootstrap, seed 20261007, 1,000 resamples (`--resamples`). Where a task has groups the groups are
resampled, not the items, and the same resamples are used for every system, so differences between systems are paired. The tables give
no interval for the calibration error, because resampling widens the per-bin gaps that it sums.

## Layers

A before generation (routing, capability boundary, abstention, well-posedness) · B guards (safety, jailbreak, prompt injection, rules) ·
C after generation (grounding, verification, judging, reward) · D agent loop · E classification that needs reasoning · F data pipelines ·
G search and matching.
