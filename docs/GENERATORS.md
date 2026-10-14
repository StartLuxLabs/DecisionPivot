# The generators of the core track

Every core family is one script, `generators/<family>.py`, and has one independent solver, `solvers/<family>.py`. The script draws a
structured specification of a case, computes the answer from it, plants one detail per contrast group and renders the state. Python 3.9 or
newer, standard library only, no argument, no input file, no network; the module docstring of each script describes its design in full,
and the README.md it writes next to the items lists its checks and shows one item per level.

The task cards of the release name the scripts by their original paths (`build/gen_<family>.py`, `solvers/solve_<family>.py`); in this
repository they are `generators/<family>.py` and `solvers/<family>.py`. Only the paths changed: run from this repository, every script
writes items, task card and README byte for byte as in release 1.1. Comments in the scripts name the development stages: *benchmark
v0* is the draft before release 1.0, *v1* (the first version) and *v2* (the harder second version) are the two designs of four older
families, *gen_v3* the seven newer families as first written, *gen_v4* the corrected generators of release 1.1.

## Rules that every family follows

1. **Script and seed.** `random.Random(20261007)` and generators derived from it; two runs give byte-identical files. The items go to
   `generated/tasks/<family>/` (`items.jsonl`, `task.json`, `README.md`).
2. **Item.** `id` = `"<family>:<number>"`; `state` holds everything that differs between items; `questions.q` = `{"type": "choice",
   "instructions": <the same string for every item of the family>, "criteria": {key: option text}}`; `gold` = key; `group` = the contrast
   group; `meta` = `source_id`, `level`, `domain`, `deviation` (the planted kind, or null), the option order and `spec`.
3. **600 items, three levels.** Exactly 200 items per level. Classes balanced exactly, overall and inside every level; deviation kinds as
   equal as the numbers allow; the position of the gold option balanced.
4. **Truth by code, one planted difference.** The script computes the answer with `truth(spec)` and renders the text from the
   specification. The members of a group are the same specification with one planted difference; the script asserts that a negative breaks
   exactly the planted condition and nothing else, that a positive breaks nothing, and that no item has a second reading. Every convention
   the answer depends on (whether a limit counts, whether touching intervals collide, what is inherited) is written in the state.
5. **Hard for the right reason.** Level 3 needs at least four computation steps or three facts from different places of the state.
   Negatives are near misses (one step beyond a limit, one link of a chain broken); positives sit on a limit or one step inside it as
   often as negatives sit beyond it. Decoys that look like violations but are not appear in both classes.
6. **No surface cue.** The members of a group have the same number of lines and nearly the same length. No word marks a class: no word
   of frequency 20 or more is more than twice as frequent in one class as in the other. Rules that never read the content stay at chance
   (`audits/audit.py`, `audits/audit_v3.py`).
7. **Variety and invented content.** Several domains, phrasings and layouts per family, drawn per item; names of people, companies,
   places and products come from syllable generators or neutral identifiers. No real brands, no real people, no sentence taken from a
   published data set.
8. **Truth twice.** For every family the independent solver re-derives each answer from the rendered text without having seen the
   generator. The six older families (`answerable_facts`, `policy_case`, `log_count_check`, `state_goal`, `toolcall_valid`,
   `filter_match`) also parse their own text back inside the script and assert that the answer is the same.

## The independent solvers

`solvers/<family>.py` exposes `solve(state, question, options) -> option key`. It receives only what a decision model receives: the
rendered state, the question and the options (an ordered mapping key -> text). It never sees `gold`, `meta` or the item id, and it was
written by a second author who had not read the generator. A state it cannot read raises an error and counts as a disagreement.
`audits/solve_all.py` runs it on every item; release 1.1 requires 600 of 600 in every family, and fresh draws with other seeds pass the
same check.

## The 13 families

| family | layer | question (options) | state | levels | contrast groups |
|---|---|---|---|---|---|
| `answerable_facts` | A | can the question be answered from the facts listed? (yes, no) | a table of facts about invented organisations with four rules of reading, and a question that needs two to four rows | 2 needed facts among 20 rows / 3 among 40 / 4 among 80 | the negative replaces one needed row by another attribute or a look-alike organisation (300 pairs) |
| `perm_inherit` | B | is the request allowed? (yes, no) | the written rules of an access system, users, groups, roles, a folder tree and one request | from a tree of depth 2 to nested groups, sealed folders and deny entries in a tree of depth 4 | the negative breaks exactly one link of the only path that grants access (300 pairs) |
| `policy_case` | B | what does the policy require for this case? (approve, deny, escalate) | a numbered policy of 4, 8 or 12 rules with exceptions, a precedence statement and a default, and a case record | the number of rules | 201 policies, most with one case per outcome |
| `log_count_check` | C | is the claim correct for this log? (yes, no) | an event log of 30, 60 or 90 lines and a claim about the exact number of events of one service and level in a time window | the number of log lines | the negative changes one field of a true claim: the count by one or two, the window or the service (300 pairs) |
| `sched_conflict` | D | can the requested booking be confirmed as it stands? (yes, no) | rooms with seats, equipment and opening hours, booking conventions, the confirmed bookings and one request | from 2 rooms and 6 to 8 bookings to 5 or 6 rooms and 20 to 28 bookings over 2 or 3 days | the positive lies exactly on the limit that the negative crosses, most often through an overlap or a double-booked person (300 pairs) |
| `state_goal` | D | after these operations, are all goal conditions satisfied? (yes, no) | a small file store, how each kind of step works, a goal of 3, 5 or 7 conditions and a numbered trace | traces of 5, 15 or 25 steps | one changed step makes exactly one condition fail: wrong target, wrong content, a swap or a replaced step (300 pairs) |
| `toolcall_valid` | D | is the proposed call correct for the request under this schema? (yes, no) | a JSON tool schema with 6, 9 or 12 properties and rules in its description, a user request, the proposed call | the number of properties | one planted deviation per negative, 50 items per kind (300 pairs) |
| `triage_order` | D | which waiting case do the rules put at the position asked for? (five tickets) | the current time, numbered ordering rules, the queue and the requested position | 6 cases and 2 or 3 rules up to 12 to 14 cases, 5 or 6 rules and two class adjustments | the members differ in one element, most often an arrival time or the current time (201 groups) |
| `clause_change` | E | does the change between the two versions alter the answer to the point at issue? (same, yes_only_A, yes_only_B) | rules of reading, two versions of an agreement and a case with facts | from 8 clauses per version to 12 to 14 | the members place a fact between the old and new limit of the stricter clause, of the looser clause, or outside both (201 groups) |
| `dep_resolve` | E | does the proposed set install cleanly in the target environment? (yes, no) | conventions (3.10.0 is later than 3.9.9), the target, an invented package index and the pins | from 4 or 5 pins to 9 to 12, with runtimes and conflicts at the higher levels | the members differ in one pin: a narrowly missed bound, a missing pin, an unmet requirement (300 pairs) |
| `ledger_reconcile` | F | which entry of ledger A does not reconcile with ledger B? (five entries, none) | two ledgers of one period and the matching conventions | ledgers of 8, 14 or 22 entries, with date tolerances, split lines, fees and batch lines at the higher levels | the members differ in the planted lines of B; `none` is the answer of 100 items (201 groups) |
| `record_rule` | F | which rule does the batch violate? (one key per rule, none) | a record type, 6 to 9 numbered integrity rules, reference lists and a batch of records with at most one rule broken | batches of 10, 16 or 24 records | 150 batches of four items with near-miss violations and, in 72 batches, the untouched batch |
| `filter_match` | G | does the record satisfy every constraint of the request? (yes, no) | a request with 6, 9 or 12 constraints of twenty kinds, ten of which need a small computation, and one catalogue record in JSON | the number of constraints | in both members the compared quantity lies on the limit or one step from it (300 pairs) |

## Seeds, fresh draws and older versions

- **Published set.** Without environment variables every script writes the items of release 1.1.
- **Fresh draws.** Seven scripts take a second seed: `clause_change`, `dep_resolve`, `ledger_reconcile`, `perm_inherit`, `record_rule`,
  `sched_conflict`, `triage_order`. `BENCH_OUT=<dir> BENCH_SEED=<K> python3 generators/<family>.py` writes a new set of the same design to
  `<dir>/<family>/`, with ids, groups and `meta` marked with the seed; `BENCH_SEED` is refused without `BENCH_OUT`, so the published set is
  never overwritten. `python3 generators/regenerate.py --seed K --check` does this for all seven and runs the checks.
- **Older versions.** Four scripts keep their first, easier version behind a switch: `BENCH_DIFFICULTY=v1` for `answerable_facts`,
  `filter_match` and `record_rule`, the argument `v1` for `toolcall_valid`. Release 1.1 uses the default `v2` of all four.

## Run time

Generating all 13 families takes about four minutes on a laptop (measured with Python 3.9.6): `policy_case` about 80 to 95 seconds,
`state_goal` about 50, `triage_order` 30 to 75, `record_rule` and `perm_inherit` up to about 30, every other family a few seconds.
The solvers check all 7,800 items in about 20 seconds; `audits/audit_v3.py` (numpy) needs about ten minutes for the 13 families.
