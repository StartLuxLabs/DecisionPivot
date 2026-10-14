"""Shared pieces of the general-chat-model baselines on the core track of DecisionPivot (EVALUATION ONLY: the items are never written
into a training directory and never go into a prompt of a model that is being trained).  Python 3.9, standard library only.

  * the family list and the item files of the core track,
  * the prompt (the wording of runner/README.md for "a model without a typed interface", extended by the request for probabilities),
  * the parser of a reply (verbalised probabilities) with the rules that are counted in README.md.
"""
import collections
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))       # repository root (this file is runner/chat/common.py)
BENCH = os.path.join(REPO, "data")                  # the benchmark folder that holds tasks/<task>/; the scripts set it from --root
SEED = 20261008


def core_families():
    out = []
    for t in sorted(os.listdir(f"{BENCH}/tasks")):
        p = f"{BENCH}/tasks/{t}/task.json"
        if os.path.isfile(p) and json.load(open(p, encoding="utf-8")).get("track") == "core":
            out.append(t)
    return out


def load_items(task):
    with open(f"{BENCH}/tasks/{task}/items.jsonl", encoding="utf-8") as f:
        return [json.loads(l) for l in f]


def task_card(task):
    with open(f"{BENCH}/tasks/{task}/task.json", encoding="utf-8") as f:
        return json.load(f)


def level_of(item, tj):
    """the level (1, 2, 3) of an item as score.py reads it: from the declared dial (`level_from`) or from `meta.level`; None if the family has none"""
    lf = tj.get("level_from")
    if lf:
        cur = item
        for part in lf["field"].split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        return lf["values"].get(str(cur)) if cur is not None else None
    lv = (item.get("meta") or {}).get("level")
    return lv if isinstance(lv, int) and not isinstance(lv, bool) and lv in (1, 2, 3) else None


def items_sha256(task):
    with open(f"{BENCH}/tasks/{task}/items.jsonl", "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------------------------------------ prompt
# runner/README.md: "system: You answer one typed question about the state you are given. Reply with the key of exactly one option, copied as it is
# written, and nothing else."  A chat model returns an answer, not a probability, so the same sentence is followed by the request for the
# probabilities; "Reply with one key." at the end of the user message becomes the request for the JSON object (with the keys of the item).
SYSTEM = ("You answer one typed question about the state you are given. Reply with the key of exactly one option, copied as it is written, "
          "and a probability for every option, as one JSON object and nothing else: "
          "{\"choice\": \"<the key of the option you pick>\", \"probabilities\": {\"<key>\": <probability>, ...}}. "
          "\"probabilities\" has one number between 0 and 1 for every option key, the numbers add up to 1, and each number is how likely you "
          "think it is that this option is the right one.")


def option_map(q):
    """{key: option text} in the order of the item (the order the options are listed in)"""
    c = q.get("criteria")
    if q["type"] == "noul":
        return {"yes": "yes", "no": "no"}
    return {str(i): t for i, t in enumerate(c)} if isinstance(c, list) else dict(c)


def state_text(it):
    return it["state"] if isinstance(it["state"], str) else json.dumps(it["state"], ensure_ascii=False, indent=1)


def user_prompt(it):
    q = it["questions"]["q"]
    opts = option_map(q)
    skeleton = "{\"choice\": \"<key>\", \"probabilities\": {" + ", ".join(f"\"{k}\": <p>" for k in opts) + "}}"
    return (f"STATE\n{state_text(it)}\n\nQUESTION\n{q['instructions']}\n\nOPTIONS (key: meaning)\n"
            + "\n".join(f"{k}: {v}" for k, v in opts.items())
            + f"\n\nReply with the JSON object, in this form:\n{skeleton}")


def build_messages(it):
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_prompt(it)}]


# ------------------------------------------------------------------------------------------------ parsing
def _fenced(text):
    m = re.findall(r"```(?:json|JSON)?\s*(.*?)```", text, re.S)
    return [x for x in m if "{" in x]


def _objects(text):
    """top-level balanced {...} blocks of a text, in order of appearance (string-aware)"""
    out, depth, start, in_str, esc, quote = [], 0, None, False, False, None
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
            continue
        if ch in "\"'" and depth > 0:
            in_str, quote = True, ch
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                out.append(text[start:i + 1])
                start = None
    return out


def _loads(s):
    for attempt in (s, re.sub(r",\s*([}\]])", r"\1", s)):
        try:
            return json.loads(attempt)
        except Exception:
            pass
    t = re.sub(r",\s*([}\]])", r"\1", s)
    t = re.sub(r"(?<![\w\"])'([^'\n]*)'(?![\w\"])", r'"\1"', t)           # single-quoted strings
    t = re.sub(r"\b(True|False|None)\b", lambda m: {"True": "true", "False": "false", "None": "null"}[m.group(1)], t)
    try:
        return json.loads(t)
    except Exception:
        return None


def _num(v):
    """a number the model wrote: a number, a numeric string, or a string with a percent sign (the sign is dropped: a list of percentages is
    normalised like any other list of numbers, and the scale is judged from the sum)"""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.fullmatch(r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*%?\s*", v)
        if m:
            return float(m.group(1))
    return None


def match_key(s, keys):
    """map a string the model wrote onto one option key, or None"""
    if s is None or isinstance(s, (dict, list, bool)):
        return None
    s = str(s).strip().strip("`\"' ")
    if not s:
        return None
    if s in keys:
        return s
    low = {k.lower(): k for k in keys}
    if len(low) == len(keys) and s.lower() in low:
        return low[s.lower()]
    head = re.split(r"[:\s(\[]", s, maxsplit=1)[0].strip("`\"'.,;")
    if head in keys:
        return head
    if len(low) == len(keys) and head.lower() in low:
        return low[head.lower()]
    hits = [k for k in keys if re.search(rf"(?<![A-Za-z0-9_\-]){re.escape(k)}(?![A-Za-z0-9_\-])", s, re.I)]
    return hits[0] if len(hits) == 1 else None


def parse_reply(content, keys):
    """-> dict(status, p, choice, psum, notes)
    status:  "ok"          probabilities parsed (p = normalised distribution over keys)
             "choice_only" the probabilities did not parse but a choice did (p = 1.0 on the choice)
             "unparsed"    neither (the line becomes an error)
    notes:   list of strings (counted in the README): "no_choice" (probabilities without a choice: the top option stands in),
             "partial_keys" (the probabilities named only some of the options), "extra_keys", "choice_not_top" (the stated choice is not the
             option with the largest probability), "psum_off" (the numbers do not add up to 1 within 0.02), "tie_to_choice" (a tie for the top
             probability resolved in favour of the stated choice by 1e-7)"""
    keys = list(keys)
    text = (content or "").strip()
    cands = []
    for blob in _fenced(text) + [text]:
        for o in _objects(blob):
            d = _loads(o)
            if isinstance(d, dict):
                cands.append(d)
    pick = None
    for d in reversed(cands):                                # the last object that looks like an answer
        if "choice" in d or "probabilities" in d or "answer" in d or any(match_key(k, keys) for k in d):
            pick = d
            break
    choice, raw_p, notes = None, None, []
    if pick is not None:
        choice = match_key(pick.get("choice", pick.get("answer")), keys)
        raw_p = pick.get("probabilities", pick.get("probability", pick.get("p")))
        if raw_p is None and all(match_key(k, keys) or k in ("choice", "answer") for k in pick) and any(match_key(k, keys) for k in pick):
            raw_p = {k: v for k, v in pick.items() if k not in ("choice", "answer")}
    if choice is None and pick is None:                      # no JSON at all: a bare key as the whole reply
        choice = match_key(text, keys) if len(text) < 80 else None
    p, psum = None, None
    if isinstance(raw_p, dict):
        v, extra = {}, 0
        for k, x in raw_p.items():
            kk = match_key(k, keys)
            n = _num(x)
            if kk is None or n is None:
                extra += 1
                continue
            v[kk] = v.get(kk, 0.0) + max(0.0, n)
        if v and sum(v.values()) > 0:
            p, psum = {k: v.get(k, 0.0) for k in keys}, sum(v.values())
            if len(v) < len(keys):
                notes.append("partial_keys")
            if extra:
                notes.append("extra_keys")
    elif isinstance(raw_p, list) and len(raw_p) == len(keys):  # a list in the order of the options
        n = [_num(x) for x in raw_p]
        if all(x is not None for x in n) and sum(max(0.0, x) for x in n) > 0:
            p, psum = {k: max(0.0, x) for k, x in zip(keys, n)}, sum(max(0.0, x) for x in n)
    if p is not None:
        scale = psum / 100.0 if (psum > 1.5 and abs(psum - 100.0) <= 2.0) else psum         # percentages that add up to 100 are fine
        if abs(scale - 1.0) > 0.02:
            notes.append("psum_off")
        z = sum(p.values())
        p = {k: x / z for k, x in p.items()}
        top = max(keys, key=lambda k: p[k])
        if choice is None:
            notes.append("no_choice")
            choice = top
        elif p[choice] < p[top] - 1e-12:
            notes.append("choice_not_top")
        elif p[choice] == p[top] and top != choice:
            p[choice] += 1e-7                                  # tie for the top: the stated choice is the top option
            z = sum(p.values())
            p = {k: x / z for k, x in p.items()}
            notes.append("tie_to_choice")
        return {"status": "ok", "p": p, "choice": choice, "psum": psum, "notes": notes}
    if choice is not None:
        return {"status": "choice_only", "p": {k: (1.0 if k == choice else 0.0) for k in keys}, "choice": choice, "psum": None, "notes": notes}
    return {"status": "unparsed", "p": None, "choice": None, "psum": None, "notes": notes}
