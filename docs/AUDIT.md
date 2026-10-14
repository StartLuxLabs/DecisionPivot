# Audit of the core families (release 1.1)

The checks below were run on the 7,800 items of release 1.1 with the scripts in `audits/`; they can be repeated on regenerated items (`python3 generators/regenerate.py --check` and `python3 audits/audit_v3.py`, which needs numpy) or on the downloaded items (`--root data`). Task = family.

1. **Labels.** `audits/solve_all.py`: an independent second implementation per task (`solvers/<task>.py`, written by another author who did not read the generator; it receives only the rendered state, the question and the options) solves every item again. Required: 100 %.
2. **No shortcut.** `audits/audit_v3.py` (numpy only; 5-fold, the rows of a group in one fold, mean of 5 fold seeds): bag-of-words logistic regression on the options only (`bow opt`), on question + options (`bow q+opt`) and over single options (`per opt`) must stay within 3 points above `ref` = max(majority key, most frequent gold position, chance); yes/no tasks: best single threshold on the length of the state (`len`) and on its number of lines (`lines`) within 0.50 ± 0.02; `pos dev` = largest distance of a gold-position share from uniform (≤ 0.03). `bow state` (information): the same regression on the words of the state.
3. **Variety.** `dup` = rows whose state equals another state (0); `dom` = domains; `skel` = distinct lines after masking numbers and identifiers; `vocab` = words of frequency ≥ 20 that are more than twice as frequent in one class (0) / worst ratio (yes/no and three-way tasks).
4. **Independence from the training data.** `overlap` = training rows of the authors' procedural training files that share two or more word 13-grams with an item of the task (counted by the authors; the training files are not public); required: 0.
5. **Format.** `audits/validate.py`.

| task | rows | solver agreement | validate | ref | bow opt | bow q+opt | per opt | pos dev | len | lines | vocab | dup | dom | skel | bow state | result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `answerable_facts` | 600 | 600 / 600 | OK | 0.500 | 0.469 | 0.469 | 0.469 | 0.000 | 0.507 | 0.500 | 0 / 1.04 | 0 | 0 | 678 | 0.489 | PASS |
| `perm_inherit` | 600 | 600 / 600 | OK | 0.500 | 0.472 | 0.472 | 0.472 | 0.000 | 0.503 | 0.500 | 0 / 1.00 | 0 | 5 | 8533 | 0.500 | PASS |
| `policy_case` | 600 | 600 / 600 | OK | 0.333 | 0.260 | 0.260 | 0.296 | 0.000 | – | – | 0 / 1.61 | 0 | 4 | 2145 | 0.238 | PASS |
| `log_count_check` | 600 | 600 / 600 | OK | 0.500 | 0.460 | 0.460 | 0.460 | 0.000 | 0.503 | 0.500 | 0 / 1.04 | 0 | 0 | 106 | 0.457 | PASS |
| `sched_conflict` | 600 | 600 / 600 | OK | 0.500 | 0.464 | 0.464 | 0.464 | 0.000 | 0.502 | 0.500 | 0 / 1.00 | 0 | 5 | 1556 | 0.527 | PASS |
| `state_goal` | 600 | 600 / 600 | OK | 0.500 | 0.500 | 0.500 | 0.500 | 0.000 | 0.505 | 0.500 | 0 / 1.00 | 0 | 5 | 2734 | 0.500 | PASS |
| `toolcall_valid` | 600 | 600 / 600 | OK | 0.500 | 0.500 | 0.500 | 0.500 | 0.000 | 0.507 | 0.508 | 0 / 1.20 | 0 | 0 | 1283 | 0.527 | PASS |
| `triage_order` | 600 | 600 / 600 | OK | 0.200 | 0.213 | 0.213 | 0.188 | 0.000 | – | – | – | 0 | 6 | 716 | 0.193 | PASS |
| `clause_change` | 600 | 600 / 600 | OK | 0.333 | 0.253 | 0.253 | 0.288 | 0.000 | – | – | 0 / 1.50 | 0 | 6 | 1413 | 0.305 | PASS |
| `dep_resolve` | 600 | 600 / 600 | OK | 0.500 | 0.469 | 0.469 | 0.469 | 0.000 | 0.503 | 0.500 | 0 / 1.00 | 0 | 5 | 6383 | 0.500 | PASS |
| `ledger_reconcile` | 600 | 600 / 600 | OK | 0.167 | 0.146 | 0.144 | 0.151 | 0.000 | – | – | – | 0 | 5 | 842 | 0.128 | PASS |
| `record_rule` | 600 | 600 / 600 | OK | 0.122 | 0.111 | 0.110 | 0.105 | 0.006 | – | – | – | 0 | 8 | 2853 | 0.116 | PASS |
| `filter_match` | 600 | 600 / 600 | OK | 0.500 | 0.473 | 0.473 | 0.473 | 0.000 | 0.503 | 0.500 | 0 / 1.21 | 0 | 4 | 1284 | 0.511 | PASS |

All tasks pass: **yes**.

## Overlap with the training rows

The two procedural training files of the authors (108,005 and 27,001 rows) were scanned for the 1,253,233 word 13-grams of the 7,800 items: no training row shares two or more 13-grams with any item of any family.

## Keys per level (`audits/key_balance.py`)

Fixed option keys: count of each key per level. Keys that differ per item: count of each gold position per level, and `none` where the task offers it.

| task | level 1 | level 2 | level 3 | gate |
|---|---|---|---|---|
| `answerable_facts` | no 100 yes 100 | no 100 yes 100 | no 100 yes 100 | PASS |
| `clause_change` | same 67 yes_only_A 67 yes_only_B 66 | same 66 yes_only_A 67 yes_only_B 67 | same 67 yes_only_A 66 yes_only_B 67 | PASS |
| `dep_resolve` | no 100 yes 100 | no 100 yes 100 | no 100 yes 100 | PASS |
| `filter_match` | no 100 yes 100 | no 100 yes 100 | no 100 yes 100 | PASS |
| `ledger_reconcile` | pos0 34 pos1 33 pos2 33 pos3 33 pos4 34 pos5 33 none 33 | pos0 33 pos1 34 pos2 33 pos3 34 pos4 33 pos5 33 none 33 | pos0 33 pos1 33 pos2 34 pos3 33 pos4 33 pos5 34 none 34 | PASS |
| `log_count_check` | no 100 yes 100 | no 100 yes 100 | no 100 yes 100 | PASS |
| `perm_inherit` | no 100 yes 100 | no 100 yes 100 | no 100 yes 100 | PASS |
| `policy_case` | approve 67 deny 67 escalate 66 | approve 66 deny 67 escalate 67 | approve 67 deny 66 escalate 67 | PASS |
| `record_rule` | pos0 31 pos1 22 pos2 22 pos3 22 pos4 26 pos5 22 pos6 23 pos7 16 pos8 12 pos9 4 none 24 | pos0 19 pos1 24 pos2 23 pos3 22 pos4 23 pos5 23 pos6 27 pos7 21 pos8 12 pos9 6 none 24 | pos0 22 pos1 27 pos2 25 pos3 28 pos4 23 pos5 27 pos6 21 pos7 14 pos8 8 pos9 5 none 24 | PASS |
| `sched_conflict` | no 100 yes 100 | no 100 yes 100 | no 100 yes 100 | PASS |
| `state_goal` | no 100 yes 100 | no 100 yes 100 | no 100 yes 100 | PASS |
| `toolcall_valid` | no 100 yes 100 | no 100 yes 100 | no 100 yes 100 | PASS |
| `triage_order` | pos0 40 pos1 40 pos2 40 pos3 40 pos4 40 | pos0 40 pos1 40 pos2 40 pos3 40 pos4 40 | pos0 40 pos1 40 pos2 40 pos3 40 pos4 40 | PASS |

## What changed in release 1.1 (quality fixes after the two-reviewer audit of 65 items, 8 October 2026)

Both reviewers (two AI models) agreed with every key (65 / 65) and found every item well-posed; the fixes below address the defects
they listed. "Before" = the items of release 1.0, "after" = the items of release 1.1, measured with the same script on both.
dep_resolve, perm_inherit and clause_change are unchanged (byte-identical to release 1.0). Every family now has `meta.level`
1 / 2 / 3 with 200 items each.

| family | defect | before -> after |
|---|---|---|
| filter_match | day-count convention stated in requests that count days | 0 of 532 -> 546 of 546 (36 on-limit items flipped under inclusive counting before; the 29 now on a limit follow the stated rule) |
| filter_match | phrasings that name or paraphrase another field ("comes from" for the maker next to `ships_from`, "origin", "listed under", ...) | 376 items -> 0 |
| filter_match | list price below price / bundle unit price / price (median) / out-of-range specs per category / shipping fee > 25 % of price | 52 -> 0 / 0.022 -> 0.809 (all in 0.72-0.93) / 2,388 of 3,450 spec values -> 0 / 131 -> 0 |
| state_goal | preamble false for at least one step (set creates files) | 471 of 600 -> 0 (asserted per step) |
| state_goal | pseudo-word file names / contents; steps in a purposeful pattern; renames that keep the extension | 94 % / 85 % -> 0 / 0; 31 % -> 92 % (all steps belong to goal-directed macros); 20 % -> 100 % |
| state_goal | (found by the independent solver) the failing condition of a negative concerns a file or folder no step touches, never in a positive; steps outside every goal's dependency cone | 66 of 300 negatives ("untouched goal -> no" about 0.61) -> 0 in both classes; dead steps per item yes 0.78 / 3.51 / 4.79 vs no 1.31 / 4.08 / 5.29 -> equal within every pair (0.91 / 3.48 / 4.44) |
| state_goal | deviation names | wrong_key / wrong_value / swap / missing -> wrong_target / wrong_content / steps_swapped / step_missing; pairs now carry `group` |
| policy_case | rules whose outcome goes against the direction of risk (e.g. approve because consent is missing) | 338 of 1,608 rules -> 0 (exceptions 241 of 514 -> 0) |
| policy_case | dead rules (never decide under the precedence) / dead exceptions / near-duplicate rule pairs | 294 / 116 / 104 -> 0 / 0 / 0 (exact check over all cells of the attribute space) |
| policy_case | risk flags no rule reads / inconsistent field pairs (account age < days since purchase, training older than tenure, ...) | 290 records / 137 records -> 0 / 0 |
| policy_case | keys approve / deny / escalate | 200 / 200 / 200 before and after (the reviewers' 0 / 5 deny was sampling); balanced per level |
| record_rule | derived fields inconsistent outside the planted violation and the deliberate decoys (tax = round(net x rate), ...) / dated references before what they name | 531 rows in 56 items / 1,270 rows in 365 items -> 0 / 0 |
| record_rule | status convention (a plain reference rule accepts every listed key, only a rule that names a status requires it) | implied by "read every rule literally" -> written in every state with a status column (420 states, 4 wordings) |
| record_rule | none share | 0.120 per level (24 of 200), as designed (about 1 / mean number of options); now asserted |
| triage_order | time columns that contradict each other (pickup before check-in, appointment before arrival) | 107 items -> 0 |
| triage_order | class-first reading (lowest listed class, then earliest arrival) gives the key | level 1: class column shown but unused in 71 items -> class is rule 1 everywhere (the other tie-break never gives the key: 37 % -> 0 %); level 2: 14.5 % -> 12.5 %; level 3: 9.5 % -> 7.5 % (at most 25 % asserted) |
| log_count_check | stated count as a cue | true share among claims of 0 events 0.506 vs 0.499 for k > 0 (no family-level cue; the reviewers' pattern was sampling); best per-level table on the stated count 0.535 -> 0.505 (histograms equalised per level) |
| log_count_check | "exactly 1 ERROR entries"; exactness of the claim | 78 items with a plural noun after 1 -> 0; "exactly" in 1 of 5 claim phrasings -> 5 of 5 (an at-least reading was defensible in 121 items) |
| log_count_check | metadata | `level` held the log severity -> `level` = difficulty 1 / 2 / 3, severity in `log_level` |
| sched_conflict | negatives decided by a cheap check (hours, seats, equipment) | level 2: 60 % -> 30 %; level 3: 60 % -> 15 %; a reader that checks only these three: 0.800 -> 0.650 (level 2), 0.800 -> 0.575 (level 3); level 1 unchanged by design (0.830) |
| answerable_facts | founding years at the clamp bound | 25.2 % of the listed years (all 2022) -> 0.17 %; distinct years 72 -> 144 (1881-2024) |
| answerable_facts | level ladder | a 3 x 3 grid without a level -> level 1 = 2 hops on 20 rows, 2 = 3 hops on 40 rows, 3 = 4 hops on 80 rows |
| answerable_facts | questions that need the inherited region | 25 % -> 40 % per level |
| ledger_reconcile | ledger A or B named in two ways within an item | 487 items -> 0 |
| ledger_reconcile | per-line deduction rule for negative amounts | not stated (no negative entries) -> stated on the size of the figure; 260 negative marked entries, 172 items whose key changes under the signed reading |
| toolcall_valid | request words that equal a parameter name without referring to it ("the travel receipt" next to `receipt`) | 198 items -> 0 |
| toolcall_valid | pairs without a group id | `group` null (pairs only in meta.pair) -> 300 groups |
| toolcall_valid | filler sentences / enum codes copied into the request | 8 sentences (one in up to 46 items) -> 44 (at most 12 items each) / "in nl" in 160 items -> language names, the call carries the code |

## Residual observations (not changed)

- policy_case: coherent policies leave a mild risk prior: calling the least risky-looking case of a policy's three cases
  "approve" is right in 44 % of the triples (chance 33 %; release 1.0: 36 %); three cases with matched risk-signal counts are
  chosen where possible (67 % of the triples).
- sched_conflict: a positive sits on the limit that its negative crosses, so "a neighbour exactly at the reset gap"
  appears in 0.76 of the positives and 0.46 of the negatives at level 3 (it still needs the bookings and the gap rule);
  level 1 keeps its cheap kinds by design.
- triage_order: at level 1 class is now the first rule, so "class first" is the written rule there, not a shortcut.
- log_count_check: the end-time rule decides 21 % of the items; 12 items have a window that reaches beyond the logged
  span.
- answerable_facts: sums are worded "that the table lists", so a missing link row never makes a sum unanswerable; 8
  "only subsidiary" negatives list no subsidiary at all.
- ledger_reconcile: "1 units" in 15 items; toolcall_valid: "1 pieces" in 6 items (cosmetic).
- toolcall_valid: only the 50 `value` negatives need the request; checking the schema and the rules alone reaches
  0.917 (a property of the v2 design, unchanged).
- policy_case: one default wording ("a request that no rule covers") must be read as "no rule applies after its
  exceptions" in 21 items; one case per policy sits within 5 % of the limit of the deciding rule (design of release 1.0).
- filter_match: the six dates of a record are not in a natural order (30 records listed before they were made).

