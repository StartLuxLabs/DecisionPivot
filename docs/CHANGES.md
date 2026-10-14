# Version history

Every release fixes its items by the SHA-256 of each items file (`releases/v<version>/index.json`). A family or task whose items change
gets a higher `version` in its task card, and the scorer does not count an answer file made on other items.

## Release 1.3 (10 October 2026)

- **Reference track.** Every item found in the training data of the final StartLux-Decision-27B models was removed, by the rule that
  built release 1.0 (no item our models trained on stays in the benchmark). The scan covered all 46 training files of those models
  (3,252,020 records, every stage from the first supervised stage to the prompt pool of reinforcement learning); an item counts as seen
  when a field other than fixed task wording is contained in a training record. 705 of the 34,104 reference items had such a field.
  Removed: 1,782 items that were seen or in a group with a seen item, and 89 more to restore the class balance, 1,871 in all, from 28 of
  the 35 tasks (`releases/v1.3/dropped_from_v1.1.json`). The reference track keeps its 35 tasks with 32,233 items. Tasks that lost more
  than 15%: `bfcl_relevance` 176 -> 144, `cuad_clause` 320 -> 192, `rerank_scifact` 5,000 -> 3,900 (22 of 100 queries, because one
  candidate passage of each was in the training data).
- **Task cards.** Every changed card has new `rows`, `groups`, `items_sha256`, a `version` one higher, a note, and
  `accepts_items_sha256` with the hash of release 1.1: an answer file made on the release 1.1 items (a superset) still counts and is read
  by id. The exposure flags of the cards gain the entry `ours_final27` (exposed when at least 3% of a task's items were found: 16 tasks).
- **Core track.** Unchanged; none of the 7,800 core items was found in the training data.
- The paper reports the reference track on these items. `scoring/derive_v13.py` derives them from a copy of release 1.1.

## Release 1.2 (10 October 2026)

- Every item of release 1.1 unchanged. Four generated families of Open Decision Bench were added as a separate set of generated families
  (`family_set` = `odb`, reported in their own table); they are not part of the core track of the paper and not part of this repository.
- The scorer reports the generated families of each set in their own headline table and the share of items with a thought in table T4.

## Release 1.1 (8 October 2026)

The reference track and three core families (`clause_change`, `dep_resolve`, `perm_inherit`) keep their items byte for byte. The other ten
core families come from corrected generators, after two AI reviewers had answered 65 items of release 1.0 (both agreed with every key) and
listed defects, and after the independent solvers had found a cue in one family. The defects change no key, but they give a model a cue or
make an item read as artificial. Each change was based on a measured property of the items, measured with the same script before and
after, and none on the score of any system. Every family now has `meta.level` 1 / 2 / 3 with 200 items each, and `state_goal` and
`toolcall_valid` now carry contrast groups, so pair accuracy covers all 13 families.

| family | what was fixed | before -> after |
|---|---|---|
| `filter_match` | the day-count rule was not stated in requests that count days | stated in 0 of 532 -> in 546 of 546 |
| | wording that names another field (for example "comes from" next to `ships_from`) | 376 items -> 0 |
| | implausible prices and specs (list price below price, unit prices, out-of-range specs, shipping fees) | 52 / 2,388 of 3,450 specs / 131 -> 0 |
| `state_goal` | the description of the steps was false for some step | 471 of 600 items -> 0 |
| | pseudo-word names, purposeless step patterns | 94% / 85% -> 0 / 0, goal-directed traces 31% -> 92% |
| | negatives whose failing condition no step touches (a cue found by the independent solver) | 66 of 300 negatives -> 0 |
| `policy_case` | rules against the direction of risk | 338 of 1,608 rules -> 0 (exceptions 241 of 514 -> 0) |
| | dead rules, dead exceptions, near-duplicate rules | 294 / 116 / 104 -> 0 |
| | unread risk flags, inconsistent field pairs | 290 / 137 records -> 0 |
| `record_rule` | derived fields inconsistent outside the planted violation, references dated before what they name | 531 rows in 56 items / 1,270 rows in 365 items -> 0 |
| | the status convention of reference lists left implicit | written in all 420 states with a status column |
| `triage_order` | time columns that contradict each other | 107 items -> 0 |
| | a class-first reading gives the key | level 1: 37% -> 0%, level 2: 14.5% -> 12.5%, level 3: 9.5% -> 7.5% |
| `log_count_check` | "exactly 1 ERROR entries", claims open to an at-least reading | 78 items -> 0, "exactly" in 1 of 5 phrasings -> 5 of 5 |
| | the stated count as a cue | best per-level rule on the stated count 0.535 -> 0.505 |
| `sched_conflict` | negatives decided by a cheap check of hours, seats or equipment | level 2: 60% -> 30%, level 3: 60% -> 15% |
| `answerable_facts` | founding years at one clamped value | 25.2% of the years -> 0.17%, distinct years 72 -> 144 |
| | two crossed dials instead of a level ladder | a ladder of three levels |
| `ledger_reconcile` | a ledger named in two ways within one item | 487 items -> 0 |
| | no rule for negative amounts | stated, 260 negative entries, 172 items whose key depends on it |
| `toolcall_valid` | request words equal to a parameter name without referring to it | 198 items -> 0 |
| | filler sentences repeated across items, enum codes copied into the request | 8 sentences -> 44 (at most 12 items each), codes -> language names |

[`AUDIT.md`](AUDIT.md) has the checks that every family of release 1.1 passes and the properties that remain.

## Release 1.0 (7 October 2026)

- 13 generated families and 35 public test sets converted to one request format, in seven layers.
- Each reference task samples at most 1,000 items of its source with the seed 20261007 (100 queries with 50 candidates for the two
  reranking tasks). Items whose text was found in the training data of the authors' models (scan of 32 training files, 1,546,178 records)
  were removed with their groups, and further items to restore the class balance (`releases/v1.1/build_drops.json` lists those of the
  13 tasks that are distributed as rebuild scripts).
