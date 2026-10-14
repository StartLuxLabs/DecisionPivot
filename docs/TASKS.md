# The 48 tasks of DecisionPivot

Written from the task cards in `releases/` (the `task.json` of every task). Layers: A before generation, B guards, C after generation, D agent loop, E reasoning classification, F data pipelines, G search and matching.

## Core track: 13 generated families (7,800 items)

Each family has 600 items, 200 on each of three levels, organised in contrast groups (the same case with one planted detail that changes the answer). Content-blind rule: accuracy, in percent, of the best rule that never reads the content (`audits/audit.py`, `audits/audit_v3.py`). The items are identical in releases 1.1 and 1.3.

| layer | family | question | options | contrast groups | content-blind rule | median state (characters) | version |
|---|---|---|---:|---:|---:|---:|---:|
| A | `answerable_facts` | can the facts answer the question | 2 | 300 | 50.7 | 2,470 | 3 |
| B | `perm_inherit` | may the user act on the folder | 2 | 300 | 50.3 | 3,926 | 1 |
| B | `policy_case` | approve, deny or escalate | 3 | 201 | 33.3 | 1,703 | 2 |
| C | `log_count_check` | is the claimed event count right | 2 | 300 | 50.5 | 2,291 | 2 |
| D | `sched_conflict` | can the booking be confirmed | 2 | 300 | 50.2 | 3,029 | 2 |
| D | `state_goal` | does the trace reach the goal | 2 | 300 | 50.5 | 2,475 | 2 |
| D | `toolcall_valid` | is the tool call valid | 2 | 300 | 50.7 | 4,975 | 3 |
| D | `triage_order` | which case is at the asked place | 5 | 201 | 20.0 | 2,256 | 2 |
| E | `clause_change` | does the edit change the answer | 3 | 201 | 33.3 | 3,730 | 1 |
| E | `dep_resolve` | do the pinned versions install | 2 | 300 | 50.3 | 3,348 | 1 |
| F | `ledger_reconcile` | which entry fails, or none | 6 | 201 | 16.7 | 2,764 | 2 |
| F | `record_rule` | which rule is broken, or none | 7 to 10 | 150 | 12.2 | 4,751 | 3 |
| G | `filter_match` | does the record pass every filter | 2 | 300 | 50.5 | 1,647 | 3 |

## Reference track: 35 converted public test sets

Items: release 1.1 (on the Hugging Face dataset) and release 1.3 (the items the paper scores, `scoring/derive_v13.py`). Labels as given by the source. Metric with its chance level in brackets; *skill* = 1 - mean squared error / that of the best constant, against a success rate. Release: **I** items included, **SA** items included under a share-alike licence, **R** rebuild script only (`reference/rebuild.py`). The licence of each source is in the `licence` field of its task card.

| layer | task | decision | items 1.1 | items 1.3 | labels | metric (chance) | release |
|---|---|---|---:|---:|---|---|---|
| A | `ambigqa` | does the question have several readings | 998 | 990 | human | accuracy (0.500) | SA |
| A | `cap_boundary_card` | will the named chat model answer correctly | 912 | 911 | programmatic | skill (0.000) | R |
| A | `cap_boundary_record` | the same, with the model's record on related questions | 775 | 774 | programmatic | skill (0.000) | R |
| A | `freshqa_premise` | does the question rest on a false premise | 498 | 495 | human | AUROC (0.500) | R |
| A | `known_unknown` | does the question have a known answer | 984 | 972 | human | accuracy (0.500) | I |
| A | `selfaware` | can the question be answered at all | 988 | 970 | human | accuracy (0.500) | SA |
| B | `aegis2_prompt` | is the prompt unsafe | 954 | 836 | human | accuracy (0.500) | I |
| B | `bipia_injection` | does the e-mail carry an inserted instruction | 88 | 88 | programmatic | accuracy (0.500) | I |
| B | `browsesafe` | does the web page carry an injected instruction | 1,000 | 1,000 | programmatic | accuracy (0.500) | I |
| B | `cosapien_policy` | allowed, disallowed or partly allowed under a safety configuration | 148 | 148 | human | accuracy (0.333) | I |
| B | `jailbreak_wild` | is the prompt a jailbreak attempt | 824 | 796 | mixed | accuracy (0.500) | I |
| B | `jbb_judge` | does the response give harmful content | 293 | 250 | human | AUROC (0.500) | I |
| B | `xstest` | should the request be refused | 449 | 445 | human | AUROC (0.500) | I |
| C | `contextual_judge` | which response is better for the context | 894 | 877 | mixed | accuracy (0.500) | I |
| C | `faithbench` | is the summary faithful to its source | 304 | 298 | human | accuracy (0.500) | R |
| C | `judgebench` | which response is correct | 619 | 619 | programmatic | accuracy (0.500) | I |
| C | `llmbar` | which output follows the instruction better | 399 | 355 | human | accuracy (0.500) | I |
| C | `processbench` | which step is the first wrong one, or none | 966 | 939 | human | accuracy (0.142) | I |
| C | `rewardbench` | which response is better | 912 | 888 | mixed | accuracy (0.500) | R |
| C | `rewardbench2` | which of four responses is best | 980 | 953 | mixed | accuracy (0.250) | I |
| C | `squad2_answerable` | can the question be answered from the passage | 944 | 916 | human | accuracy (0.500) | SA |
| D | `agentreward_success` | did the web agent complete its task | 552 | 552 | human | accuracy (0.500) | R |
| D | `bfcl_relevance` | does any listed function serve the request | 176 | 144 | mixed | accuracy (0.500) | I |
| D | `mind2web_element` | which of ten page elements to act on next | 997 | 901 | human | accuracy (0.100) | R |
| E | `cuad_clause` | does the contract hold a clause of the named category | 320 | 192 | human | accuracy (0.500) | I |
| E | `folio_validation` | is the conclusion true, false or undetermined | 204 | 203 | human | accuracy (0.333) | SA |
| E | `legalbench_mix` | ten legal classification sub-tasks | 942 | 910 | mixed | accuracy (0.428) | I |
| E | `primevul_pair` | is the function vulnerable (asked for a function and its patch) | 1,000 | 996 | programmatic | pair accuracy (0.250) | I |
| F | `label_errors` | is the label of the text correct | 996 | 996 | human | accuracy (0.500) | R |
| G | `entity_match_abt_buy` | do the two records describe the same product | 996 | 996 | mixed | AUROC (0.500) | R |
| G | `entity_match_amazon_google` | do the two records describe the same product | 1,000 | 999 | mixed | AUROC (0.500) | R |
| G | `nevir` | which of two documents that differ by a negation is relevant | 1,000 | 998 | human | pair accuracy (0.250) | I |
| G | `paws` | do the two sentences mean the same | 992 | 976 | human | accuracy (0.500) | R |
| G | `rerank_nfcorpus` | how well does the passage answer the query | 5,000 | 4,950 | human | nDCG@10 (0.142) | R |
| G | `rerank_scifact` | how well does the passage answer the query | 5,000 | 3,900 | human | nDCG@10 (0.088) | R |
| | **all 35** | | **34,104** | **32,233** | | | |

Release 1.1 holds 41,904 items in all, release 1.3 40,033. `releases/v1.1/index.json` and `releases/v1.3/index.json` give the number of items and the SHA-256 of every items file; `python3 scoring/check_data.py` compares a copy with them.
