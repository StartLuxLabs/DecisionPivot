#!/usr/bin/env python3
"""Turn the raw replies of a chat model into answer files of DecisionPivot (EVALUATION ONLY).  Python 3.9, standard library only.
    python3 runner/chat/collect.py RAW.jsonl SYSTEM [--root DIR] [--runs runs] [--stats FILE]
--root DIR: the benchmark folder that holds tasks/<task>/ (default: data/); --runs: the folder of the run folders (default: runs/ of the
repository).

RAW.jsonl is the file written by run_api.py.  For every item that has a reply one line goes to <runs>/SYSTEM/<task>.jsonl:
    {"id", "p": {key: probability}, "choice", "tokens", "closed", "prompt_tokens", "completion_tokens", "reasoning_tokens", "flag", "notes"}
  p        the verbalised probabilities, normalised over the item's option keys (the scorer normalises again); the top option of the scorer is
           the largest of them.  A tie for the largest is resolved in favour of the stated choice (note "tie_to_choice").
  flag     "probabilities_unparsed": the reply named an option but its probabilities did not parse: p is 1.0 on the option, 0.0 elsewhere.
  tokens   the length of the thought in tokens as the API reports it (reasoning tokens); only for the runs with reasoning (low, high).
  closed   whether the reply ended by itself (finish_reason "stop") and not at the limit of max_tokens.
An item whose replies all failed gets {"id", "error": "..."} (API error after the retries, reply cut at max_tokens, or no option and no
probabilities in the reply); the scorer counts it as unanswered and wrong.  An item that was never asked has no line.
_items.json in the run folder holds the SHA-256 of every items file the run was made on (the scorer reads it); v1.1: the stamps of
families that the raw file does not cover (files carried over from v1.0) are kept.
The statistics (failure rates, token totals, agreement of the stated choice with the largest probability, accuracy of the stated choice) are
written to --stats."""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("system")
    ap.add_argument("--root", default=None, help="benchmark folder that holds tasks/ (default: data/)")
    ap.add_argument("--runs", default=os.path.join(common.REPO, "runs"))
    ap.add_argument("--stats", default=None)
    ap.add_argument("--index", default="", help="runs_index.json to record the files in (default '' = none)")
    args = ap.parse_args()
    if args.root:
        common.BENCH = os.path.abspath(args.root)
    fams = common.core_families()
    items = {}
    for t in fams:
        for it in common.load_items(t):
            items[it["id"]] = (t, it)
    last = {}                                                  # id -> the best record: a reply beats an error, later beats earlier
    with open(args.raw, encoding="utf-8") as f:
        for l in f:
            try:
                r = json.loads(l)
            except Exception:
                continue
            ok = r.get("error") is None and (r.get("content") or "").strip() != ""
            if r["id"] not in last or ok or not last[r["id"]][0]:
                last[r["id"]] = (ok, r)
    out_dir = f"{args.runs}/{args.system}"
    os.makedirs(out_dir, exist_ok=True)
    lines = collections.defaultdict(list)
    st = collections.defaultdict(collections.Counter)          # family or "ALL" -> counters
    sums = collections.defaultdict(lambda: collections.defaultdict(float))
    for rid, (ok, r) in last.items():
        if rid not in items:
            continue
        task, it = items[rid]
        keys = list(common.option_map(it["questions"]["q"]))
        u = r.get("usage") or {}
        d = u.get("completion_tokens_details") or {}
        rt = d.get("reasoning_tokens")
        row = {"id": rid}
        cat = "api_error"
        pr = None
        if ok:
            pr = common.parse_reply(r.get("content"), keys)
            cat = pr["status"]
        elif r.get("finish_reason") == "length" or "(length)" in (r.get("error") or ""):
            cat = "length"
        elif "empty content" in (r.get("error") or ""):
            cat = "unparsed"                                        # the model answered with nothing, on every attempt: no usable reply
        if pr and pr["status"] != "unparsed":
            row.update({"p": {k: round(x, 9) for k, x in pr["p"].items()}, "choice": pr["choice"]})
            if pr["status"] == "choice_only":
                row["flag"] = "probabilities_unparsed"
            if pr["notes"]:
                row["notes"] = pr["notes"]
        else:
            row["error"] = {"unparsed": "reply has neither a usable option nor probabilities" if ok else "empty reply on every attempt",
                            "length": "reply cut at max_tokens", "api_error": r.get("error") or "no reply"}[cat]
        if r.get("reasoning") in ("low", "high") and rt is not None:
            row["tokens"] = rt
        if r.get("finish_reason"):
            row["closed"] = r["finish_reason"] == "stop"
        for k_out, v in (("prompt_tokens", u.get("prompt_tokens")), ("completion_tokens", u.get("completion_tokens")), ("reasoning_tokens", rt)):
            if v is not None:
                row[k_out] = v
        lines[task].append((it, row))
        for key in (task, "ALL"):
            c = st[key]
            c["requested"] += 1
            c[cat] += 1
            c["attempts_gt1"] += (r.get("attempts") or 1) > 1
            if pr:
                for n in pr["notes"]:
                    c["note_" + n] += 1
            if "p" in row:
                gold = str(it["gold"])
                c["choice_right"] += row["choice"] == gold
                top = max(keys, key=lambda k: row["p"][k])
                c["top_right"] += top == gold
            s = sums[key]
            s["prompt_tokens"] += u.get("prompt_tokens") or 0
            s["completion_tokens"] += u.get("completion_tokens") or 0
            s["reasoning_tokens"] += rt or 0
            s["seconds"] += r.get("seconds") or 0
            c["finish_" + str(r.get("finish_reason"))] += 1
    stamps = {}
    for t in fams:
        if not lines[t]:
            continue
        order = {it["id"]: n for n, it in enumerate(common.load_items(t))}
        with open(f"{out_dir}/{t}.jsonl", "w", encoding="utf-8") as f:
            for it, row in sorted(lines[t], key=lambda x: order[x[0]["id"]]):
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        stamps[t] = common.items_sha256(t)
    stamp_path = f"{out_dir}/_items.json"
    if os.path.exists(stamp_path):                             # v1.1: keep the stamps of the families this raw file does not cover
        try:
            prev = json.load(open(stamp_path, encoding="utf-8"))
        except Exception:
            prev = {}
        stamps = dict(prev, **stamps)
    with open(stamp_path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(stamps.items())), f, indent=1)
    if args.index and stamps:                                  # v1.1: record the source of every file written in runs_index.json
        import hashlib
        import time
        ix = json.load(open(args.index, encoding="utf-8")) if os.path.exists(args.index) else {"runs": {}, "rejected": {}}
        for t in stamps:
            data = open(f"{out_dir}/{t}.jsonl", "rb").read()
            ix.setdefault("runs", {})[f"{args.system}/{t}"] = {
                "source": f"general_llm/raw/{os.path.basename(args.raw)} (chat-model API run, collected {time.strftime('%Y-%m-%d %H:%M')})",
                "basis": "items_sha256", "items_sha256": stamps[t], "lines": data.count(b"\n"), "sha256": hashlib.sha256(data).hexdigest()}
            ix.setdefault("rejected", {}).pop(f"{args.system}/{t}", None)
        with open(args.index, "w", encoding="utf-8") as f:
            json.dump(ix, f, indent=1, sort_keys=True)
    stats = {k: dict(v, **{"sum_" + a: b for a, b in sums[k].items()}) for k, v in st.items()}
    if args.stats:
        os.makedirs(os.path.dirname(os.path.abspath(args.stats)), exist_ok=True)
        with open(args.stats, "w", encoding="utf-8") as f:
            json.dump({"system": args.system, "raw": os.path.basename(args.raw), "stats": stats}, f, indent=1, sort_keys=True)
    a = stats.get("ALL", {})
    n = a.get("requested", 0)
    print(f"{args.system}: {n} items with a reply or an error; ok {a.get('ok', 0)}, probabilities unparsed {a.get('choice_only', 0)}, "
          f"unparsed {a.get('unparsed', 0)}, cut at max_tokens {a.get('length', 0)}, API errors {a.get('api_error', 0)}; "
          f"tokens in {int(a.get('sum_prompt_tokens', 0)):,} out {int(a.get('sum_completion_tokens', 0)):,} (thought {int(a.get('sum_reasoning_tokens', 0)):,})")


if __name__ == "__main__":
    main()
