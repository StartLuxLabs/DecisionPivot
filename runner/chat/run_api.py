#!/usr/bin/env python3
"""Ask a chat model through an OpenAI-compatible API for the core track of DecisionPivot (EVALUATION ONLY).  Python 3.9, standard library only.

    python3 runner/chat/run_api.py --keyfile KEYFILE --base-url BASE_URL --model deepseek-v4-pro --reasoning off  --out RAW.jsonl [--subsample FILE] [--workers 24]
    python3 runner/chat/run_api.py --keyfile KEYFILE --base-url BASE_URL --model glm-5.3         --reasoning low  --out RAW.jsonl
    python3 runner/chat/run_api.py --keyfile KEYFILE --base-url BASE_URL --model deepseek-v4-pro --reasoning high --subsample runner/chat/subsample_1296.json --out RAW.jsonl
--root DIR: the benchmark folder that holds tasks/<task>/ (default: data/ of the repository).  The model names are examples: --reasoning
sends the request fields that those two providers use (below); another provider may need other fields.

--reasoning off   DeepSeek: "thinking": {"type": "disabled"}, temperature 0                       (GLM rejects "disabled")
--reasoning low   GLM: "reasoning_effort": "low", temperature 0
--reasoning high  "thinking": {"type": "enabled"} and "reasoning_effort": "high"; the provider's default sampling (no temperature sent)
The key is read from the file named by --keyfile and put into the Authorization header only: it is never printed, logged or stored.
RAW.jsonl gets one line per request as soon as it finishes: {"id", "task", "model", "reasoning", "content", "reasoning_chars", "usage",
"finish_reason", "seconds", "attempts", "error"}.  The run can be restarted: ids with a reply (no error) in RAW.jsonl are skipped, ids with an
error are asked again.  Transient errors (network, timeout, HTTP 408/409/425/429/5xx, an empty reply) are retried twice (waits of 5 and 20 s).
--stream reads the reply as server-sent events (for long thoughts behind a proxy that closes idle connections)."""
import argparse
import concurrent.futures as cf
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

TRANSIENT_HTTP = {408, 409, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524, 525, 526, 527, 529}
lock = threading.Lock()
TOT = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "calls": 0, "errors": 0}


class Api:
    def __init__(self, keyfile, base):
        self.key = open(keyfile).read().strip()
        if not self.key:
            raise SystemExit("key file is empty")
        self.base = base.rstrip("/")

    def redact(self, s):
        return str(s).replace(self.key, "<key>")

    def body(self, model, reasoning, messages, max_tokens, stream):
        b = {"model": model, "messages": messages, "max_tokens": max_tokens, "stream": bool(stream)}
        if stream:
            b["stream_options"] = {"include_usage": True}
        if reasoning == "off":
            if model.startswith("glm"):
                raise SystemExit("glm-5.3 rejects thinking disabled: use --reasoning low")
            b.update({"thinking": {"type": "disabled"}, "temperature": 0})
        elif reasoning == "low":
            b.update({"reasoning_effort": "low", "temperature": 0})
        elif reasoning == "high":
            b.update({"thinking": {"type": "enabled"}, "reasoning_effort": "high"})
        else:
            raise SystemExit("--reasoning must be off, low or high")
        return b

    def chat(self, body, timeout):
        req = urllib.request.Request(f"{self.base}/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        if not body.get("stream"):
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = json.loads(r.read())
            ch = out["choices"][0]
            msg = ch.get("message") or {}
            return {"content": msg.get("content") or "",
                    "reasoning_chars": len(msg.get("reasoning_content") or msg.get("reasoning") or ""),
                    "usage": out.get("usage"), "finish_reason": ch.get("finish_reason")}
        content, rchars, usage, fin = [], 0, None, None
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    ev = json.loads(data)
                except Exception:
                    continue
                if ev.get("usage"):
                    usage = ev["usage"]
                for ch in ev.get("choices") or []:
                    d = ch.get("delta") or {}
                    if d.get("content"):
                        content.append(d["content"])
                    rchars += len(d.get("reasoning_content") or d.get("reasoning") or "")
                    if ch.get("finish_reason"):
                        fin = ch["finish_reason"]
        return {"content": "".join(content), "reasoning_chars": rchars, "usage": usage, "finish_reason": fin}


def one(api, task_id, task, messages, args):
    t0, err, res, attempt = time.time(), None, None, 0
    body = api.body(args.model, args.reasoning, messages, args.max_tokens, args.stream)
    for attempt, wait in enumerate((0, 5, 20), 1):
        time.sleep(wait)
        try:
            res = api.chat(body, args.timeout)
            if res["content"].strip():
                err = None
                break
            err = f"empty content ({res['finish_reason']})"
            if res["finish_reason"] == "length":           # the thought used up max_tokens: asking again gives the same
                break
        except urllib.error.HTTPError as e:
            try:
                detail = api.redact(e.read().decode("utf-8", "replace"))[:160].replace("\n", " ")
            except Exception:
                detail = ""
            err = f"HTTP {e.code} {detail}".strip()
            if e.code not in TRANSIENT_HTTP:
                break
        except Exception as e:  # noqa: BLE001  (network, timeout, broken stream, bad JSON)
            err = api.redact(f"{type(e).__name__}: {str(e)[:120]}")
    out = {"id": task_id, "task": task, "model": args.model, "reasoning": args.reasoning, "seconds": round(time.time() - t0, 1),
           "attempts": attempt, "error": err}
    if res:
        out.update({"content": res["content"], "reasoning_chars": res["reasoning_chars"], "usage": res["usage"],
                    "finish_reason": res["finish_reason"]})
    return out


def requests_to_do(args):
    """-> [(id, task, messages, sort key)] for the items of the run (the subsample, or all items of the core families)"""
    sub = json.load(open(args.subsample)) if args.subsample else None
    fams = args.tasks.split(",") if args.tasks else common.core_families()
    reqs = []
    for t in fams:
        items, tj = common.load_items(t), common.task_card(t)
        keep = set(sub[t]) if sub is not None else None
        for it in items:
            if keep is not None and it["id"] not in keep:
                continue
            msgs = common.build_messages(it)
            reqs.append((it["id"], t, msgs, len(msgs[1]["content"]), common.level_of(it, tj)))
    return reqs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyfile", required=True)
    ap.add_argument("--root", default=None, help="benchmark folder that holds tasks/ (default: data/)")
    ap.add_argument("--base-url", required=True, help="base URL of the OpenAI-compatible API, up to and including /v1")
    ap.add_argument("--model", required=True)
    ap.add_argument("--reasoning", required=True, choices=["off", "low", "high"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--subsample", default=None)
    ap.add_argument("--tasks", default=None)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--timeout", type=int, default=1500)
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="only the first N requests after ordering (pilot)")
    ap.add_argument("--per-task", type=int, default=None, help="pilot: N requests per family")
    ap.add_argument("--order", choices=["shuffle", "longest"], default="shuffle")
    ap.add_argument("--only-ids", default=None, help="JSON list of item ids: ask only these (a repair pass)")
    args = ap.parse_args()
    if args.root:
        common.BENCH = os.path.abspath(args.root)
    if args.max_tokens is None:
        args.max_tokens = {"off": 2048, "low": 8192, "high": 32768}[args.reasoning]
    api = Api(args.keyfile, args.base_url)
    reqs = requests_to_do(args)
    rng = random.Random(common.SEED)
    if args.order == "shuffle":
        rng.shuffle(reqs)
    else:                                                      # heavy items first: the long thoughts do not end up as the tail of the run
        reqs.sort(key=lambda r: (-(r[4] or 0), -r[3]))
    if args.only_ids:
        want = set(json.load(open(args.only_ids)))
        reqs = [r for r in reqs if r[0] in want]
    if args.per_task:
        seen, keep = {}, []
        for r in reqs:
            if seen.get(r[1], 0) < args.per_task:
                seen[r[1]] = seen.get(r[1], 0) + 1
                keep.append(r)
        reqs = keep
    if args.limit:
        reqs = reqs[:args.limit]
    done = set()
    if os.path.exists(args.out):
        for line in open(args.out, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("error") is None and (r.get("content") or "").strip():
                done.add(r["id"])
    todo = [r for r in reqs if r[0] not in done]
    print(f"{args.model} reasoning={args.reasoning}: {len(todo)} to do ({len(done)} done), {args.workers} workers, "
          f"max_tokens {args.max_tokens}, stream {args.stream}", flush=True)
    t0, n = time.time(), 0
    with open(args.out, "a", encoding="utf-8") as f, cf.ThreadPoolExecutor(args.workers) as ex:
        futs = [ex.submit(one, api, r[0], r[1], r[2], args) for r in todo]
        for fut in cf.as_completed(futs):
            res = fut.result()
            with lock:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
                f.flush()
            n += 1
            u = res.get("usage") or {}
            TOT["prompt_tokens"] += u.get("prompt_tokens", 0) or 0
            TOT["completion_tokens"] += u.get("completion_tokens", 0) or 0
            TOT["reasoning_tokens"] += ((u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)) or 0
            TOT["calls"] += 1
            TOT["errors"] += res["error"] is not None
            if n % 50 == 0 or n == len(todo):
                print(f"{args.model} {args.reasoning}: {n}/{len(todo)}, {TOT['errors']} errors, {(time.time() - t0) / 60:.1f} min, "
                      f"tokens in {TOT['prompt_tokens']:,} out {TOT['completion_tokens']:,} (thought {TOT['reasoning_tokens']:,})", flush=True)
    print("USAGE", json.dumps(dict(TOT, model=args.model, reasoning=args.reasoning, minutes=round((time.time() - t0) / 60, 1))), flush=True)


if __name__ == "__main__":
    main()
