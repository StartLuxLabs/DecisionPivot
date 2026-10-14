#!/usr/bin/env python3
"""Hand-worked cases for the reader of the chat-model replies (runner/chat/common.parse_reply) and for the prompt.
    python3 tests/test_chat_parse.py
Python 3.9, standard library only; prints OK and the number of cases."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runner", "chat"))
import common  # noqa: E402

K = ["R1", "R2", "R3", "none"]
n = 0


def check(cond, what):
    global n
    n += 1
    assert cond, what


def near(a, b, eps=1e-6):
    return abs(a - b) < eps


# a plain reply
r = common.parse_reply('{"choice": "R3", "probabilities": {"R1": 0.1, "R2": 0.1, "R3": 0.7, "none": 0.1}}', K)
check(r["status"] == "ok" and r["choice"] == "R3" and near(r["p"]["R3"], 0.7) and r["notes"] == [], "plain reply")

# code fence with prose around it, lower-case key, percentages
r = common.parse_reply('My answer:\n```json\n{"choice": "r3", "probabilities": {"R1": "5%", "R2": "10%", "r3": "80%", "none": "5%"}}\n```\nDone.', K)
check(r["status"] == "ok" and r["choice"] == "R3" and near(r["p"]["R3"], 0.8) and "psum_off" not in r["notes"], "fence, case, percentages")

# numbers that do not add up are normalised and noted
r = common.parse_reply('{"choice": "R3", "probabilities": {"R1": 0.3, "R2": 0.1, "R3": 0.8, "none": 0.05}}', K)
check(r["status"] == "ok" and "psum_off" in r["notes"] and near(sum(r["p"].values()), 1.0) and near(r["p"]["R3"], 0.8 / 1.25), "normalised")

# the stated choice is not the largest probability: the probabilities stand and the case is noted
r = common.parse_reply('{"choice": "R3", "probabilities": {"R1": 0.1, "R2": 0.1, "R3": 0.1, "none": 0.7}}', K)
check(r["status"] == "ok" and r["choice"] == "R3" and "choice_not_top" in r["notes"] and max(r["p"], key=r["p"].get) == "none", "choice not top")

# a tie for the largest probability goes to the stated choice
r = common.parse_reply('{"choice": "no", "probabilities": {"yes": 0.5, "no": 0.5}}', ["yes", "no"])
check(r["status"] == "ok" and "tie_to_choice" in r["notes"] and r["p"]["no"] > r["p"]["yes"], "tie")

# probabilities missing: the option with probability 1.0 and the flag of collect.py
r = common.parse_reply('{"choice": "R2"}', K)
check(r["status"] == "choice_only" and r["p"] == {"R1": 0.0, "R2": 1.0, "R3": 0.0, "none": 0.0}, "choice only")
r = common.parse_reply('{"choice": "none", "probabilities": {"yes": 1}}', K)
check(r["status"] == "choice_only" and r["choice"] == "none", "unknown keys in the probabilities")

# probabilities without a choice: the top option stands in
r = common.parse_reply('{"probabilities": {"R1": 0.0, "R2": 0.0, "R3": 0.9, "none": 0.1}}', K)
check(r["status"] == "ok" and r["choice"] == "R3" and "no_choice" in r["notes"], "no choice")

# single quotes, trailing comma, a list in the order of the options, a choice with a trailing explanation
r = common.parse_reply("{'choice': 'R2', 'probabilities': {'R1': 0.0, 'R2': 1.0, 'R3': 0.0, 'none': 0.0},}", K)
check(r["status"] == "ok" and r["choice"] == "R2", "single quotes")
r = common.parse_reply('{"choice": "R3", "probabilities": [0.1, 0.2, 0.6, 0.1]}', K)
check(r["status"] == "ok" and near(r["p"]["R2"], 0.2), "list")
r = common.parse_reply('{"choice": "R2: the batch violates it", "probabilities": {"R1": 0, "R2": 1, "R3": 0, "none": 0}}', K)
check(r["status"] == "ok" and r["choice"] == "R2", "choice with an explanation")

# nothing usable
for bad in ("", "I think it is R3 or maybe R2", "{}", "[1, 2]"):
    check(common.parse_reply(bad, K)["status"] == "unparsed", f"unparsed: {bad!r}")

# keys that look alike are not confused: "A1" does not match inside "A10"
r = common.parse_reply('{"choice": "A10", "probabilities": {"A1": 0.1, "A10": 0.9}}', ["A1", "A10"])
check(r["choice"] == "A10" and near(r["p"]["A10"], 0.9), "A1 / A10")

# the prompt: wording of runner/README.md, options in the order of the item, the keys of the item in the form line
it = {"state": {"a": 1}, "questions": {"q": {"type": "choice", "instructions": "Is it?", "criteria": {"yes": "It is.", "no": "It is not."}}}}
msgs = common.build_messages(it)
u = msgs[1]["content"]
check(msgs[0]["role"] == "system" and msgs[0]["content"].startswith("You answer one typed question about the state you are given."), "system message")
check(u.startswith('STATE\n{\n "a": 1\n}\n\nQUESTION\nIs it?\n\nOPTIONS (key: meaning)\nyes: It is.\nno: It is not.\n\nReply with the JSON object'), "user message")
check(u.rstrip().endswith('{"choice": "<key>", "probabilities": {"yes": <p>, "no": <p>}}'), "form line with the keys of the item")
print("OK", n, "cases")
