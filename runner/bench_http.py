"""Run DecisionPivot tasks against a typed-decision endpoint, POST <url>/v1/systemone (EVALUATION ONLY) - for decision models that
are served by their own code (for example an open release behind its own server) or by a hosted typed-decision API.
    python3 runner/bench_http.py --url http://127.0.0.1:9701 --model NAME --out runs/NAME [--bench DIR] [--tasks a,b]
        [--workers 32] [--max-chars 400000] [--api-key-env VAR]
The request body is {"model", "state", "questions"} of the item, exactly as in items.jsonl; the answer object of the reply
(its "answers" field) is stored as it is.  --bench DIR: the benchmark folder that holds tasks/<task>/ (default: data/ of the
repository).  --api-key-env VAR: send the value of the environment variable VAR as "Authorization: Bearer ..." (the key is read
from the environment only; it is never written to a file or printed).
Writes RUN_DIR/<task>.jsonl, one line per item: {"id", "answers": {"q": ANSWER}} or {"id", "error"}; resumable
(answered ids are skipped; lines with an error are tried again on the next call)."""
import argparse
import concurrent.futures as cf
import json
import os
import time
import urllib.error
import urllib.request


def stamp_items(out_dir, bench, task):
    """record the SHA-256 of the items file the run is made on in OUT_DIR/_items.json (read by score.py: a run on other items does not count)"""
    import hashlib
    with open(f"{bench}/tasks/{task}/items.jsonl", "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    p = f"{out_dir}/_items.json"
    d = {}
    if os.path.exists(p):
        try:
            with open(p) as f:
                d = json.load(f)
        except Exception:
            d = {}
    d[task] = sha
    with open(p + f".{os.getpid()}.tmp", "w") as f:
        json.dump(d, f, indent=1)
    os.replace(p + f".{os.getpid()}.tmp", p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--bench", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--tasks", default="")
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--max-chars", type=int, default=400000)
    ap.add_argument("--api-key-env", default="", help="name of an environment variable that holds an API key (sent as a Bearer token)")
    a = ap.parse_args()
    headers = {"Content-Type": "application/json"}
    if a.api_key_env:
        key = os.environ.get(a.api_key_env, "").strip()
        if not key:
            raise SystemExit(f"the environment variable {a.api_key_env} is empty")
        headers["Authorization"] = "Bearer " + key
    tasks = a.tasks.split(",") if a.tasks else sorted(
        t for t in os.listdir(f"{a.bench}/tasks") if os.path.isfile(f"{a.bench}/tasks/{t}/items.jsonl"))
    os.makedirs(a.out, exist_ok=True)

    def one(it):
        st = it["state"]
        if len(st if isinstance(st, str) else json.dumps(st)) > a.max_chars:
            return {"id": it["id"], "error": f"state longer than {a.max_chars} characters"}
        body = json.dumps({"model": a.model, "state": st, "questions": it["questions"]}).encode()
        err = None
        for wait in (0, 2, 10, 30):
            time.sleep(wait)
            try:
                req = urllib.request.Request(f"{a.url}/v1/systemone", data=body, headers=headers)
                with urllib.request.urlopen(req, timeout=600) as r:
                    o = json.loads(r.read())
                return {"id": it["id"], "answers": o.get("answers")}
            except urllib.error.HTTPError as e:
                err = f"HTTP {e.code}"
                if e.code in (400, 401, 403, 413, 422):          # a request or a key that a retry cannot fix
                    break
            except Exception as e:  # noqa: BLE001
                err = type(e).__name__
        return {"id": it["id"], "error": err}

    for task in tasks:
        items = [json.loads(l) for l in open(f"{a.bench}/tasks/{task}/items.jsonl", encoding="utf-8")]
        stamp_items(a.out, a.bench, task)
        out = f"{a.out}/{task}.jsonl"
        keep = {}
        if os.path.exists(out):
            for l in open(out):
                if l.endswith("\n"):
                    try:
                        x = json.loads(l)
                    except Exception:
                        continue
                    if x.get("answers"):
                        keep[x["id"]] = l
        todo = [it for it in items if it["id"] not in keep]
        t0, n_err = time.time(), 0
        with open(out + ".tmp", "w") as f:
            for l in keep.values():
                f.write(l)
            with cf.ThreadPoolExecutor(a.workers) as ex:
                for res in ex.map(one, todo):
                    n_err += "error" in res
                    f.write(json.dumps(res, ensure_ascii=False) + "\n")
        os.replace(out + ".tmp", out)
        print(json.dumps({"task": task, "items": len(items), "new": len(todo), "errors": n_err,
                          "minutes": round((time.time() - t0) / 60, 2)}), flush=True)
    print("BENCH_HTTP_DONE", flush=True)


if __name__ == "__main__":
    main()
