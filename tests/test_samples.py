"""Tests on the sample items in tests/samples/tasks/ (two whole contrast groups per core family, EVALUATION ONLY): the format check, the
independent solvers and the scorer, without the full data.
    python3 tests/test_samples.py            (Python 3.9, standard library only)"""
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
import warnings

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(REPO, "tests", "samples")
sys.path.insert(0, os.path.join(REPO, "audits"))
sys.path.insert(0, os.path.join(REPO, "scoring"))
import validate as V  # noqa: E402
import score as S  # noqa: E402

FAMILIES = sorted(os.listdir(os.path.join(SAMPLES, "tasks")))


def items_of(task):
    with open(os.path.join(SAMPLES, "tasks", task, "items.jsonl"), encoding="utf-8") as f:
        return [json.loads(l) for l in f]


def options_of(item):
    c = item["questions"]["q"]["criteria"]
    return [str(i) for i in range(len(c))] if isinstance(c, list) else list(c)


class Samples(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter("ignore", ResourceWarning)      # the audit tools read files without closing them explicitly

    def test_13_families(self):
        self.assertEqual(len(FAMILIES), 13)
        with open(os.path.join(REPO, "releases", "v1.1", "index.json"), encoding="utf-8") as f:
            index = json.load(f)["tasks"]
        self.assertEqual(sorted(t for t, e in index.items() if e["track"] == "core"), FAMILIES)

    def test_format_and_hash(self):
        old = V.HERE
        V.HERE = SAMPLES
        try:
            for t in FAMILIES:
                tj, errs = V.check(t)
                self.assertEqual(errs, [], t)
                with open(os.path.join(SAMPLES, "tasks", t, "items.jsonl"), "rb") as f:
                    self.assertEqual(hashlib.sha256(f.read()).hexdigest(), tj["items_sha256"], t)
        finally:
            V.HERE = old

    def test_whole_groups(self):
        for t in FAMILIES:
            with open(os.path.join(SAMPLES, "tasks", t, "task.json"), encoding="utf-8") as f:
                tj = json.load(f)
            groups = {}
            for it in items_of(t):
                groups.setdefault(it["group"], []).append(it)
            self.assertEqual(len(groups), tj["groups"], t)
            self.assertEqual({it["meta"]["level"] for g in groups.values() for it in g}, {1, 3}, t)
            for g in groups.values():
                self.assertGreater(len({str(it["gold"]) for it in g}), 1, f"{t}: the members of a contrast group differ in the key")

    def test_independent_solvers(self):
        for t in FAMILIES:
            spec = importlib.util.spec_from_file_location(f"solver_{t}", os.path.join(REPO, "solvers", f"{t}.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for it in items_of(t):
                q = it["questions"]["q"]
                c = q["criteria"]
                opts = {str(i): x for i, x in enumerate(c)} if isinstance(c, list) else dict(c)
                self.assertEqual(str(mod.solve(json.loads(json.dumps(it["state"])), q["instructions"], opts)), str(it["gold"]), it["id"])


class Scoring(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter("ignore", ResourceWarning)
        self.dir = tempfile.mkdtemp()
        self.old = S.HERE
        S.HERE = SAMPLES

    def tearDown(self):
        S.HERE = self.old
        shutil.rmtree(self.dir)

    def run_system(self, name, prob_fn):
        d = os.path.join(self.dir, name)
        os.makedirs(d)
        for t in FAMILIES:
            with open(os.path.join(d, f"{t}.jsonl"), "w") as f:
                for it in items_of(t):
                    f.write(json.dumps({"id": it["id"], "p": prob_fn(it)}) + "\n")
        return d

    def test_oracle(self):
        d = self.run_system("oracle", lambda it: {k: (1.0 if k == str(it["gold"]) else 0.0) for k in options_of(it)})
        for t in FAMILIES:
            r = S.score_task(t, d, 50)
            self.assertIsNotNone(r, t)
            self.assertEqual(r["accuracy"], 1.0, t)
            self.assertEqual(r["pair_accuracy"], 1.0, t)
            self.assertEqual(r["auto_at_5"], 1.0, t)
            self.assertEqual(r["coverage"], 1.0, t)

    def test_always_yes_solves_no_pair(self):
        d = self.run_system("yes", lambda it: {k: (0.9 if k == "yes" else 0.1 / (len(options_of(it)) - 1)) for k in options_of(it)})
        yes_no = [t for t in FAMILIES if set(options_of(items_of(t)[0])) == {"yes", "no"}]
        self.assertEqual(len(yes_no), 8)
        for t in yes_no:
            r = S.score_task(t, d, 50)
            self.assertAlmostEqual(r["accuracy"], 0.5, msg=t)
            self.assertEqual(r["pair_accuracy"], 0.0, t)

    def test_missing_answers_do_not_count(self):
        d = os.path.join(self.dir, "empty")
        os.makedirs(d)
        self.assertIsNone(S.score_task(FAMILIES[0], d, 10))


if __name__ == "__main__":
    unittest.main()
