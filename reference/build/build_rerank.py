"""Tasks rerank_scifact / rerank_nfcorpus (layer G, public test set): rerank the 50 candidates of a query.
Source: the public reranking test github.com/dchristopoulos/system1-rerank-bench (MIT): 100 test queries each of BEIR
SciFact and NFCorpus with the 50 hybrid-search candidates that every system of that test reranked.  The item file
rr_items.json is built from the repository's data files by reference/build/rr_build.py (queries, candidates in
retrieval order, corpus texts, relevance judgments).
    python3 reference/build/build_rerank.py RR_ITEMS.json
One row per (query, candidate) in the candidates' order; the question is the four-level rubric registered in that test
for decision models.  Metric: nDCG@10 per query with linear graded gain; the ideal ranking is taken over ALL judged
documents of the query (meta.ideal_gains), also those that are not among the 50 candidates, and ties are broken by
document id - the definition of the source test, so values are comparable with its published table."""
import collections
import json
import os
import sys

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "generated", "reference")   # writes HERE/tasks/<task>/
INS = "How well does the passage supply the information needed to answer or verify the query?"
LEVELS = ["The passage is off-topic for the query.",
          "The passage is on a related topic but does not supply what the query asks for.",
          "The passage partly supplies the information needed to answer or verify the query.",
          "The passage fully supplies the information needed to answer or verify the query."]
LIC = {"scifact": "candidate lists: MIT (system1-rerank-bench); SciFact texts and judgments: CC BY-NC 2.0 (as listed by BEIR)",
       "nfcorpus": "candidate lists: MIT (system1-rerank-bench); NFCorpus texts and judgments: licence not confirmed on a primary page"}
items = json.load(open(sys.argv[1]))
for ds in ("scifact", "nfcorpus"):
    it = items[ds]
    task = f"rerank_{ds}"
    top = max(g for q in it["qrels"].values() for g in q.values())
    rows, n_rel, n_rel_all = [], 0, 0
    grades = collections.Counter()
    for q in sorted(it["queries"]):
        judged = it["qrels"][q]
        ideal = sorted((g for g in judged.values() if g > 0), reverse=True)[:10]
        n_rel_all += sum(1 for g in judged.values() if g > 0)
        for rank, d in enumerate(it["candidates"][q], 1):
            g = int(judged.get(d, 0))
            n_rel += g > 0
            grades[g] += 1
            rows.append({"id": f"{task}:{q}:{d}", "state": {"query": it["queries"][q], "passage": it["corpus"][d]},
                         "questions": {"q": {"type": "score", "instructions": INS, "criteria": LEVELS}},
                         "gold": 3 if g == top else (2 if g > 0 else 0), "soft": None, "group": f"{task}:{q}",
                         "meta": {"source_id": f"{q}:{d}", "query_id": q, "doc_id": d, "relevance": g, "ideal_gains": ideal,
                                  "rank_in_candidates": rank}})
    d = f"{HERE}/tasks/{task}"
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/items.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    json.dump({"task": task, "layer": "G", "title": f"Reranking, {'SciFact' if ds == 'scifact' else 'NFCorpus'} (50 candidates per query)",
               "decision": "how well a retrieved passage supplies what a query asks for; the candidates of a query are ranked by the answer",
               "source": {"name": "system1-rerank-bench (BEIR SciFact and NFCorpus test queries with hybrid-search candidates)",
                          "url": "https://github.com/dchristopoulos/system1-rerank-bench", "files": ["rr_items.json (built by paper/scripts/search/rr_build.py)"],
                          "split": "100 test queries, 50 candidates each", "version": "repository as downloaded 2026-10-06"},
               "licence": LIC[ds], "redistribution": "rebuild script only", "labels": "human",
               "item_source": "public test set", "metric": "ndcg@10", "chance": None, "rows": len(rows), "groups": len(it["queries"]),
               "question_type": "score", "options": 4,
               "notes": f"All {len(it['queries'])} queries with all their candidates (the row cap does not apply to ranking tasks). Graded judgments of the "
                        f"candidates: {dict(sorted(grades.items()))}; {n_rel} of the {n_rel_all} judged-relevant documents are among the candidates, "
                        f"so a perfect reranker stays below 1. `gold` is only the placeholder the format requires (3 = highest grade of the set, "
                        f"2 = a lower positive grade, 0 = not judged relevant); the metric uses meta.relevance and meta.ideal_gains. The rubric "
                        f"wording is the one registered in the source test for decision models, one passage per request."},
              open(f"{d}/task.json", "w"), indent=1)
    open(f"{d}/README.md", "w").write(f"# {task}\n\nReranking of 50 hybrid-search candidates per query; see `task.json`. Built by "
                                      f"`build/build_rerank.py` from the item file of the public reranking test.\n")
    print(task, len(rows), "rows", len(it["queries"]), "queries", dict(grades))
