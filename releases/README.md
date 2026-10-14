# Releases: task cards, hashes and dropped items

This folder holds no items. It records what each release of DecisionPivot contains, so that a copy of the items can be checked and the
releases that are not distributed as files can be derived or rebuilt.

```
v1.1/index.json               every task of release 1.1 (48 tasks, 41,904 items): track, layer, metric, rows, groups, version,
                              SHA-256 of items.jsonl, redistribution status
v1.1/task_cards/<task>.json   the task card (task.json) of every task of release 1.1, as on the Hugging Face dataset
v1.1/build_drops.json         for the 13 tasks released as rebuild scripts: the ids that the build scripts write but release 1.0 dropped
                              (items found in the authors' training data and items dropped with them to keep the classes balanced)
v1.3/index.json               the same for release 1.3 (48 tasks, 40,033 items)
v1.3/task_cards/<task>.json   the task cards of release 1.3
v1.3/dropped_from_v1.1.json   the 1,871 ids of 28 reference tasks that release 1.3 drops from release 1.1
```

Used by `scoring/check_data.py` (compare a copy with the hashes), `scoring/derive_v13.py` (release 1.3 from release 1.1),
`generators/regenerate.py` (the core hashes; `--install` writes the core task cards) and `reference/rebuild.py`.
