# Sample items (evaluation only)

Two whole contrast groups of each core family, one of level 1 and one of level 3, copied byte for byte from release 1.1 (64 items). They
let `tests/test_samples.py` run the format check, the independent solvers and the scorer without the full data. Each `task.json` is the
task card of release 1.1 with `rows`, `groups` and `items_sha256` of the sample and a `sample` field that names the full family.

These items are part of the benchmark: never use them as training data or put them into the prompts of a model that is being trained.
