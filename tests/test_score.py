"""Unit tests of the scores that v1 adds to score.py; every expected number is worked out by hand in the comment above it.
    python3 tests/test_score.py            (Python 3.9, standard library only)

A "case" is a list of items; an item is (top probability, right?, group, level).  The helper builds yes/no or three-option items
whose top option has exactly that probability, so the expected values below can be checked with pencil and paper."""
import collections
import json
import math
import os
import random
import shutil
import tempfile
import unittest

import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scoring"))
import score as S  # noqa: E402


def mk_items(task, rows, keys=("yes", "no")):
    """rows: dicts with gold, optional group and level"""
    items = []
    for n, r in enumerate(rows, 1):
        items.append({"id": f"{task}:{n:03d}", "state": None, "soft": None, "gold": r["gold"], "group": r.get("group"),
                      "questions": {"q": {"type": "choice", "instructions": "?", "criteria": {k: k for k in r.get("keys", keys)}}},
                      "meta": ({"level": r["level"]} if "level" in r else {})})
    return items


def mk_probs(item, top_p, right):
    """probabilities whose top option is the gold option (right) or another option (wrong) with probability top_p"""
    ks = [k for k in S.keys_of(item)]
    gold = str(item["gold"])
    other = [k for k in ks if k != gold]
    top = gold if right else other[0]
    rest = (1.0 - top_p) / (len(ks) - 1)
    return {k: (top_p if k == top else rest) for k in ks}


def build(rows, tj_extra=None, task="t"):
    """rows: (top_p or None, right, group, level); None top_p = unanswered.  -> TaskPrep, SystemArrays"""
    spec = [{"gold": "yes", "group": g, "level": lv} if lv is not None else {"gold": "yes", "group": g} for _, _, g, lv in rows]
    items = mk_items(task, spec)
    probs = {}
    for it, (p, right, g, lv) in zip(items, rows):
        probs[it["id"]] = None if p is None else mk_probs(it, p, right)
    tj = {"task": task, "layer": "A", "metric": "accuracy", "track": "core", "rows": len(items)}
    if any(g for _, _, g, _ in rows):
        tj["group_kind"] = "contrast"
    tj.update(tj_extra or {})
    P = S.TaskPrep(tj, items)
    return P, S.SystemArrays(P, probs), items, probs, tj


def stats(rows, **kw):
    P, A, *_ = build(rows, **kw)
    return S.task_stats(P, A, None)


def seq(confs, wrong=()):
    """items with the given top probabilities, the positions in `wrong` (0-based) being errors; no groups, no levels"""
    return [(c, i not in wrong, None, None) for i, c in enumerate(confs)]


class TestAutoAt(unittest.TestCase):
    def test_wrong_item_last(self):
        # 10 items, confidences 0.99 ... 0.90, only the last (0.90) is wrong.
        # prefixes of 1..9 items have 0 errors (ok for 5% and 1%); the prefix of 10 has 1/10 = 10% errors, too many for both.
        # auto_at_5 = auto_at_1 = 9 / 10
        s = stats(seq([0.99 - 0.01 * i for i in range(10)], wrong={9}))
        self.assertAlmostEqual(s["auto_at_5"], 0.9)
        self.assertAlmostEqual(s["auto_at_1"], 0.9)

    def test_wrong_item_in_the_middle(self):
        # the sixth item (position 5) is wrong: prefixes of 1..5 are clean; 6: 1/6, 7: 1/7, 8: 1/8, 9: 1/9, 10: 1/10, all above 5%
        # the longest prefix that meets the target has 5 items: 5 / 10 for both targets
        s = stats(seq([0.99 - 0.01 * i for i in range(10)], wrong={5}))
        self.assertAlmostEqual(s["auto_at_5"], 0.5)
        self.assertAlmostEqual(s["auto_at_1"], 0.5)

    def test_equal_probabilities_enter_together(self):
        # confidences 0.9 (right), 0.8 (right), 0.8 (wrong), 0.7 (right).  Prefixes may end only after a whole group of equal
        # probabilities: after 0.9: 0/1 ok -> 1 item; after both 0.8: 1/3 = 33% no; after 0.7: 1/4 = 25% no.  auto_at_5 = 1/4,
        # whatever the order of the two tied items (an order-dependent rule would give 2/4 when the right one comes first)
        for order in ((True, False), (False, True)):
            rows = [(0.9, True, None, None), (0.8, order[0], None, None), (0.8, order[1], None, None), (0.7, True, None, None)]
            self.assertAlmostEqual(stats(rows)["auto_at_5"], 0.25)

    def test_a_longer_prefix_can_meet_the_target_after_a_shorter_one_failed(self):
        # 40 items, the most confident one is wrong, the other 39 are right.  Prefix 1: 100%; prefix 20: 1/20 = 5% (counts: at or
        # below); prefix 40: 1/40 = 2.5%.  The longest prefix that meets 5% is the whole list: auto_at_5 = 1.
        # For 1% a prefix needs at least 100 items to hold one error: none exists, auto_at_1 = 0
        s = stats(seq([0.99 - 0.001 * i for i in range(40)], wrong={0}))
        self.assertAlmostEqual(s["auto_at_5"], 1.0)
        self.assertAlmostEqual(s["auto_at_1"], 0.0)

    def test_nothing_can_be_decided(self):
        # one item, wrong: the only prefix has a 100% error rate
        self.assertEqual(stats(seq([0.9], wrong={0}))["auto_at_5"], 0.0)

    def test_exactly_five_percent_counts(self):
        # 20 items, one error at the least confident place: prefix of 19 clean, prefix of 20 has 1/20 = 5% = target -> counts
        s = stats(seq([0.99 - 0.001 * i for i in range(20)], wrong={19}))
        self.assertAlmostEqual(s["auto_at_5"], 1.0)
        self.assertAlmostEqual(s["auto_at_1"], 19 / 20)

    def test_unanswered_items_are_wrong_and_least_confident(self):
        # two answered right (0.9, 0.8) and one unanswered (counts as wrong, top probability 1/2): prefix of 2 clean, prefix of 3 33%
        rows = [(0.9, True, None, None), (0.8, True, None, None), (None, False, None, None)]
        self.assertAlmostEqual(stats(rows)["auto_at_5"], 2 / 3)
        self.assertAlmostEqual(stats(rows)["accuracy"], 2 / 3)


class TestConfidentShare(unittest.TestCase):
    def test_threshold_is_inclusive(self):
        # top probabilities 0.95 (right), 0.90 (right), 0.899 (wrong), 0.60 (right): items at or above 0.90 are the first two
        # accuracy among them 2/2 = 1, share 2/4 = 0.5
        s = stats(seq([0.95, 0.90, 0.899, 0.60], wrong={2}))
        self.assertAlmostEqual(s["acc_at_090"], 1.0)
        self.assertAlmostEqual(s["share_at_090"], 0.5)

    def test_error_among_the_confident(self):
        # 0.95 right, 0.92 wrong, 0.90 right, 0.60 right: three items at or above 0.90, two right: 2/3; share 3/4
        s = stats(seq([0.95, 0.92, 0.90, 0.60], wrong={1}))
        self.assertAlmostEqual(s["acc_at_090"], 2 / 3)
        self.assertAlmostEqual(s["share_at_090"], 0.75)

    def test_nobody_is_confident(self):
        s = stats(seq([0.8, 0.7], wrong=set()))
        self.assertEqual(s["share_at_090"], 0.0)
        self.assertTrue(math.isnan(s["acc_at_090"]))


class TestAurc(unittest.TestCase):
    def test_distinct_probabilities(self):
        # confidences 0.9 right, 0.8 right, 0.7 wrong, 0.6 right.  Error rate of the prefix that ends with each item:
        # 0/1, 0/2, 1/3, 1/4.  AURC = (0 + 0 + 1/3 + 1/4) / 4 = 0.5833333 / 4 = 0.1458333
        self.assertAlmostEqual(stats(seq([0.9, 0.8, 0.7, 0.6], wrong={2}))["aurc"], (1 / 3 + 1 / 4) / 4)

    def test_ties_share_the_risk_of_their_group(self):
        # 0.9 right, 0.8 right, 0.8 wrong, 0.7 right.  Prefix after 0.9: 0/1 (one item); after the tied pair: 1/3 (two items);
        # after 0.7: 1/4 (one item).  AURC = (1 * 0 + 2 * 1/3 + 1 * 1/4) / 4 = 0.9166667 / 4 = 0.2291667
        rows = [(0.9, True, None, None), (0.8, True, None, None), (0.8, False, None, None), (0.7, True, None, None)]
        self.assertAlmostEqual(stats(rows)["aurc"], (2 / 3 + 1 / 4) / 4)

    def test_perfect_and_worst_order(self):
        self.assertAlmostEqual(stats(seq([0.9, 0.8, 0.7, 0.6], wrong={3}))["aurc"], (0 + 0 + 0 + 1 / 4) / 4)
        # the error is the most confident item: risks 1/1, 1/2, 1/3, 1/4 -> (1 + 0.5 + 0.3333 + 0.25) / 4 = 0.5208333
        self.assertAlmostEqual(stats(seq([0.9, 0.8, 0.7, 0.6], wrong={0}))["aurc"], (1 + 1 / 2 + 1 / 3 + 1 / 4) / 4)


class TestTriggerRecall(unittest.TestCase):
    CONFS = [0.99 - 0.01 * i for i in range(10)]            # 0.99 ... 0.90

    def test_errors_in_the_lowest_fifth(self):
        # 10 items: the lowest 20% are the two least confident (0.91 and 0.90).  Errors at exactly those two: both caught: 2/2
        self.assertAlmostEqual(stats(seq(self.CONFS, wrong={8, 9}))["trigger_recall_20"], 1.0)

    def test_one_of_two_errors_caught(self):
        # errors at 0.93 (position 6) and 0.90 (position 9): only the one at 0.90 lies among the two lowest: 1/2
        self.assertAlmostEqual(stats(seq(self.CONFS, wrong={6, 9}))["trigger_recall_20"], 0.5)

    def test_no_error_caught(self):
        self.assertAlmostEqual(stats(seq(self.CONFS, wrong={0}))["trigger_recall_20"], 0.0)

    def test_tied_group_across_the_boundary_counts_in_proportion(self):
        # six items 0.99 ... 0.94 right, then four items tied at 0.60, two of them wrong.  The lowest 20% of 10 items are 2 items,
        # half of the tied group of 4; the expected number of errors among 2 of the 4 is 2 * (2 / 4) = 1; 1 of 2 errors: 0.5
        rows = [(0.99 - 0.01 * i, True, None, None) for i in range(6)] + [(0.6, True, None, None), (0.6, False, None, None),
                                                                           (0.6, True, None, None), (0.6, False, None, None)]
        self.assertAlmostEqual(stats(rows)["trigger_recall_20"], 0.5)

    def test_no_errors_means_no_recall(self):
        self.assertTrue(math.isnan(stats(seq(self.CONFS))["trigger_recall_20"]))


class TestPairs(unittest.TestCase):
    def test_pair_accuracy(self):
        # three pairs: both right; one wrong; both wrong.  Only the first pair counts: 1/3.  Item accuracy 3/6
        rows = [(0.9, True, "g1", None), (0.9, True, "g1", None), (0.9, True, "g2", None), (0.9, False, "g2", None),
                (0.9, False, "g3", None), (0.9, False, "g3", None)]
        s = stats(rows)
        self.assertAlmostEqual(s["pair_accuracy"], 1 / 3)
        self.assertAlmostEqual(s["accuracy"], 3 / 6)

    def test_unanswered_member_makes_the_group_wrong(self):
        rows = [(0.9, True, "g1", None), (None, False, "g1", None), (0.9, True, "g2", None), (0.9, True, "g2", None)]
        self.assertAlmostEqual(stats(rows)["pair_accuracy"], 1 / 2)

    def test_groups_of_three(self):
        # a triple counts only if all three are right: triples (R, R, R) and (R, R, W) -> 1/2
        rows = [(0.9, True, "g1", None)] * 3 + [(0.9, True, "g2", None), (0.9, True, "g2", None), (0.9, False, "g2", None)]
        self.assertAlmostEqual(stats(rows)["pair_accuracy"], 1 / 2)

    def test_no_pair_scores_without_groups(self):
        s = stats(seq([0.9, 0.8]))
        self.assertNotIn("pair_accuracy", s)
        self.assertNotIn("pair_direction", s)

    def test_ranking_groups_are_not_contrast_groups(self):
        s = stats([(0.9, True, "q1", None), (0.9, True, "q1", None)], tj_extra={"group_kind": "ranking"})
        self.assertNotIn("pair_accuracy", s)

    def test_pair_direction(self):
        # P(yes) of the member whose truth is yes / of the member whose truth is no:
        #   pair 1: 0.8 / 0.3 -> counts; pair 2: 0.4 / 0.6 -> no; pair 3: 0.5 / 0.5 -> a tie does not count; pair 4: 0.9 / 0.2 -> counts
        # 2 of 4 pairs: 0.5.  (the gold of the second member is "no" in every pair)
        spec = []
        for g in ("p1", "p2", "p3", "p4"):
            spec += [{"gold": "yes", "group": g}, {"gold": "no", "group": g}]
        items = mk_items("t", spec)
        p_yes = [0.8, 0.3, 0.4, 0.6, 0.5, 0.5, 0.9, 0.2]
        probs = {it["id"]: {"yes": p, "no": 1 - p} for it, p in zip(items, p_yes)}
        tj = {"task": "t", "layer": "A", "metric": "accuracy", "track": "core", "group_kind": "contrast"}
        P = S.TaskPrep(tj, items)
        s = S.task_stats(P, S.SystemArrays(P, probs), None)
        self.assertAlmostEqual(s["pair_direction"], 0.5)
        # accuracy of that run: pair 1 both right (0.8 yes, 0.3 -> no right); pair 2 both wrong; pair 3 yes right? 0.5/0.5 first option wins
        # (yes first): yes member right, no member wrong; pair 4 both right
        self.assertAlmostEqual(s["pair_accuracy"], 2 / 4)

    def test_pair_direction_ignores_pairs_without_one_yes_and_one_no(self):
        items = mk_items("t", [{"gold": "yes", "group": "a"}, {"gold": "yes", "group": "a"}])
        probs = {it["id"]: {"yes": 0.9, "no": 0.1} for it in items}
        P = S.TaskPrep({"task": "t", "layer": "A", "metric": "accuracy", "track": "core", "group_kind": "contrast"}, items)
        self.assertNotIn("pair_direction", S.task_stats(P, S.SystemArrays(P, probs), None))


class TestLevels(unittest.TestCase):
    def rows(self):
        # level 1: two pairs, both right in both            -> accuracy 1.0, pair accuracy 1.0
        # level 2: two pairs, one all right, one both wrong -> accuracy 0.5, pair accuracy 0.5
        # level 3: two pairs, each with one right one wrong -> accuracy 0.5, pair accuracy 0.0
        rows = []
        rows += [(0.9, True, "a1", 1)] * 2 + [(0.9, True, "a2", 1)] * 2
        rows += [(0.9, True, "b1", 2)] * 2 + [(0.9, False, "b2", 2)] * 2
        rows += [(0.9, True, "c1", 3), (0.9, False, "c1", 3), (0.9, True, "c2", 3), (0.9, False, "c2", 3)]
        return rows

    def test_accuracy_and_pair_accuracy_per_level(self):
        s = stats(self.rows())
        self.assertAlmostEqual(s["level1_accuracy"], 1.0)
        self.assertAlmostEqual(s["level2_accuracy"], 0.5)
        self.assertAlmostEqual(s["level3_accuracy"], 0.5)
        self.assertAlmostEqual(s["level1_pair_accuracy"], 1.0)
        self.assertAlmostEqual(s["level2_pair_accuracy"], 0.5)
        self.assertAlmostEqual(s["level3_pair_accuracy"], 0.0)

    def test_level_from_a_dial_and_the_severity_clash(self):
        tj = {"level_from": {"field": "meta.lines", "values": {"30": 1, "60": 2, "90": 3}}}
        self.assertEqual(S.level_of({"meta": {"lines": 60, "level": "ERROR"}}, tj), 2)       # meta.level there is a log severity
        self.assertIsNone(S.level_of({"meta": {"level": "ERROR"}}, {}))                       # a string is not a difficulty level
        self.assertEqual(S.level_of({"meta": {"level": 3}}, {}), 3)
        self.assertIsNone(S.level_of({"meta": {"level": 7}}, {}))

    def test_dials_are_reported_for_crossed_families(self):
        rows = [(0.9, True, "a", None), (0.9, False, "a", None), (0.9, True, "b", None), (0.9, True, "b", None)]
        spec = [{"gold": "yes", "group": g} for _, _, g, _ in rows]
        items = mk_items("t", spec)
        for it, hops, rws in zip(items, (2, 2, 3, 3), (20, 20, 40, 40)):
            it["meta"].update({"hops": hops, "rows": rws})
        probs = {it["id"]: mk_probs(it, 0.9, r) for it, (_, r, _, _) in zip(items, rows)}
        tj = {"task": "t", "layer": "A", "metric": "accuracy", "track": "core", "group_kind": "contrast", "dials": {"hops": "meta.hops", "rows": "meta.rows"}}
        P = S.TaskPrep(tj, items)
        d = S.dial_stats(P, S.SystemArrays(P, probs))
        # hops 2 = group a (one right, one wrong): accuracy 0.5, pair 0; hops 3 = group b (both right): accuracy 1, pair 1
        self.assertAlmostEqual(d["hops"]["2"]["accuracy"], 0.5)
        self.assertAlmostEqual(d["hops"]["2"]["pair_accuracy"], 0.0)
        self.assertAlmostEqual(d["hops"]["3"]["pair_accuracy"], 1.0)
        self.assertAlmostEqual(d["rows"]["40"]["accuracy"], 1.0)


class TestResampling(unittest.TestCase):
    def test_a_resample_is_a_multiset_of_groups(self):
        # groups g0 (both right), g1 (both wrong), g2 (one right, one wrong), drawn 2, 0 and 1 times:
        # items: 2 * 2 right + (1 right, 1 wrong) = 5 right of 6 -> accuracy 5/6; pair accuracy = (2 * 1 + 0 + 0) / 3 = 2/3
        rows = [(0.9, True, "g0", None)] * 2 + [(0.9, False, "g1", None)] * 2 + [(0.9, True, "g2", None), (0.9, False, "g2", None)]
        P, A, *_ = build(rows)
        s = S.task_stats(P, A, [2, 0, 1])
        self.assertAlmostEqual(s["accuracy"], 5 / 6)
        self.assertAlmostEqual(s["pair_accuracy"], 2 / 3)
        self.assertEqual(s["n_items"], 6)

    def test_bootstrap_resamples_groups_not_items(self):
        # ten pairs: five with both members right, five with both wrong.  By pair the accuracy is Binomial(10, 1/2) / 10
        # (2.5% and 97.5% points at 0.2 and 0.8, width 0.6); by item (20 items) it would be Binomial(20, 1/2) / 20 (0.3 and 0.7,
        # width 0.4).  The interval of score_task_arrays must be the wide one
        rows = []
        for g in range(10):
            rows += [(0.9, g < 5, f"g{g}", None)] * 2
        P, A, items, probs, tj = build(rows)
        self.assertEqual(P.n_units, 10)
        r, boot = S.score_task_arrays("t", tj, items, P, probs, 1000)
        self.assertAlmostEqual(r["value"], 0.5)
        self.assertGreater(r["hi"] - r["lo"], 0.5)
        self.assertGreater(r["accuracy_hi"] - r["accuracy_lo"], 0.5)
        self.assertEqual(len(boot["accuracy"]), 1000)

    def test_the_same_resamples_for_every_system_of_a_task(self):
        a, b = S.make_resamples(7, 5), S.make_resamples(7, 5)
        self.assertEqual(a, b)
        self.assertTrue(all(len(x) == 7 and max(x) < 7 for x in a))


def brute(items, tau=0.90, trigger=0.20):
    """independent slow implementation; items = [(top probability, right)]"""
    n = len(items)
    tps = sorted({round(p, 12) for p, _ in items}, reverse=True)
    out = {"accuracy": sum(r for _, r in items) / n}
    for name, target in (("auto_at_5", 0.05), ("auto_at_1", 0.01)):
        best = 0
        for t in tps:                                           # the items with top probability >= t form a prefix with whole groups
            sel = [r for p, r in items if round(p, 12) >= t]
            if (len(sel) - sum(sel)) / len(sel) <= target + 1e-12:
                best = max(best, len(sel))
        out[name] = best / n
    risk = 0.0
    for p, _ in items:                                          # every item enters with the risk of its whole group
        sel = [r for q, r in items if round(q, 12) >= round(p, 12)]
        risk += (len(sel) - sum(sel)) / len(sel)
    out["aurc"] = risk / n
    hi = [r for p, r in items if round(p, 12) >= tau - 1e-9]
    out["share_at_090"] = len(hi) / n
    out["acc_at_090"] = sum(hi) / len(hi) if hi else float("nan")
    errors = sum(1 - r for _, r in items)
    if errors:
        slots, caught = trigger * n, 0.0
        for t in sorted(tps):                                   # lowest groups first; a group that does not fit counts in proportion
            grp = [r for p, r in items if round(p, 12) == t]
            take = min(len(grp), slots)
            caught += (take / len(grp)) * (len(grp) - sum(grp))
            slots -= take
            if slots <= 1e-12:
                break
        out["trigger_recall_20"] = caught / errors
    else:
        out["trigger_recall_20"] = float("nan")
    return out


class TestAgainstBruteForce(unittest.TestCase):
    def test_random_cases_with_many_ties(self):
        rng = random.Random(1)
        pool = [0.55, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]
        for _ in range(400):
            n = rng.randint(1, 30)
            rows = [(rng.choice(pool), rng.random() < 0.7, None, None) for _ in range(n)]
            got = stats(rows)
            want = brute([(p, 1 if r else 0) for p, r, _, _ in rows])
            for k, v in want.items():
                if isinstance(v, float) and math.isnan(v):
                    self.assertTrue(math.isnan(got[k]), (k, rows))
                else:
                    self.assertAlmostEqual(got[k], v, places=9, msg=f"{k} {rows}")

    def test_multiplicities_equal_repeating_the_items(self):
        rng = random.Random(2)
        pool = [0.55, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]
        for _ in range(200):
            g = rng.randint(1, 8)
            rows, groups = [], []
            for gi in range(g):
                for _m in range(rng.randint(1, 3)):
                    rows.append((rng.choice(pool), rng.random() < 0.6, f"g{gi}", None))
            P, A, *_ = build(rows)
            cnt = [rng.randint(0, 3) for _ in range(P.n_units)]
            if sum(cnt) == 0:
                continue
            got = S.task_stats(P, A, cnt)
            expanded = []
            for u, members in enumerate(P.members):
                for _c in range(cnt[u]):
                    expanded += [(rows[j][0], 1 if rows[j][1] else 0) for j in members]
            want = brute(expanded)
            for k, v in want.items():
                if isinstance(v, float) and math.isnan(v):
                    self.assertTrue(math.isnan(got[k]))
                else:
                    self.assertAlmostEqual(got[k], v, places=9, msg=k)


class TestRunsCountOnlyWhenTheyFit(unittest.TestCase):
    """a run needs a line for 99% of the items and the items it was made on must be the items of the task"""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.old = S.HERE
        S.HERE = self.dir
        os.makedirs(f"{self.dir}/tasks/t")
        os.makedirs(f"{self.dir}/runs/s")
        items = mk_items("t", [{"gold": "yes"} if i % 2 else {"gold": "no"} for i in range(200)])
        with open(f"{self.dir}/tasks/t/items.jsonl", "w") as f:
            for it in items:
                it["state"] = "x"
                f.write(json.dumps(it) + "\n")
        tj = {"task": "t", "layer": "A", "title": "t", "decision": "d", "source": {}, "licence": "l", "redistribution": "r", "labels": "programmatic",
              "item_source": "generated", "metric": "accuracy", "chance": 0.5, "rows": 200, "question_type": "choice", "options": 2,
              "track": "core", "items_sha256": "aaa"}
        with open(f"{self.dir}/tasks/t/task.json", "w") as f:
            json.dump(tj, f)
        self.items = items

    def tearDown(self):
        S.HERE = self.old
        shutil.rmtree(self.dir)

    def write_run(self, n, errors=0):
        with open(f"{self.dir}/runs/s/t.jsonl", "w") as f:
            for i, it in enumerate(self.items[:n]):
                if i < errors:
                    f.write(json.dumps({"id": it["id"], "error": "too long"}) + "\n")
                else:
                    g = it["gold"]
                    f.write(json.dumps({"id": it["id"], "p": {g: 0.9, ("no" if g == "yes" else "yes"): 0.1}}) + "\n")

    def score(self, index=None):
        return S.task_worker(("t", [("s", f"{self.dir}/runs/s")], 20, None, index or {}))[1]["s"]

    def test_full_run_counts(self):
        self.write_run(200)
        r = self.score()
        self.assertNotIn("not_run", r)
        self.assertAlmostEqual(r["accuracy"], 1.0)

    def test_99_percent_of_the_items_is_enough_and_errors_count_as_lines(self):
        self.write_run(198)                                   # 198 of 200 = 99%
        r = self.score()
        self.assertNotIn("not_run", r)
        self.assertAlmostEqual(r["coverage"], 0.99)           # the two missing items are unanswered and wrong
        self.assertAlmostEqual(r["accuracy"], 0.99)

    def test_an_error_line_is_a_line_but_not_an_answer(self):
        self.write_run(200, errors=10)
        r = self.score()
        self.assertNotIn("not_run", r)
        self.assertAlmostEqual(r["coverage"], 0.95)
        self.assertAlmostEqual(r["accuracy"], 0.95)

    def test_the_length_of_the_thought_is_averaged_when_the_lines_carry_it(self):
        # every line has tokens = 100 (items 1..100) or 300 (items 101..200): the mean over the 200 items is 200
        with open(f"{self.dir}/runs/s/t.jsonl", "w") as f:
            for i, it in enumerate(self.items):
                g = it["gold"]
                f.write(json.dumps({"id": it["id"], "p": {g: 0.9, ("no" if g == "yes" else "yes"): 0.1}, "tokens": 100 if i < 100 else 300}) + "\n")
        self.assertAlmostEqual(self.score()["tokens_mean"], 200.0)
        self.write_run(200)                                   # lines without the field: no average
        self.assertNotIn("tokens_mean", self.score())

    def test_fewer_lines_than_99_percent_do_not_count(self):
        self.write_run(197)
        self.assertIn("not_run", self.score())

    def test_the_index_file_is_read_at_the_right_level(self):
        # runs_index.json keeps the entries under "runs"; a run recorded for other items must not be scored
        self.write_run(200)
        with open(f"{self.dir}/runs_index.json", "w") as f:
            json.dump({"runs": {"s/t": {"items_sha256": "bbb"}}, "rejected": {}}, f)
        self.assertIn("not_run", S.task_worker(("t", [("s", f"{self.dir}/runs/s")], 20, None, S.load_index()))[1]["s"])
        with open(f"{self.dir}/runs_index.json", "w") as f:
            json.dump({"runs": {"s/t": {"items_sha256": "aaa"}}, "rejected": {}}, f)
        self.assertNotIn("not_run", S.task_worker(("t", [("s", f"{self.dir}/runs/s")], 20, None, S.load_index()))[1]["s"])

    def test_the_stamp_written_by_a_runner_is_checked(self):
        # a runner writes {task: sha256 of the items file} into the run folder; a stamp that differs from items_sha256 of the task: not run
        self.write_run(200)
        with open(f"{self.dir}/runs/s/_items.json", "w") as f:
            json.dump({"t": "bbb"}, f)
        self.assertIn("not_run", self.score())
        with open(f"{self.dir}/runs/s/_items.json", "w") as f:
            json.dump({"t": "aaa", "other_task": "zzz"}, f)
        self.assertNotIn("not_run", self.score())
        os.remove(f"{self.dir}/runs/s/_items.json")                 # no stamp and no index entry: the ids decide
        self.assertNotIn("not_run", self.score())

    def test_a_run_made_on_other_items_does_not_count(self):
        self.write_run(200)
        self.assertIn("not_run", S.task_worker(("t", [("s", f"{self.dir}/runs/s")], 20, None, {"s/t": {"items_sha256": "bbb"}}))[1]["s"])
        self.assertNotIn("not_run", S.task_worker(("t", [("s", f"{self.dir}/runs/s")], 20, None, {"s/t": {"items_sha256": "aaa"}}))[1]["s"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
