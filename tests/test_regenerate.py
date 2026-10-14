"""Regeneration test (about half a minute): two families are generated from the published seed and must give the items of release 1.1 byte
for byte, and two fresh draws (seeds 1 and 2) of the same families must pass the independent solver on every item and the format check.
Everything is written to a temporary folder.
    python3 tests/test_regenerate.py            (Python 3.9, standard library only)"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAMILIES = ("dep_resolve", "sched_conflict")          # two of the seven families whose generator takes a seed (fast ones)
SEEDS = (1, 2)


def generate(family, out_tasks, seed=None):
    env = dict(os.environ, BENCH_OUT=out_tasks)
    env.pop("BENCH_SEED", None)
    if seed is not None:
        env["BENCH_SEED"] = str(seed)
    return subprocess.run([sys.executable, "-I", os.path.join(REPO, "generators", f"{family}.py")], cwd=REPO, env=env,
                          capture_output=True, text=True)


class Regenerate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        with open(os.path.join(REPO, "releases", "v1.1", "index.json"), encoding="utf-8") as f:
            cls.index = json.load(f)["tasks"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir)

    def test_published_seed_gives_release_items(self):
        root = os.path.join(self.dir, "published")
        for fam in FAMILIES:
            r = generate(fam, os.path.join(root, "tasks"))
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            with open(os.path.join(root, "tasks", fam, "items.jsonl"), "rb") as f:
                self.assertEqual(hashlib.sha256(f.read()).hexdigest(), self.index[fam]["items_sha256"], fam)

    def test_fresh_draws_pass_the_solver(self):
        for seed in SEEDS:
            root = os.path.join(self.dir, f"seed_{seed}")
            for fam in FAMILIES:
                r = generate(fam, os.path.join(root, "tasks"), seed)
                self.assertEqual(r.returncode, 0, r.stderr[-2000:])
                with open(os.path.join(root, "tasks", fam, "items.jsonl"), encoding="utf-8") as f:
                    items = [json.loads(l) for l in f]
                self.assertEqual(len(items), 600)
                self.assertTrue(all(it["id"].startswith(f"{fam}:s{seed}:") for it in items))
                with open(os.path.join(root, "tasks", fam, "items.jsonl"), "rb") as f:
                    self.assertNotEqual(hashlib.sha256(f.read()).hexdigest(), self.index[fam]["items_sha256"])
            for tool in ("solve_all.py", "validate.py", "key_balance.py"):
                r = subprocess.run([sys.executable, "-I", os.path.join(REPO, "audits", tool), "--root", root] + list(FAMILIES),
                                   cwd=REPO, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, f"seed {seed}, {tool}:\n{r.stdout[-3000:]}{r.stderr[-2000:]}")


if __name__ == "__main__":
    unittest.main()
