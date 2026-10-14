"""Task mind2web_element (layer D, public test set): "which of the listed page elements should the agent act on next?"
Built from the test splits of Multimodal-Mind2Web (official Hugging Face data set osunlp/Multimodal-Mind2Web, license tag openrail;
the text of Mind2Web, Deng et al. 2023, arXiv:2306.06070, aligned with screenshots).  TEXT columns only: the screenshots and
`raw_html` are never read.  One row of the data = one step (action) of a task: the confirmed task, the action strings, the
cleaned HTML of the page before the step, the target element (`pos_candidates`) and the other candidate elements
(`neg_candidates`).
    python3 reference/build/build_mind2web_element.py CACHE_DIR      (the download cache, or its folder mind2web/; needs pyarrow)
The source files are read from the cache (fetched once from the pinned commit if missing; streamed to disk) and their checksums
are verified, so the output is the same on every run.  No item text is written or edited here.
Files.  Only shards of at most 300 MB were used (the other shards are 303-430 MB): test_task shards 1-4 of 5, test_website
shards 1-3 of 4, test_domain shard 4 of 11.  The rows of the splits that are in the other shards are not available here.
Rows.  A row is used if it has a positive candidate (the first of `pos_candidates`, as the Mind2Web code does), the positive is
found in the cleaned HTML and at least nine different negative candidates (other text than the positive) can be drawn.
Options.  Ten per row: the positive and nine negatives drawn from the row's `neg_candidates` with a generator seeded with
20261007 and the action id (a shuffled order of the negatives; a negative whose option text is the same as the positive's or as an
already drawn one is skipped), shuffled together with the positive by the same generator; keys A..J.  The option text is the
cleaned representation of the element taken from the row's `cleaned_html` (the data set's own cleaned page, in which every
element carries its backend_node_id): the opening tag with the attributes kept there (without backend_node_id), the visible
text of the element and its descendants, the closing tag; an element without text is written as an empty tag; cut at 300
characters.  state = {task: the confirmed task, previous_actions: the action strings of the task before this step}.
Sampling.  Per split the rows with a positive are sorted by action id and put in a random order (random.Random(20261007)); the
first n valid rows are taken, n = 333, 333, 334 for test_task, test_website, test_domain (equal shares, so that each kind of
generalisation counts the same).  The final row order is shuffled with the same generator."""
import collections
import hashlib
import json
import os
import random
import sys
import urllib.request
from html.parser import HTMLParser

import pyarrow.parquet as pq

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "generated", "reference")   # writes HERE/tasks/<task>/
TASK, SOURCE, SEED, CUT, N_NEG = "mind2web_element", "mind2web", 20261007, 300, 9
COMMIT = "1b4c6a8cf9f77b7a5e0d641959935c80c4a05889"   # main, last modified 2024-06-05, read on 2026-10-07
URL = f"https://huggingface.co/datasets/osunlp/Multimodal-Mind2Web/resolve/{COMMIT}/"
FILES = {"data/test_task-00001-of-00005-bdd2cef984845c42.parquet": "4e1d73221736b0d83a2e10a9e8dac96a62da543d0e278af0c6b4df9d112d6062",
         "data/test_task-00002-of-00005-e2696e51f1c78db8.parquet": "671b018cb997825da2c9ac0dcc6fa67d1d98e7f48261baedce82e057277c89fc",
         "data/test_task-00003-of-00005-944419f61d7cf1fb.parquet": "18d4753123608aa5227fbf3f25f521f8f48133f70a25a70c65b5683044857368",
         "data/test_task-00004-of-00005-a3a487e53da307b4.parquet": "d2a207d9e3feb6cf8e3a3a1504de7c51913f61de1d2e6e4069c883678cd8d4b7",
         "data/test_website-00001-of-00004-b0b6abaa088e90d8.parquet": "100c84f000045cb2b5f0218753a6417d302708a24ca6c7263d7392d5a40be1b6",
         "data/test_website-00002-of-00004-11198eb4fc38a82b.parquet": "c43299672781d6ec8972d5b7524778c348e5a386e788a424d65276f9c236adf9",
         "data/test_website-00003-of-00004-3019191fc3984b5e.parquet": "2e9227f8b80f0e75b490698adc45862587d23fcd139b559de0c0b59971fcfd59",
         "data/test_domain-00004-of-00011-d94e067efdd549d4.parquet": "8fac667f3c8acc5005d69a663e28702c2682bbaccc24a4cd291bafeb0019d1b8"}
SPLITS = {"test_task": 333, "test_website": 333, "test_domain": 334}      # rows per split
SPLIT_SIZE = {"test_task": (1339, 5), "test_website": (1019, 4), "test_domain": (4060, 11)}   # rows and shards on the card
KEYS = "ABCDEFGHIJ"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
INSTRUCTIONS = "Which of the listed page elements should the agent act on next to complete the task?"
COLS = ["action_uid", "operation", "pos_candidates", "neg_candidates", "website", "domain", "subdomain", "annotation_id",
        "confirmed_task", "action_reprs", "target_action_index", "target_action_reprs", "cleaned_html"]


def fetch(cache, name):
    """Path of one source file in the cache (streamed once from the pinned official URL), SHA-256 verified."""
    path = os.path.join(cache, name)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with urllib.request.urlopen(URL + name, timeout=600) as r, open(path + ".part", "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        os.replace(path + ".part", path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != FILES[name]:
        sys.exit(f"{path}: checksum differs from the file this task was built from ({URL + name})")
    return path


def dumps(item):
    """One JSON line; the three characters that str.splitlines() takes for line ends are written as JSON escapes."""
    return (json.dumps(item, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
            .replace("\x85", "\\u0085"))


class Node:
    __slots__ = ("tag", "attrs", "kids", "text")

    def __init__(self, tag, attrs):
        self.tag, self.attrs, self.kids, self.text = tag, attrs, [], None


class Page(HTMLParser):
    """The cleaned HTML as a tree; `by_id` maps backend_node_id to the element."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.nodes, self.by_id = [], {}
        self.stack = [Node("#root", [])]
        self.feed(html)
        self.close()

    def _open(self, tag, attrs):
        n = Node(tag, [(k, v if v is not None else "") for k, v in attrs])
        self.stack[-1].kids.append(n)
        self.nodes.append(n)
        for k, v in n.attrs:
            if k == "backend_node_id":
                self.by_id[v] = n
        return n

    def handle_starttag(self, tag, attrs):
        n = self._open(tag, attrs)
        if tag not in VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self._open(tag, attrs)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if data.strip():
            self.stack[-1].kids.append(" ".join(data.split()))

    def texts(self):
        for n in reversed(self.nodes):          # children come after their parent in document order
            n.text = " ".join(t for t in (k if isinstance(k, str) else k.text for k in n.kids) if t)

    def represent(self, backend_node_id):
        """Cleaned representation of one element: tag, kept attributes, visible text; None if the element is not in the page."""
        n = self.by_id.get(backend_node_id)
        if n is None:
            return None
        if n.tag == "text":
            s = n.text
        else:
            attrs = "".join(f' {k}="{" ".join(v.split())}"' for k, v in n.attrs if k != "backend_node_id")
            s = f"<{n.tag}{attrs}>{n.text}</{n.tag}>" if n.text else f"<{n.tag}{attrs}/>"
        return s[:CUT]


def build_row(row):
    """(options, gold_position, meta extras) for one data row, or the reason it cannot be used."""
    pos_all = [json.loads(p) for p in row["pos_candidates"]]
    if not pos_all:
        return "no positive candidate"
    page = Page(row["cleaned_html"])
    page.texts()
    pos = pos_all[0]
    pos_text = page.represent(pos["backend_node_id"])
    if pos_text is None:
        return "positive not found in the cleaned page"
    negs = [json.loads(n)["backend_node_id"] for n in row["neg_candidates"]]
    rng = random.Random(f"{SEED}:{row['action_uid']}")
    order = list(range(len(negs)))
    rng.shuffle(order)
    chosen, used = [], {pos_text}
    for i in order:
        t = page.represent(negs[i])
        if t is not None and t not in used:
            used.add(t)
            chosen.append((negs[i], t))
            if len(chosen) == N_NEG:
                break
    if len(chosen) < N_NEG:
        return "fewer than nine different negatives"
    options = [(pos["backend_node_id"], pos_text)] + chosen
    rng.shuffle(options)
    gold_pos = next(i for i, o in enumerate(options) if o[0] == pos["backend_node_id"] and o[1] == pos_text)
    return options, gold_pos, len(pos_all), pos["tag"]


def main():
    cache = os.path.abspath(sys.argv[1])
    cache = cache if os.path.basename(cache) == SOURCE else os.path.join(cache, SOURCE)
    paths = {name: fetch(cache, name) for name in sorted(FILES)}
    # pass 1: light columns of every row (index of the row inside its file: file, row group, offset)
    light = {s: [] for s in SPLITS}
    n_rows = collections.Counter()
    for name, path in paths.items():
        split = os.path.basename(name).split("-")[0]
        pf = pq.ParquetFile(path)
        for g in range(pf.num_row_groups):
            t = pf.read_row_group(g, columns=["action_uid", "pos_candidates"]).to_pylist()
            for k, r in enumerate(t):
                n_rows[split] += 1
                light[split].append({"uid": r["action_uid"], "has_pos": len(r["pos_candidates"]) > 0, "loc": (name, g, k)})
    no_pos = {s: sum(not r["has_pos"] for r in light[s]) for s in SPLITS}
    rng = random.Random(SEED)
    chosen_rows, dropped = [], collections.Counter()
    cache_rg = {}
    for split, quota in SPLITS.items():
        cand = sorted((r for r in light[split] if r["has_pos"]), key=lambda r: r["uid"])
        rng.shuffle(cand)
        taken, pos = [], 0
        while len(taken) < quota and pos < len(cand):
            batch = cand[pos:pos + quota - len(taken)]
            pos += len(batch)
            for r in sorted(batch, key=lambda r: r["loc"]):          # file order: one read per row group
                name, g, k = r["loc"]
                if (name, g) not in cache_rg:
                    cache_rg.clear()
                    cache_rg[(name, g)] = pq.ParquetFile(paths[name]).read_row_group(g, columns=COLS).to_pylist()
                row = cache_rg[(name, g)][k]
                res = build_row(row)
                if isinstance(res, str):
                    dropped[(split, res)] += 1
                else:
                    taken.append((r["uid"], split, row, res))
        taken.sort(key=lambda x: x[0])
        chosen_rows += taken
    items = []
    for uid, split, row, (options, gold_pos, n_pos, pos_tag) in chosen_rows:
        idx = int(row["target_action_index"])
        items.append({"id": f"{TASK}:{uid}",
                      "state": {"task": row["confirmed_task"], "previous_actions": row["action_reprs"][:idx]},
                      "questions": {"q": {"type": "choice", "instructions": INSTRUCTIONS,
                                          "criteria": {KEYS[i]: o[1] for i, o in enumerate(options)}}},
                      "gold": KEYS[gold_pos], "soft": None, "group": None,
                      "meta": {"source_id": uid, "split": split, "website": row["website"], "domain": row["domain"],
                               "subdomain": row["subdomain"], "annotation_id": row["annotation_id"], "target_action_index": idx,
                               "operation": json.loads(row["operation"])["op"], "gold_position": gold_pos,
                               "n_positive_candidates": n_pos, "positive_tag": pos_tag, "option_node_ids": [o[0] for o in options]}})
    rng.shuffle(items)
    per_split = collections.Counter(it["meta"]["split"] for it in items)
    gold = collections.Counter(it["gold"] for it in items)
    ops = collections.Counter(it["meta"]["operation"] for it in items)
    multi = sum(it["meta"]["n_positive_candidates"] > 1 for it in items)
    n_task = len({it["meta"]["annotation_id"] for it in items})
    sites = {s: len({it["meta"]["website"] for it in items if it["meta"]["split"] == s}) for s in SPLITS}
    doms = {s: sorted({it["meta"]["domain"] for it in items if it["meta"]["split"] == s}) for s in SPLITS}
    in_files = {s: n_rows[s] for s in SPLITS}
    chance = 1 / len(KEYS)
    interactive = {"a", "button", "input", "select", "textarea", "label"}
    tag_of = lambda text: text[1:].split(">")[0].split("/")[0].split(" ")[0] if text.startswith("<") else "text"
    pos_inter = neg_inter = n_neg = only = 0
    for it in items:
        tags = {k: tag_of(v) for k, v in it["questions"]["q"]["criteria"].items()}
        pos_inter += tags[it["gold"]] in interactive
        neg_inter += sum(t in interactive for k, t in tags.items() if k != it["gold"])
        n_neg += len(tags) - 1
        only += [k for k, t in tags.items() if t in interactive] == [it["gold"]]
    drop_txt = "; ".join(f"{n} in {s} ({why})" for (s, why), n in sorted(dropped.items())) or "none"
    tj = {"task": TASK, "layer": "D", "title": "Mind2Web: which page element should the agent act on next?",
          "decision": "which of ten page elements (the target element of the step and nine other elements of the page) the agent should "
                      "act on next, given the task and the actions already taken",
          "source": {"name": "Multimodal-Mind2Web (text columns of the test splits; Mind2Web: Towards a Generalist Agent for the Web, arXiv:2306.06070; "
                             "Multimodal-Mind2Web: GPT-4V(ision) is a Generalist Web Agent, if Grounded, arXiv:2401.01614)",
                     "url": "https://huggingface.co/datasets/osunlp/Multimodal-Mind2Web", "files": sorted(FILES),
                     "split": "test_task, test_website, test_domain: " + ", ".join(
                         f"{s} {in_files[s]} of {SPLIT_SIZE[s][0]:,} rows ({sum(1 for n in FILES if os.path.basename(n).startswith(s))} of {SPLIT_SIZE[s][1]} shards)" for s in SPLITS),
                     "version": f"commit {COMMIT} (last modified 2024-06-05), downloaded 2026-10-07"},
          "licence": "openrail (license tag of the Multimodal-Mind2Web card; the Mind2Web card says cc-by-4.0)",
          "redistribution": "rebuild script only", "labels": "human", "item_source": "public test set", "metric": "accuracy",
          "chance": chance, "rows": len(items), "groups": None, "question_type": "choice", "options": len(KEYS),
          "notes": f"{len(items)} steps ({', '.join(f'{s} {per_split[s]}' for s in SPLITS)}) of {n_task} tasks; operations of the target: "
                   + ", ".join(f"{k} {v}" for k, v in sorted(ops.items())) + ". Gold = the positive candidate of the step (the first of "
                   f"`pos_candidates`; {multi} rows have more than one positive candidate, the others are then not among the options). "
                   f"AVAILABILITY: the card's parquet shards hold screenshots; only shards of at most 300 MB were downloaded, so each split "
                   f"is a subset: test_task {in_files['test_task']} of 1,339 rows (4 of 5 shards), test_website {in_files['test_website']} of 1,019 "
                   f"(3 of 4), test_domain {in_files['test_domain']} of 4,060 (1 of 11); the shards are not a random sample of a split, and the sample "
                   f"covers {sites['test_task']}, {sites['test_website']} and {sites['test_domain']} websites (test_task, test_website, test_domain); the test_domain rows come "
                   f"from the domains {', '.join(doms['test_domain'])} only. Rows without a positive candidate: " + ", ".join(f"{s} {no_pos[s]}" for s in SPLITS)
                   + f" (not used); other rows rejected while drawing: {drop_txt}. Equal shares of the three splits ({', '.join(str(v) for v in SPLITS.values())}), "
                   f"drawn per split in a random order of the action ids with random.Random({SEED}); several steps of one task can be in "
                   f"the sample (meta.annotation_id). OPTIONS: ten per row, keys A..J: the positive and nine negatives drawn from the row's "
                   f"`neg_candidates` (random elements of the row's candidate list, which has a median of 408 negatives, not chosen for similarity to "
                   f"the target and not checked for being equivalent to it, e.g. a container of the target; the target's tag is a link, button, "
                   f"input, select, textarea or label in {pos_inter / len(items):.0%} of the rows against {neg_inter / n_neg:.0%} of the negatives, "
                   f"and the target is the only such option in {only / len(items):.0%} of the rows), skipping negatives "
                   f"whose option text equals the positive's or one already drawn; the order is drawn per row with a generator seeded with "
f"{SEED} and the action id (meta.gold_position, meta.option_node_ids); gold key counts " + ", ".join(f"{k} {gold[k]}" for k in KEYS)
                   + f". Option text = cleaned representation of the element taken from the row's cleaned HTML: the opening tag with the "
                   f"attributes kept in the cleaned page (no backend_node_id), the visible text of the element and its descendants, the "
                   f"closing tag (an element without text is written as an empty tag), cut at {CUT} characters; the candidate records "
                   f"themselves hold only tag and attributes (class, id, bounding box ...), no text. The Mind2Web authors' own representation "
                   f"is a pruned page for the whole row; this one is per element. state.task = confirmed task, state.previous_actions = the "
                   f"strings of `action_reprs` before the target index, as given (the target's own string is not in the state). The page "
                   f"itself is not part of the state. Labels are the elements chosen by the crowd workers who recorded the tasks."}
    d = f"{HERE}/tasks/{TASK}"
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/items.jsonl", "w", encoding="utf-8") as f:
        for it in items:
            f.write(dumps(it) + "\n")
    with open(f"{d}/task.json", "w", encoding="utf-8") as f:
        json.dump(tj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    with open(f"{d}/README.md", "w", encoding="utf-8") as f:
        f.write(f"# {TASK}\n\n{tj['title']}\n\n- Decision: {tj['decision']}.\n- Source: {tj['source']['name']}; "
                f"{tj['source']['url']}, {tj['source']['version']}.\n"
                + "".join(f"- File `{n}`: SHA-256 `{FILES[n]}`\n" for n in sorted(FILES))
                + f"- Licence: openrail (card tag); {tj['redistribution']}.\n- Rows: {len(items)} ({', '.join(f'{s} {per_split[s]}' for s in SPLITS)}); "
                f"ten options per row; metric: accuracy (chance {chance}).\n- Rebuild: `python3 reference/build/build_{TASK}.py CACHE_DIR` (needs pyarrow; "
                "reads the text columns of about 2 GB of parquet shards).\n\nOnly shards of at most 300 MB were used, so each split is a subset; "
                "see `task.json`.\n")
    print(TASK, len(items), "rows", dict(per_split), "; gold", dict(gold), "; dropped", drop_txt, "; no positive", no_pos,
          "; multi-positive rows", multi, "; tasks", n_task)


if __name__ == "__main__":
    main()
