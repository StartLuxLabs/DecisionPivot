"""Task answerable_facts (layer A, generated, programmatic truth): "can the question be answered from the facts listed?"

Two versions.  The constant DIFFICULTY at the top of the file chooses the version: "v2" (the default, and what tasks/answerable_facts holds) or
"v1" (the first version); the environment variable BENCH_DIFFICULTY overrides it (``BENCH_DIFFICULTY=v1 python3 generators/answerable_facts.py``).
Either run rewrites the task directory (items.jsonl, task.json, README.md) and is deterministic.  v1 was answered at 0.98 by a strong hosted model,
so v2 raises the dials (hops 2 / 3 / 4 on 20 / 40 / 80 rows), writes the rules of reading into the state, and adds look-alike rows and derived facts
that exist only under a written rule.  The v1 code path is the first version, unchanged (main_v1, write_readme_v1); v2 is the block of functions ending in _v2.

gen_v4 (2026-10-08) fixes three defects that two reviewers found in the first release of v2 (the v1 path keeps its clamp, it regenerates the first version):
  (1) Founding years were clamped: a subsidiary was founded "min(2022, parent + 0..25)", so 25 % of all listed founding years were exactly 2022 and 2022
      was the maximum wherever it occurred.  The years are now drawn family by family: every subsidiary is founded 2 to 20 years after its parent (the
      order parent -> child holds by construction), the head year is drawn uniformly from the window in which the youngest member of the family still fits
      below 2024; years lie in 1880-2024 and nothing is clamped (no value piles up at a bound).  Head count and number of sites were never clamped.
  (2) The nine cells of hops x rows are replaced by a level ladder: ``meta.level`` 1 / 2 / 3 with 200 items each; level 1 = hops 2 on 20 rows, level 2 =
      hops 3 on 40 rows, level 3 = hops 4 on 80 rows (``meta.hops`` and ``meta.rows`` stay); with the level also the number of organisations (8 / 14 / 26),
      of families (2 / 3 / 4) and of near-miss rows per needed row (1 / 2 / 3) rise.  Per level: 100 pairs, 100 yes + 100 no, 50 + 50 negatives of the two
      deviation kinds (also inside every form), exactly half of the positives and of the negatives list ``yes`` first.
  (3) The region-inheritance rule (rule 4) is in every state but only one question in four needed it.  Now 40 of the 100 pairs of every level are region
      questions (inherit, inherit_rel, inherit_chain2: 40 pairs each, the other forms 20 pairs each), and in half of their negatives the missing row is the
      parent's region row (the case the rule is about: "provided the parent has a region row of its own").

VERSION v2 (default)

Item design.  The state is a facts table about invented organisations (rows "entity - attribute - value"; attributes: founding year, headquarters,
parent organisation, head count, product line, number of sites, chief executive, operating region) in one of four layouts with one of four label sets,
preceded by FOUR LINES OF RULES OF READING (one wording of four for each, in a drawn order): (1) only the rows may be used, a fact without a row is
unknown; (2) organisations are related only where a parent row says so, a shared family name proves nothing; (3) a comparison or a total needs the figure
of every organisation it covers and no figure is worked out from other figures; (4) one fact is inherited: an organisation with no region row takes the
region of its parent, if the parent has a region row of its own (one step, nothing else is inherited).  The organisations form 2 to 4 families (one family
name, many suffixes, most names look alike) with parent links up to three levels deep.  The question follows.
Question forms (``meta.form``; ``meta.hops`` = the number of rows the question needs; 12 forms, 20 pairs per form and 40 for the region form of each level):
  hops 2  rel_lookup (a figure of the parent)   compare (two figures, often of two look-alikes)   inherit (the region of an organisation without a region row)
          rev_lookup (a figure of the ONE subsidiary the table lists for an organisation, found through the value column)
  hops 3  chain2 (a figure two links up)   compare_rel / compare_parent (a comparison with a figure reached through a link)
          inherit_rel (the region of the parent, which has no region row and takes the one of its own parent)
  hops 4  chain3 (a figure three links up)   compare_chain2 (a comparison through two links)
          agg_subs (the combined head count or number of sites of the two subsidiaries whose own parent row names the asked organisation)
          inherit_chain2 (the region two links up, taken over from its parent)
The gold answer is yes when every row the question needs is in the table (the inherited region counts as derivable only through its two rows and rule 4),
and no when one is not.

Near misses.  For every needed row the table holds the same attribute of 1 / 2 / 3 look-alike siblings (same family name, at 20 / 40 / 80 rows) and one
more look-alike row is kept back for the decoy; the asked organisation has at least one more row, and where it exists a child row that names it as parent
(a link that points the other way).  In the three ``inherit`` forms the organisation whose region is asked never has a region row of its own, in either
member of a pair; in ``agg_subs`` and ``rev_lookup`` exactly the chosen subsidiaries have a parent row naming the asked organisation (``agg_subs`` never
removes a link row).

Contrast pairs.  600 items = 300 pairs (300 yes, 300 no).  The negative replaces ONE row the question needs (``meta.missing_role`` says which: a link, a
figure, one side of a comparison, one of the totalled figures) by
  other_entity     the same attribute of a look-alike organisation (97 of 150 from the same family), or
  other_attribute  another attribute of the same organisation.
Count matching: one neutral filler row is changed as well, so that the asked organisation (other_entity) or the asked attribute (other_attribute) has the
same number of rows in both members (asserted); the table keeps its size and still mentions every organisation of the question.
Level ladder (``meta.level``, 200 items each): level 1 = hops 2 on 20 rows (8 organisations), level 2 = hops 3 on 40 rows (14), level 3 = hops 4 on 80 rows (26).
Truth twice.  ``truth_v2(spec)`` follows the structured question over the structured table with the rules of reading; ``check_v2(item)`` re-derives the
answer from the rendered text only (it parses the four rules, the rows in any layout and label set, and the question in any phrasing) and the script
asserts that both agree on all 600 items, that every deviation flips the answer with exactly one needed row missing, that no forbidden row (a region row
of the inheriting organisation, the parent row of a third subsidiary) is in either table, and that classes, deviation kinds, option positions and levels are
exactly balanced (also within every level).

VERSION v1 (DIFFICULTY = "v1")

Item design.  Every item is a facts table about invented organisations ("entity · attribute · value", attributes:
founding year, headquarters, parent organisation, head count, product line, number of sites, chief executive) and one
question that needs one, two or three of those facts.  Question forms (``hops`` = number of facts the question needs):
  hops 1  lookup           "What is the head count of X?"
  hops 2  rel_lookup       "What is the head count of the parent company of X?"       (the link and the value)
          compare          "Which has the greater head count: X or Y?"                (two looked-up numbers)
  hops 3  compare_rel      "Is the head count of X greater than that of the parent company of Y?"
          compare_parent   "Does X have a greater head count than its parent company?"
          chain2           "What is the head count of the parent company of the parent company of X?"
The gold answer is yes when every needed fact is a row of the table and no when one is not.  Nothing outside the table
may be used; the table says so in its first lines.

Contrast pairs.  The benchmark holds 300 pairs (600 items, 300 yes and 300 no).  A pair is one table + question (yes)
and the same table with ONE planted deviation (no): one row the question needs is replaced, at the same place, by
  other_entity     the same attribute of another organisation (often one with the same family name), or
  other_attribute  another attribute of the same organisation.
The table keeps its size, every organisation named in the question still occurs in it, and exactly one needed fact is
missing (asserted for every negative).  Because both members of a pair share almost every row, the length, the
vocabulary and the structure of the two classes are the same by construction.
Count matching.  A replaced row changes how many rows mention the asked organisation (other_entity) or carry the asked
attribute (other_attribute), and a reader could use that count as a cue.  So one neutral filler row (not part of the
question) is changed as well, in the negative only, to give the asked organisation and the asked attribute the same
number of rows as in the positive (asserted for every pair); the pair then differs in two rows, one of them neutral.

Dials (each level has 200 items = 100 pairs; the 3 x 3 cells hold 33 or 34 pairs each):
  hops  1, 2, 3     number of facts the question needs
  rows  10, 20, 40  number of rows of the table (organisations: 5, 8, 14)

Truth twice.  ``truth(spec)`` follows the structured question over the structured table.  ``check(item)`` re-derives
the answer from the rendered text only (it parses the rows of the table in any of four layouts and the question in
any of its phrasings) and the script asserts that both agree on all 600 items.

Run:
    python3 generators/answerable_facts.py
"""
import collections
import json
import os
import random
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repository root (this file is generators/<family>.py)
HERE = os.path.join(REPO, "generated")                               # the items are written to HERE/tasks/<family>/
AUDITS = os.path.join(REPO, "audits")                                # validate.py and audit.py, run on HERE/tasks/<family>/
SEED = 20261007
TASK = "answerable_facts"
PAIRS = 300
DIFFICULTY = "v2"        # "v2": the harder dials (default, what the task directory holds) | "v1": the first version (easier dials)
DIFFICULTY = os.environ.get("BENCH_DIFFICULTY", DIFFICULTY)             # e.g. BENCH_DIFFICULTY=v1 python3 generators/answerable_facts.py
assert DIFFICULTY in ("v1", "v2"), DIFFICULTY


def rng_for(*parts):
    return random.Random(":".join(str(p) for p in (SEED, TASK) + parts))


# ---------------------------------------------------------------------------------------------------- invented names
START = ["Kel", "Vor", "Tal", "Mar", "Dra", "Sen", "Ori", "Quil", "Bar", "Hal", "Jor", "Lum", "Nor", "Pel", "Ryn", "Sol",
         "Tev", "Zan", "Fen", "Gar", "Kor", "Mel", "Nim", "Pav", "Rav", "Sav", "Tor", "Vel", "Wen", "Yar", "Zol", "Bel",
         "Cor", "Dov", "Eld", "Fal", "Gal", "Hes", "Jav", "Kas", "Lor", "Mir", "Nev", "Per", "Ros", "Sul", "Tam", "Ves",
         "Zer", "Ald", "Bran", "Cris", "Dern", "Fran", "Grel", "Hald", "Krin", "Prav", "Stel", "Trel", "Vrin"]
END = ["vane", "mora", "trin", "dex", "wick", "lor", "tis", "ven", "sal", "dar", "kos", "nex", "phel", "quin", "rov", "tan",
       "vik", "zen", "bel", "dor", "fen", "gan", "kar", "lis", "mun", "nor", "pen", "rik", "sel", "tor", "van", "xan",
       "yor", "zim", "dra", "lia", "ria"]
BLOCK = {"barbel", "bellis", "beltis", "corbel", "crissal", "garbel", "marmar", "norsel", "norsk", "origan", "pernor",
         "sensal", "sultan", "tallis", "torsel", "torsk", "trellis", "vessel", "belbel", "korkar", "talvan", "salsal", "trellor"}
GIVEN1 = ["Ta", "Me", "Ka", "Li", "Ro", "Ne", "Sa", "Vi", "Jo", "El", "An", "Or", "Ul", "Ya", "Za", "Be", "Da", "Fi", "Ha",
          "Ke", "Lo", "Mi", "Na", "Pa", "Re", "Si", "To", "Wa"]
GIVEN2 = ["vi", "ro", "sen", "ra", "lan", "ko", "mi", "dan", "ta", "nor", "lis", "vo", "ren", "sha", "dor", "mia", "ven",
          "lo", "kai"]


def coin(rng):
    """an invented one-word name, e.g. Veldra, Kasrik, Stelmora"""
    while True:
        w = (rng.choice(START).lower() + rng.choice(END)).capitalize()
        if w.lower() not in BLOCK:
            return w


BLOCK_GIVEN = {"anta", "belis", "beta", "damia", "daren", "data", "daven", "filo", "hako", "halo", "hami", "haven", "jota", "kalo", "karen",
               "karo", "kasha", "kavi", "keta", "lira", "liven", "lolo", "lora", "loren", "loro", "lota", "mero", "meta", "milan", "milo", "mimi",
               "minor", "mira", "miro", "nako", "naren", "nevo", "orlo", "para", "paren", "pasha", "pata", "pavo", "redan", "remi", "rota", "sakai",
               "sara", "silo", "simia", "siren", "sita", "talis", "tara", "taro", "toko", "tolan", "tora", "toro", "vira", "vita", "zamia"}


def person(rng):
    """an invented person name: a given name from syllables (never an existing first name or word) and an invented family name"""
    while True:
        g = rng.choice(GIVEN1) + rng.choice(GIVEN2)
        if g.lower() not in BLOCK_GIVEN:
            return g + " " + coin(rng)


SUFFIX_HEAD = ["Holdings", "Group"]
SUFFIX_MEMBER = ["Foods", "Marine", "Labs", "Works", "Systems", "Trading", "Logistics", "Energy", "Textiles", "Optics",
                 "Freight", "Robotics", "Media", "Pharma", "Materials", "Motors", "Paper", "Tools"]
PRODUCT_NOUN = ["pumps", "valves", "sensors", "bearings", "filters", "lamps", "cables", "engines", "boilers", "drills",
                "gearboxes", "pipes", "switches", "fasteners", "hinges", "batteries", "compressors", "fans"]

# ------------------------------------------------------------------------------------------------------- attributes
ATTRS = ["founded", "hq", "parent", "staff", "product", "sites", "ceo"]
NUMERIC = ["founded", "staff", "sites"]
LABELS = {
    "founded": ["founding year", "year founded", "year of founding", "foundation year"],
    "hq": ["headquarters", "head office", "registered office", "main office"],
    "parent": ["parent organisation", "parent company", "parent group", "parent body"],
    "staff": ["head count", "staff count", "number of employees", "workforce size"],
    "product": ["product line", "main product", "core product", "flagship product"],
    "sites": ["number of sites", "site count", "number of locations", "location count"],
    "ceo": ["chief executive", "CEO", "managing director", "top executive"],
}
PREAMBLE = [
    "Facts on record. Use only the rows below. A fact that has no row is unknown, and organisations are related only where a row says so, whatever their names suggest.",
    "Register extract. These rows are everything that is known. Do not fill in a missing row from outside knowledge or from similar names: a family name does not make two organisations related.",
    "Facts retrieved for this request. Answer from the rows below and nothing else; a fact without a row is not available, and a shared name is no evidence of a link between organisations.",
    "Reference facts. Each row states one fact about one organisation. Facts without a row are not known, and relations (such as a parent organisation) exist only where a row states them.",
]
FORMS = ["lookup", "rel_lookup", "compare", "compare_rel", "compare_parent", "chain2"]
HOPS_OF = {"lookup": 1, "rel_lookup": 2, "compare": 2, "compare_rel": 3, "compare_parent": 3, "chain2": 3}
INSTRUCTIONS = "Can the question be answered from the facts listed?"
OPTIONS = {"yes": "Every fact the question needs is listed.", "no": "At least one fact the question needs is not listed."}


# --------------------------------------------------------------------------------------------------------- the world
def make_world(rng, n_ent):
    """-> {entity: {attr: value}}; value None = the entity has no such fact (a family head has no parent)"""
    n_fam = 2 if n_ent <= 8 else 3
    sizes = [n_ent // n_fam + (1 if k < n_ent % n_fam else 0) for k in range(n_fam)]
    cities = [coin(rng) for _ in range(rng.randint(5, 8))]
    brands = [coin(rng) for _ in range(rng.randint(4, 7))]
    world, stems, depth = collections.OrderedDict(), set(), {}
    for size in sizes:
        while True:
            stem = coin(rng)
            if stem not in stems:
                stems.add(stem)
                break
        suf = rng.sample(SUFFIX_MEMBER, size - 1)
        names = [f"{stem} {rng.choice(SUFFIX_HEAD)}"] + [f"{stem} {s}" for s in suf]
        for k, name in enumerate(names):
            if k == 0:
                parent, depth[name] = None, 0
            elif k == 1:
                parent = names[0]
            elif k == 2:
                parent = names[1]                                   # a chain of two links: member -> member -> head
            else:
                parent = rng.choice([n for n in names[:k] if depth[n] <= 1])
            if k:
                depth[name] = depth[parent] + 1
            world[name] = {"parent": parent}
    used_staff, used_sites, used_year = set(), set(), set()
    for name, d in world.items():
        yr = rng.randint(1951, 2021)
        if d["parent"]:
            yr = min(2022, world[d["parent"]]["founded"] + rng.randint(0, 25))
        d["founded"] = yr
        while True:
            st = int(round(10 ** rng.uniform(1.2, 3.9)))
            if st not in used_staff:
                used_staff.add(st)
                break
        d["staff"] = st
        d["sites"] = rng.randint(1, 40)
        d["hq"] = rng.choice(cities)
        d["product"] = f"{rng.choice(brands)} {rng.choice(PRODUCT_NOUN)}"
        d["ceo"] = person(rng)
    return world


def exists(world, e, a):
    return world[e].get(a) is not None


# ------------------------------------------------------------------------------------------------------- questions
def needs_of(world, q):
    """the facts a question needs: [(entity, attribute, role)] in reading order"""
    f = q["form"]
    if f == "lookup":
        return [(q["e"], q["a"], "value")]
    if f == "rel_lookup":
        return [(q["e"], "parent", "link"), (world[q["e"]]["parent"], q["a"], "value")]
    if f == "compare":
        return [(q["x"], q["a"], "left"), (q["y"], q["a"], "right")]
    if f == "compare_rel":
        return [(q["x"], q["a"], "left"), (q["y"], "parent", "link"), (world[q["y"]]["parent"], q["a"], "value")]
    if f == "compare_parent":
        return [(q["x"], q["a"], "left"), (q["x"], "parent", "link"), (world[q["x"]]["parent"], q["a"], "value")]
    if f == "chain2":
        p = world[q["e"]]["parent"]
        return [(q["e"], "parent", "link1"), (p, "parent", "link2"), (world[p]["parent"], q["a"], "value")]
    raise ValueError(f)


def named_entities(q):
    return [q[k] for k in ("e", "x", "y") if k in q]


def make_question(rng, world, form):
    ents = list(world)
    with_parent = [e for e in ents if world[e]["parent"]]
    for _ in range(200):
        op = rng.choice(["greater", "smaller"])
        if form == "lookup":
            e = rng.choice(ents)
            a = rng.choice([a for a in ATTRS if exists(world, e, a)])
            return {"form": form, "e": e, "a": a}
        if form == "rel_lookup":
            return {"form": form, "e": rng.choice(with_parent), "a": rng.choice([a for a in ATTRS if a != "parent"])}
        if form == "chain2":
            deep = [e for e in with_parent if world[world[e]["parent"]]["parent"]]
            return {"form": form, "e": rng.choice(deep), "a": rng.choice([a for a in ATTRS if a != "parent"])}
        a = rng.choice(NUMERIC)
        if form == "compare":
            x, y = rng.sample(ents, 2)
            if world[x][a] != world[y][a]:
                return {"form": form, "x": x, "y": y, "a": a, "op": op}
        elif form == "compare_rel":
            x, y = rng.choice(ents), rng.choice(with_parent)
            if x != y and x != world[y]["parent"] and world[x][a] != world[world[y]["parent"]][a]:
                return {"form": form, "x": x, "y": y, "a": a, "op": op}
        elif form == "compare_parent":
            x = rng.choice(with_parent)
            if world[x][a] != world[world[x]["parent"]][a]:
                return {"form": form, "x": x, "a": a, "op": op}
    raise RuntimeError("no question")


# ------------------------------------------------------------------------------------------------------- the table
def build_rows(rng, world, q, n_rows):
    """the base table: the needed facts, one more row for every organisation the question names, then random rows"""
    needs = needs_of(world, q)
    chosen = [(e, a) for e, a, _ in needs]
    assert len(set(chosen)) == len(chosen)
    for e in sorted(set(named_entities(q))):
        free = [a for a in ATTRS if exists(world, e, a) and (e, a) not in chosen]
        chosen.append((e, rng.choice(free)))
    pool = [(e, a) for e in world for a in ATTRS if exists(world, e, a) and (e, a) not in chosen]
    rng.shuffle(pool)
    chosen += pool[:n_rows - len(chosen)]
    assert len(chosen) == n_rows, (len(chosen), n_rows)
    if rng.random() < 0.5:                                          # grouped by organisation
        order = list(world)
        rng.shuffle(order)
        chosen.sort(key=lambda k: (order.index(k[0]), ATTRS.index(k[1])))
        layout = "grouped"
    else:
        order = None
        rng.shuffle(chosen)
        layout = "shuffled"
    return [(e, a, str(world[e][a])) for e, a in chosen], layout, order


def decoy_row(rng, world, rows, removed, kind):
    """a row that takes the place of the removed row: -> (entity, attribute, value) or None"""
    keys = {(e, a) for e, a, _ in rows}
    e, a, _ = removed
    if kind == "other_entity":
        stem = e.split()[0]
        cands = [(e2, a) for e2 in world if e2 != e and exists(world, e2, a) and (e2, a) not in keys]
        mates = [c for c in cands if c[0].split()[0] == stem]
        if mates and rng.random() < 0.6:
            cands = mates
    else:
        cands = [(e, a2) for a2 in ATTRS if a2 != a and exists(world, e, a2) and (e, a2) not in keys]
    if not cands:
        return None
    e2, a2 = rng.choice(cands)
    return (e2, a2, str(world[e2][a2]))


def compensate(rng, world, rows, dec, removed, kind, protected):
    """one neutral filler row is changed as well, so that the organisation (other_entity) or the attribute (other_attribute)
    of the removed fact keeps in the negative the number of rows it has in the positive: the number of rows that mention
    the asked organisation or the asked attribute then says nothing about the answer.  -> (rows, old row, new row) or None"""
    keys = {(r[0], r[1]) for r in rows}
    e0, a0, _ = removed
    cands = []
    for k, r in enumerate(rows):
        if r == dec or r[0] in protected or r[1] == a0:
            continue
        if kind == "other_entity":                                   # (F, B) -> (e0, B)
            if exists(world, e0, r[1]) and (e0, r[1]) not in keys:
                cands.append((k, (e0, r[1], str(world[e0][r[1]]))))
        elif exists(world, r[0], a0) and (r[0], a0) not in keys:     # (F, C) -> (F, a0)
            cands.append((k, (r[0], a0, str(world[r[0]][a0]))))
    if not cands:
        return None
    k, new = rng.choice(cands)
    return rows[:k] + [new] + rows[k + 1:], rows[k], new


# ----------------------------------------------------------------------------------------------------- rendering
def render_table(rows, labels, style, pre):
    lines = [PREAMBLE[pre]]
    if style == 0:
        lines += ["Entity · Attribute · Value"] + [f"{e} · {labels[a]} · {v}" for e, a, v in rows]
    elif style == 1:
        lines += ["| Entity | Attribute | Value |", "|---|---|---|"] + [f"| {e} | {labels[a]} | {v} |" for e, a, v in rows]
    elif style == 2:
        lines += [f"- {e} — {labels[a]}: {v}" for e, a, v in rows]
    else:
        lines += [f"{n}. {e} | {labels[a]} | {v}" for n, (e, a, v) in enumerate(rows, 1)]
    return "\n".join(lines)


def render_question(q, labels, frame):
    a, R = labels.get(q.get("a")), labels["parent"]
    f, op = q["form"], q.get("op")
    if f == "lookup":
        e = q["e"]
        return ["What is the {a} of {e}?", "State the {a} of {e}.", "Give the {a} recorded for {e}.",
                "Looking at {e}: what is its {a}?"][frame].format(a=a, e=e)
    if f == "rel_lookup":
        e = q["e"]
        return ["What is the {a} of the {R} of {e}?", "Find the {R} of {e}, then state its {a}.",
                "Look up the {R} of {e} and report its {a}.", "For the {R} of {e}, what is the {a}?"][frame].format(a=a, R=R, e=e)
    if f == "chain2":
        e = q["e"]
        return ["What is the {a} of the {R} of the {R} of {e}?",
                "Starting at {e}, go to its {R}, then to that organisation's {R}, and state the {a} of the one you reach.",
                "Give the {a} of the {R} of the {R} of {e}.", "For the {R} of the {R} of {e}, what is the {a}?"
                ][frame].format(a=a, R=R, e=e)
    x, y = q["x"], q.get("y")
    if f == "compare":
        return ["Is the {a} of {x} {op} than the {a} of {y}?", "Does {x} have a {op} {a} than {y}?",
                "Which has the {op} {a}: {x} or {y}?", "Compare {x} and {y}: which one has the {op} {a}?"
                ][frame].format(a=a, x=x, y=y, op=op)
    if f == "compare_rel":
        return ["Is the {a} of {x} {op} than the {a} of the {R} of {y}?", "Does {x} have a {op} {a} than the {R} of {y}?",
                "Which is {op}: the {a} of {x} or the {a} of the {R} of {y}?",
                "Compare the {a} of {x} with the {a} of the {R} of {y}: which is {op}?"][frame].format(a=a, R=R, x=x, y=y, op=op)
    return ["Is the {a} of {x} {op} than the {a} of its {R}?", "Does {x} have a {op} {a} than its {R}?",
            "Which is {op}: the {a} of {x} or the {a} of its {R}?",
            "Compare {x} with its {R}: which has the {op} {a}?"][frame].format(a=a, R=R, x=x, op=op)


# -------------------------------------------------------------------------------------- truth on the specification
def truth(spec):
    """True when every fact the question needs is a row of the table (and the chain of links can be followed)"""
    tbl = {(e, a): v for e, a, v in spec["rows"]}
    q, g = spec["q"], tbl.get
    f = q["form"]
    if f == "lookup":
        return (q["e"], q["a"]) in tbl
    if f == "rel_lookup":
        p = g((q["e"], "parent"))
        return p is not None and (p, q["a"]) in tbl
    if f == "compare":
        return (q["x"], q["a"]) in tbl and (q["y"], q["a"]) in tbl
    if f == "compare_rel":
        p = g((q["y"], "parent"))
        return (q["x"], q["a"]) in tbl and p is not None and (p, q["a"]) in tbl
    if f == "compare_parent":
        p = g((q["x"], "parent"))
        return (q["x"], q["a"]) in tbl and p is not None and (p, q["a"]) in tbl
    p = g((q["e"], "parent"))
    p2 = g((p, "parent")) if p is not None else None
    return p2 is not None and (p2, q["a"]) in tbl


# ---------------------------------------------------------- check: the answer from the rendered text alone
ALL_LABELS = sorted({x for v in LABELS.values() for x in v}, key=lambda x: (-len(x), x))
PARENT_LABELS = set(LABELS["parent"])
LAB = "(?:" + "|".join(re.escape(x) for x in ALL_LABELS) + ")"
PAR = "(?:" + "|".join(re.escape(x) for x in sorted(PARENT_LABELS, key=lambda x: (-len(x), x))) + ")"
ENT = r"[A-Z][a-z]+ [A-Z][a-z]+"
OP = r"(?:greater|smaller)"
ROW_PATTERNS = [r"(.+?) · (.+?) · (.+)", r"\| (.+?) \| (.+?) \| (.+?) \|", r"- (.+?) — (.+?): (.+)", r"\d+\. (.+?) \| (.+?) \| (.+)"]
Q_PATTERNS = [
    ("lookup", rf"What is the (?P<a>{LAB}) of (?P<e>{ENT})\?"),
    ("lookup", rf"State the (?P<a>{LAB}) of (?P<e>{ENT})\."),
    ("lookup", rf"Give the (?P<a>{LAB}) recorded for (?P<e>{ENT})\."),
    ("lookup", rf"Looking at (?P<e>{ENT}): what is its (?P<a>{LAB})\?"),
    ("rel_lookup", rf"What is the (?P<a>{LAB}) of the (?P<r>{PAR}) of (?P<e>{ENT})\?"),
    ("rel_lookup", rf"Find the (?P<r>{PAR}) of (?P<e>{ENT}), then state its (?P<a>{LAB})\."),
    ("rel_lookup", rf"Look up the (?P<r>{PAR}) of (?P<e>{ENT}) and report its (?P<a>{LAB})\."),
    ("rel_lookup", rf"For the (?P<r>{PAR}) of (?P<e>{ENT}), what is the (?P<a>{LAB})\?"),
    ("chain2", rf"What is the (?P<a>{LAB}) of the (?P<r>{PAR}) of the (?P=r) of (?P<e>{ENT})\?"),
    ("chain2", rf"Starting at (?P<e>{ENT}), go to its (?P<r>{PAR}), then to that organisation's (?P=r), and state the (?P<a>{LAB}) of the one you reach\."),
    ("chain2", rf"Give the (?P<a>{LAB}) of the (?P<r>{PAR}) of the (?P=r) of (?P<e>{ENT})\."),
    ("chain2", rf"For the (?P<r>{PAR}) of the (?P=r) of (?P<e>{ENT}), what is the (?P<a>{LAB})\?"),
    ("compare", rf"Is the (?P<a>{LAB}) of (?P<x>{ENT}) (?P<op>{OP}) than the (?P=a) of (?P<y>{ENT})\?"),
    ("compare", rf"Does (?P<x>{ENT}) have a (?P<op>{OP}) (?P<a>{LAB}) than (?P<y>{ENT})\?"),
    ("compare", rf"Which has the (?P<op>{OP}) (?P<a>{LAB}): (?P<x>{ENT}) or (?P<y>{ENT})\?"),
    ("compare", rf"Compare (?P<x>{ENT}) and (?P<y>{ENT}): which one has the (?P<op>{OP}) (?P<a>{LAB})\?"),
    ("compare_rel", rf"Is the (?P<a>{LAB}) of (?P<x>{ENT}) (?P<op>{OP}) than the (?P=a) of the (?P<r>{PAR}) of (?P<y>{ENT})\?"),
    ("compare_rel", rf"Does (?P<x>{ENT}) have a (?P<op>{OP}) (?P<a>{LAB}) than the (?P<r>{PAR}) of (?P<y>{ENT})\?"),
    ("compare_rel", rf"Which is (?P<op>{OP}): the (?P<a>{LAB}) of (?P<x>{ENT}) or the (?P=a) of the (?P<r>{PAR}) of (?P<y>{ENT})\?"),
    ("compare_rel", rf"Compare the (?P<a>{LAB}) of (?P<x>{ENT}) with the (?P=a) of the (?P<r>{PAR}) of (?P<y>{ENT}): which is (?P<op>{OP})\?"),
    ("compare_parent", rf"Is the (?P<a>{LAB}) of (?P<x>{ENT}) (?P<op>{OP}) than the (?P=a) of its (?P<r>{PAR})\?"),
    ("compare_parent", rf"Does (?P<x>{ENT}) have a (?P<op>{OP}) (?P<a>{LAB}) than its (?P<r>{PAR})\?"),
    ("compare_parent", rf"Which is (?P<op>{OP}): the (?P<a>{LAB}) of (?P<x>{ENT}) or the (?P=a) of its (?P<r>{PAR})\?"),
    ("compare_parent", rf"Compare (?P<x>{ENT}) with its (?P<r>{PAR}): which has the (?P<op>{OP}) (?P<a>{LAB})\?"),
]


def parse_rows(text):
    rows = []
    for line in text.split("\n")[1:]:
        for pat in ROW_PATTERNS:
            m = re.fullmatch(pat, line)
            if m:
                e, a, v = m.groups()
                if (e, a) != ("Entity", "Attribute"):
                    rows.append((e, a, v))
                break
    return rows


def check(item):
    """the answer (True / False) recomputed from the rendered state alone"""
    st = item["state"]
    tbl = {}
    for e, a, v in parse_rows(st["facts"]):
        assert (e, a) not in tbl, f"duplicate row {e} {a}"
        tbl[(e, a)] = v
    hits = [(f, m.groupdict()) for f, pat in Q_PATTERNS for m in [re.fullmatch(pat, st["question"])] if m]
    assert len(hits) == 1, f"question parsed {len(hits)} times: {st['question']}"
    f, g = hits[0]
    has, get = (lambda e, a: (e, a) in tbl), (lambda e, a: tbl.get((e, a)))
    if f == "lookup":
        return has(g["e"], g["a"])
    if f == "rel_lookup":
        p = get(g["e"], g["r"])
        return p is not None and has(p, g["a"])
    if f == "compare":
        return has(g["x"], g["a"]) and has(g["y"], g["a"])
    if f in ("compare_rel", "compare_parent"):
        owner = g["y"] if f == "compare_rel" else g["x"]
        p = get(owner, g["r"])
        return has(g["x"], g["a"]) and p is not None and has(p, g["a"])
    p = get(g["e"], g["r"])
    p2 = get(p, g["r"]) if p is not None else None
    return p2 is not None and has(p2, g["a"])


# --------------------------------------------------------------------------------------------------- one pair
def make_pair(i, plan):
    """-> (positive spec, negative spec, info) for pair i; retries with fresh random draws until the pair is valid"""
    for attempt in range(300):
        rng = rng_for("pair", i, attempt)
        n_rows = plan["rows"]
        try:
            world = make_world(rng, {10: 5, 20: 8, 40: 14}[n_rows])
            q = make_question(rng, world, plan["form"])
            rows, layout, order = build_rows(rng, world, q, n_rows)
        except (RuntimeError, IndexError, ValueError):
            continue
        needs = needs_of(world, q)
        j = rng.randrange(len(needs))
        removed = next(r for r in rows if (r[0], r[1]) == (needs[j][0], needs[j][1]))
        dec = decoy_row(rng, world, rows, removed, plan["dev"])
        if dec is None:
            continue
        neg_rows = [dec if r == removed else r for r in rows]
        protected = {n[0] for n in needs} | set(named_entities(q)) | {dec[0]}
        comp = compensate(rng, world, neg_rows, dec, removed, plan["dev"], protected)
        if comp is None:
            continue
        neg_rows, old_row, new_row = comp
        if layout == "grouped":                                      # the changed rows take their natural place
            neg_rows.sort(key=lambda k: (order.index(k[0]), ATTRS.index(k[1])))
        labels = {a: rng.choice(LABELS[a]) for a in ATTRS}
        look = {"labels": labels, "style": rng.randrange(4), "pre": rng.randrange(4), "frame": rng.randrange(4)}
        base = {"q": q, "layout": layout, **look}
        return ({**base, "rows": rows}, {**base, "rows": neg_rows},
                {"role": needs[j][2], "removed": list(removed), "decoy": list(dec), "needs": [list(n) for n in needs],
                 "compensation": [list(old_row), list(new_row)]})
    raise RuntimeError(f"pair {i}: no valid draw")


def to_item(n, pair, spec, info, dev):
    st = {"facts": render_table(spec["rows"], spec["labels"], spec["style"], spec["pre"]),
          "question": render_question(spec["q"], spec["labels"], spec["frame"])}
    gold = "yes" if dev is None else "no"
    q = spec["q"]
    return {"id": f"{TASK}:{n:05d}", "state": st,
            "questions": {"q": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": dict(OPTIONS)}},
            "gold": gold, "soft": None, "group": f"{TASK}:pair:{pair:03d}",
            "meta": {"source_id": f"{n:05d}", "pair": pair, "hops": HOPS_OF[q["form"]], "rows": len(spec["rows"]),
                     "form": q["form"], "deviation": dev or "none", "missing_role": info["role"] if dev else None,
                     "table_layout": spec["layout"], "table_style": spec["style"],
                     "spec": {"q": q, "rows": [list(r) for r in spec["rows"]], "labels": spec["labels"],
                              "needs": info["needs"], "removed": info["removed"] if dev else None,
                              "decoy": info["decoy"] if dev else None,
                              "compensation": info["compensation"] if dev else None}}}


# --------------------------------------------------------------------------------------------------- the plan
def make_plan():
    """300 pairs: hops x rows on a Latin square (33 / 34 pairs per cell), forms and deviation kinds balanced per hops"""
    rng = rng_for("plan")
    plan = []
    for h in (1, 2, 3):
        cells = []
        for r_idx, r in enumerate((10, 20, 40)):
            cells += [r] * (34 if r_idx == h - 1 else 33)
        rng.shuffle(cells)
        forms = {1: ["lookup"], 2: ["rel_lookup", "compare"], 3: ["compare_rel", "compare_parent", "chain2"]}[h]
        form_list = [forms[k % len(forms)] for k in range(100)]
        rng.shuffle(form_list)
        devs = ["other_entity"] * 50 + ["other_attribute"] * 50
        rng.shuffle(devs)
        plan += [{"hops": h, "rows": cells[k], "form": form_list[k], "dev": devs[k]} for k in range(100)]
    rng.shuffle(plan)
    return plan


def assign_orders(rows):
    """the order of the two options is drawn per item (exactly half of the positives and half of the negatives list `yes` first - within
    every level when the items have one), recorded in meta.order and frozen in the file"""
    rng = rng_for("options")
    levels = sorted({r["meta"].get("level") for r in rows}, key=lambda x: (x is not None, x))     # v1 has no level: one group per class
    for gold in ("yes", "no"):
        for level in levels:
            idx = [i for i, r in enumerate(rows) if r["gold"] == gold and r["meta"].get("level") == level]
            flags = [True] * (len(idx) // 2) + [False] * (len(idx) - len(idx) // 2)
            rng.shuffle(flags)
            for i, yes_first in zip(idx, flags):
                order = ["yes", "no"] if yes_first else ["no", "yes"]
                rows[i]["questions"]["q"]["criteria"] = {k: OPTIONS[k] for k in order}
                rows[i]["meta"]["order"] = order


# ------------------------------------------------------------------------------------------ vocabulary test
TOKEN = re.compile(r"[a-z0-9]+(?:[-_'][a-z0-9]+)*")


def state_text(item):
    st = item["state"]
    return st if isinstance(st, str) else "\n".join(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for v in st.values())


def vocabulary_test(items, classes, min_freq=20, max_ratio=2.0):
    """no token of frequency >= min_freq may occur in one class at more than max_ratio times the rate of another class"""
    cnt = {c: collections.Counter() for c in classes}
    for it in items:
        cnt[it["_class"]].update(TOKEN.findall(state_text(it).lower()))
    tot = {c: sum(cnt[c].values()) for c in classes}
    worst, tested, bad = (1.0, ""), 0, []
    for tok in sorted(set().union(*cnt.values())):
        if sum(cnt[c][tok] for c in classes) < min_freq:
            continue
        tested += 1
        rate = [cnt[c][tok] / tot[c] for c in classes]
        ratio = max(rate) / min(rate) if min(rate) > 0 else float("inf")
        if ratio > worst[0]:
            worst = (ratio, tok)
        if ratio > max_ratio:
            bad.append((tok, [cnt[c][tok] for c in classes]))
    assert not bad, f"vocabulary cue: {bad[:10]}"
    return tested, worst


# --------------------------------------------------------------------------------------------------- output
def run_tool(script, *args):
    r = subprocess.run([sys.executable, os.path.join(AUDITS, script), "--root", HERE] + list(args), capture_output=True, text=True, cwd=REPO)
    return r.stdout.strip().split("\n")


def fmt_item(it):
    out = [f"id `{it['id']}` (pair `{it['group']}`, gold **{it['gold']}**, deviation `{it['meta']['deviation']}`)", "",
           "state.facts:", "```", it["state"]["facts"], "```", "state.question:", "```", it["state"]["question"], "```",
           f"question: {it['questions']['q']['instructions']}", ""]
    out += [f"- `{k}`: {v}" for k, v in it["questions"]["q"]["criteria"].items()]
    return "\n".join(out)


def main_v1():
    plan = make_plan()
    items, stats = [], collections.Counter()
    for i, p in enumerate(plan):
        pos, neg, info = make_pair(i, p)
        e0, a0, _ = info["removed"]                                  # the asked organisation and attribute keep their row counts
        cnt = lambda rows: (sum(r[0] == e0 for r in rows), sum(r[1] == a0 for r in rows))
        assert cnt(pos["rows"]) == cnt(neg["rows"]), (i, cnt(pos["rows"]), cnt(neg["rows"]))
        assert len(set(pos["rows"]) - set(neg["rows"])) == 2 and len(pos["rows"]) == len(neg["rows"])   # needed row + one neutral row
        items.append((i, pos, info, None))
        items.append((i, neg, info, p["dev"]))
    rng = rng_for("order")
    rng.shuffle(items)
    rows = []
    for n, (pair, spec, info, dev) in enumerate(items, 1):
        it = to_item(n, pair, spec, info, dev)
        # ---- truth twice
        assert truth(spec) == (dev is None), f"{it['id']}: truth {truth(spec)} but planted deviation {dev}"
        assert check(it) == truth(spec), f"{it['id']}: check {check(it)} != truth {truth(spec)}"
        assert (it["gold"] == "yes") == check(it)
        # ---- exactly one fact affected
        tbl = {(e, a) for e, a, _ in spec["rows"]}
        missing = [k for k in info["needs"] if (k[0], k[1]) not in tbl]
        assert len(missing) == (0 if dev is None else 1), (it["id"], missing)
        assert len(spec["rows"]) == it["meta"]["rows"] in (10, 20, 40)
        assert len(parse_rows(it["state"]["facts"])) == len(spec["rows"])
        text = it["state"]["facts"]
        for e in named_entities(spec["q"]):
            assert e in text, f"{it['id']}: {e} not mentioned any more"
        if dev:
            e0, a0, _ = info["removed"]
            e1, a1, _ = info["decoy"]
            assert (e1 != e0 and a1 == a0) if dev == "other_entity" else (e1 == e0 and a1 != a0), (it["id"], dev)
            assert (e1, a1) not in {(r[0], r[1]) for r in spec["rows"] if list(r) != info["decoy"]}
        it["_class"] = it["gold"]
        rows.append(it)
    rows.sort(key=lambda r: r["id"])
    assign_orders(rows)
    # ---- balance and dials
    cls = collections.Counter(r["gold"] for r in rows)
    assert cls == {"yes": 300, "no": 300}, cls
    by = lambda key: collections.Counter(r["meta"][key] for r in rows)
    assert set(by("hops").values()) == {200} and set(by("rows").values()) == {200}, (by("hops"), by("rows"))
    cell = collections.Counter((r["meta"]["hops"], r["meta"]["rows"]) for r in rows)
    assert set(cell.values()) <= {66, 68}, cell
    dev = collections.Counter(r["meta"]["deviation"] for r in rows)
    assert dev["other_entity"] == dev["other_attribute"] == 150, dev
    tested, worst = vocabulary_test(rows, ["yes", "no"])
    lengths = [len(state_text(r)) for r in rows]
    for r in rows:
        del r["_class"]
    d = f"{HERE}/tasks/{TASK}"
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/items.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(rows, key=lambda r: r["id"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    task = {"task": TASK, "layer": "A", "title": "Generated facts tables: can the question be answered from the facts listed?",
            "decision": "whether a question can be answered from the facts of a table (yes) or at least one fact it needs is not listed (no)",
            "source": {"name": f"generator build/gen_{TASK}.py", "url": "", "files": [], "split": "generated, seed 20261007",
                       "version": "script of 2026-10-07"},
            "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
            "labels": "programmatic", "item_source": "generated", "metric": "accuracy", "chance": 0.5, "rows": len(rows),
            "groups": PAIRS, "question_type": "choice", "options": 2,
            "notes": ("600 items = 300 contrast pairs (meta.pair, group): a facts table with a question (yes) and the same table in which "
                      "one needed row is replaced at the same place by another attribute of the same organisation or the same attribute "
                      "of another organisation (no). The metric is item accuracy; the group allows a pair analysis. Dials: hops "
                      "(facts needed: 1, 2, 3) x rows (10, 20, 40). Everything is invented and every answer is computed twice (specification and "
                      "a parser of the rendered text). State length %d to %d characters (median %d)." % (min(lengths), max(lengths), sorted(lengths)[300]))}
    json.dump(task, open(f"{d}/task.json", "w"), indent=1)
    val = run_tool("validate.py", TASK)
    aud = run_tool("audit.py", TASK)
    print(val[1] if len(val) > 1 else val)
    print(aud[0])
    print(aud[1] if len(aud) > 1 else aud)
    sys.dont_write_bytecode = True
    sys.path.insert(0, AUDITS)
    import audit
    audit.HERE = HERE                       # the audit reads HERE/tasks/<family>/
    a = audit.audit(TASK)
    assert not a["flag"] and a["length"] < 0.55, a
    write_readme_v1(d, rows, dev, cell, lengths, val, aud, tested, worst)
    print("vocabulary test:", tested, "tokens with frequency >= 20, worst ratio %.2f (%s)" % worst)
    print("counts per class", dict(cls), "| hops", dict(by("hops")), "| rows", dict(by("rows")), "| deviation", dict(dev))
    print("state length", min(lengths), max(lengths), "median", sorted(lengths)[300])


def write_readme_v1(d, rows, dev, cell, lengths, val, aud, tested, worst):
    forms = ", ".join(f"`{f}` {sum(1 for r in rows if r['meta']['form'] == f and r['gold'] == 'yes')}" for f in FORMS)
    roles = collections.Counter(r["meta"]["missing_role"] for r in rows if r["gold"] == "no")
    roles = ", ".join(f"`{k}` {v}" for k, v in sorted(roles.items()))
    ex = []
    for h, r in ((1, 10), (2, 20), (3, 40)):
        ex.append(next(x for x in sorted(rows, key=lambda x: x["id"]) if x["meta"]["hops"] == h and x["meta"]["rows"] == r and x["gold"] == "no"))
    txt = f"""# {TASK}

Generated facts tables: can the question be answered from the facts listed? (layer A, generated, programmatic truth)

- Decision: whether a question can be answered from the facts of a table (yes) or at least one fact it needs is not listed (no).
- Source: generator `build/gen_{TASK}.py` (standard library only, `random.Random(20261007)` and sub-generators; the output is identical on every run); no third-party text.
- Licence: generated by the benchmark's script (no third-party text); items included.
- Rows: {len(rows)} in {PAIRS} contrast pairs (300 yes, 300 no); metric: accuracy (chance 0.5).
- Rebuild: `python3 build/gen_{TASK}.py`

## What is generated

A table of facts about invented organisations (rows `entity · attribute · value`; attributes: founding year, headquarters, parent
organisation, head count, product line, number of sites, chief executive; every organisation name, city, product and person is made by a
syllable generator) and one question that needs one, two or three of the facts: a look-up, a look-up through the parent organisation, a
comparison of two numbers, a comparison in which one number is reached through the parent, a chain of two parent links. The table is
shown in one of four layouts, with one of four label sets and one of four question phrasings per question type (chosen per item).
The question is answerable (yes) when every needed fact is a row of the table; nothing outside the table may be used, and the table says so.
The order of the two options is drawn per item (`meta.order`; exactly half of the positives and half of the negatives list `yes` first).

**Pairs.** The positive and the negative of a pair share the table except two rows: the negative replaces one row the question needs
by a fact about the same attribute of another organisation (often one with the same family name) or by another attribute of the
same organisation (`meta.deviation` = `other_entity` / `other_attribute`; `meta.missing_role` says which needed fact is gone: the value, the
link to the parent, one side of a comparison). The table keeps its size and still mentions every organisation of the question. The second
changed row is a neutral filler row (`meta.spec.compensation`) that gives the asked organisation (other_entity) or the asked attribute (other_attribute)
the same number of rows as in the positive, so that these counts say nothing about the answer. In the grouped layout the changed rows take their
natural place. Length, vocabulary and structure of the two classes are therefore the same by construction.

## Dials

| dial | levels | items per level |
|---|---|---|
| `hops` (facts the question needs) | 1, 2, 3 | 200 each |
| `rows` (rows of the table) | 10, 20, 40 | 200 each |

The nine cells hold {min(cell.values())} to {max(cell.values())} items each (33 or 34 pairs). State length: {min(lengths)} to {max(lengths)} characters (median {sorted(lengths)[len(lengths)//2]}).

## Deviation kinds (negatives)

| `meta.deviation` | items |
|---|---|
| `other_entity` | {dev['other_entity']} |
| `other_attribute` | {dev['other_attribute']} |

Question forms (`meta.form`, per class): {forms}. Missing fact (`meta.missing_role`, negatives): {roles}.

## Checks made by the script

- `truth(spec)` (structured question over the structured table) and `check(item)` (parses the rendered text only) agree on all 600 items.
- Every planted deviation turns the answer from yes to no and exactly one needed fact is missing; the table has the same number of rows; every organisation named in the question is still mentioned; the asked organisation and the asked attribute have the same number of rows in both members of a pair.
- Classes are exactly balanced; every dial level has exactly 200 items.
- Vocabulary test: {tested} tokens of frequency >= 20 are tested; none occurs in one class at more than twice the rate of the other (largest ratio {worst[0]:.2f}, `{worst[1]}`).
- Shortcut audit (`python3 audit.py {TASK}`), best length rule below 0.55:

```
{aud[0]}
{aud[1]}
```

Validator: `{val[1].strip() if len(val) > 1 else val}`

## Examples (one per `hops` level; negatives)

""" + "\n\n".join(f"### hops = {x['meta']['hops']}, rows = {x['meta']['rows']}\n\n" + fmt_item(x) for x in ex) + """

## Independence from training generators

The items are disjoint from any training generator of the authors by construction: this is a new generator, written for the benchmark;
names, templates and fact tables share nothing with the generators used for training.
"""
    open(f"{d}/README.md", "w", encoding="utf-8").write(txt)


# ================================================================================================================ version v2
# The harder version (the default).  The pair design, the count matching and the checks are those of v1; what changes is the
# material: hops 2 / 3 / 4, rows 20 / 40 / 80 with up to 26 look-alike organisations (one family name, many suffixes), a near-miss
# row for every needed fact, two readings that need a rule written in the state (a total over the listed subsidiaries; a region
# taken over from the parent) and a table whose first lines state the rules of reading.
ATTRS2 = ATTRS + ["region"]
LABELS2 = dict(LABELS, region=["operating region", "home region", "region of operation", "base region"])
LOOKUP2 = ["founded", "hq", "staff", "product", "sites", "ceo"]    # what a question may ask for (not the link, not the region)
FORMS_BY_HOPS2 = {2: ["rel_lookup", "compare", "inherit", "rev_lookup"], 3: ["chain2", "compare_rel", "compare_parent", "inherit_rel"],
                  4: ["chain3", "compare_chain2", "agg_subs", "inherit_chain2"]}
FORMS2 = [f for h in (2, 3, 4) for f in FORMS_BY_HOPS2[h]]
HOPS2 = {f: h for h, fs in FORMS_BY_HOPS2.items() for f in fs}
ROWS2 = (20, 40, 80)
N_ENT2 = {20: 8, 40: 14, 80: 26}
NEAR2 = {20: 1, 40: 2, 80: 3}                                      # near-miss rows (the same attribute of a look-alike) per needed row
# gen_v4: the level ladder.  Both dials rise with the level; every level holds 100 pairs (200 items).
LEVELS = {1: (2, 20), 2: (3, 40), 3: (4, 80)}                      # meta.level -> (meta.hops, meta.rows)
REGION_FORMS = ("inherit", "inherit_rel", "inherit_chain2")        # the questions that need rule 4 (a region taken over from the parent)
FORM_PAIRS = {"rel_lookup": 20, "compare": 20, "inherit": 40, "rev_lookup": 20,                   # pairs per form (100 per level):
              "chain2": 20, "compare_rel": 20, "compare_parent": 20, "inherit_rel": 40,           # 40 % of every level ask for a region
              "chain3": 20, "compare_chain2": 20, "agg_subs": 20, "inherit_chain2": 40}
# gen_v4: founding years.  Drawn family by family, never clamped.
YEAR_LO, YEAR_HI = 1880, 2024                                      # every founding year lies in this range
GAP = (2, 20)                                                      # a subsidiary is founded 2 to 20 years after its parent
UNREMOVABLE = {"agg_subs": {"link1", "link2"}}                     # a link row of a total is not removed: that would only change WHICH organisations are totalled
RULES2 = {
    "closed": ["Use only the rows below; a fact that has no row is unknown.",
               "These rows are everything that is known, and nothing outside them may be assumed.",
               "Answer from the rows alone: whatever has no row is not available.",
               "The table is the only source, and a fact without a row cannot be used."],
    "links": ["Organisations are related only where a row says so: a {P} row makes an organisation a subsidiary of the one it names, and a shared family name proves nothing.",
              "A {P} row is the only evidence of a link between two organisations; an organisation is a subsidiary of another only if its own {P} row names it.",
              "Links exist only where a row states them: an organisation is a subsidiary of X only if it has a {P} row that names X, and similar names do not count.",
              "Do not infer links from names; an organisation counts as a subsidiary of another only when its {P} row names it."],
    "figures": ["A comparison or a total needs the figure of every organisation it covers, and no figure can be worked out from other figures.",
                "Every organisation in a comparison or a total needs a figure of its own in a row; a figure is never calculated from other rows.",
                "For a comparison or a sum, each organisation involved must have its own figure; the totals, differences or averages of other figures do not replace it.",
                "Each figure must have its own row: a figure is never taken from the figures of other organisations, and a comparison or a total needs all the figures it covers."],
    "region": ["One exception: an organisation that has no row for its {R} takes over the {R} of its parent, provided the parent has a row for its own {R}.",
               "The {R} is the one fact that is inherited: when an organisation has no {R} row, it takes the {R} of its parent, if the parent has {aR} row of its own.",
               "If an organisation has no {R} row, its {R} is that of its parent, but only when the parent has {aR} row; no other fact is taken over from a parent.",
               "An organisation without {aR} row shares the {R} of its parent, as long as the parent has {aR} row of its own. Nothing else is inherited."],
}
RULE_KEYS = ["closed", "links", "figures", "region"]


def stem_of(e):
    return e.split()[0]


def depth_of(world, e):
    d = 0
    while world[e]["parent"]:
        e, d = world[e]["parent"], d + 1
    return d


def children_of(world):
    kids = collections.defaultdict(list)
    for e, d in world.items():
        if d["parent"]:
            kids[d["parent"]].append(e)
    return kids


def draw_years(rng, world):
    """founding years, family by family (gen_v4; the first release clamped them with min(2022, parent + 0..25), so a quarter of all
    years were exactly 2022): every subsidiary is founded GAP years after its parent, so the order parent -> child holds by
    construction; the year of the head is drawn uniformly from the window in which the youngest member of the family still fits
    below YEAR_HI.  Every year lies in YEAR_LO..YEAR_HI and no value is clamped to a bound."""
    families = collections.OrderedDict()
    for e in world:
        families.setdefault(stem_of(e), []).append(e)
    year = {}
    for members in families.values():
        offset = {}
        for e in members:                                           # a parent is listed before its children
            p = world[e]["parent"]
            offset[e] = 0 if p is None else offset[p] + rng.randint(*GAP)
        head = rng.randint(YEAR_LO, YEAR_HI - max(offset.values()))
        for e in members:
            year[e] = head + offset[e]
    return year


def make_world_v2(rng, n_ent):
    """organisations in 2 to 4 families (one family name, one head, many suffixes); the first family has a chain of three links
    (head <- a <- b <- c), the others a head with two or more children, so every form has material"""
    n_fam = {8: 2, 14: 3, 26: 4}[n_ent]
    sizes = [n_ent // n_fam + (1 if k < n_ent % n_fam else 0) for k in range(n_fam)]
    cities = [coin(rng) for _ in range(rng.randint(6, 9))]
    brands = [coin(rng) for _ in range(rng.randint(5, 8))]
    regions = []
    while len(regions) < 6:
        r = coin(rng)
        if r not in regions:
            regions.append(r)
    world, stems, depth = collections.OrderedDict(), set(), {}
    for f, size in enumerate(sizes):
        while True:
            stem = coin(rng)
            if stem not in stems:
                stems.add(stem)
                break
        suf = rng.sample(SUFFIX_MEMBER, size - 1)
        names = [f"{stem} {rng.choice(SUFFIX_HEAD)}"] + [f"{stem} {s}" for s in suf]
        for k, name in enumerate(names):
            if k == 0:
                parent, depth[name] = None, 0
            else:
                if f == 0 and k <= 3:
                    parent = names[k - 1]                           # the chain
                elif f > 0 and k <= 2:
                    parent = names[0]                               # a head with two children
                elif f > 0 and k == 3:
                    parent = names[1]
                else:
                    parent = rng.choice([n for n in names[:k] if depth[n] <= 2])
                depth[name] = depth[parent] + 1
            world[name] = {"parent": parent}
    year = draw_years(rng, world)
    used_staff = set()
    for name, d in world.items():
        d["founded"] = year[name]
        while True:
            st = int(round(10 ** rng.uniform(1.2, 3.9)))
            if st not in used_staff:
                used_staff.add(st)
                break
        d["staff"] = st
        d["sites"] = rng.randint(1, 40)
        d["hq"] = rng.choice(cities)
        d["product"] = f"{rng.choice(brands)} {rng.choice(PRODUCT_NOUN)}"
        d["ceo"] = person(rng)
        d["region"] = rng.choice(regions)
    return world


def make_question_v2(rng, world, form):
    ents = list(world)
    with_parent = [e for e in ents if world[e]["parent"]]
    kids = children_of(world)
    stems = collections.defaultdict(list)
    for e in ents:
        stems[stem_of(e)].append(e)
    for _ in range(400):
        op = rng.choice(["greater", "smaller"])
        if form == "rel_lookup":
            return {"form": form, "e": rng.choice(with_parent), "a": rng.choice(LOOKUP2)}
        if form == "inherit":
            return {"form": form, "e": rng.choice(with_parent), "a": "region"}
        if form == "inherit_rel":
            return {"form": form, "e": rng.choice([e for e in with_parent if depth_of(world, e) >= 2]), "a": "region"}
        if form == "inherit_chain2":
            return {"form": form, "e": rng.choice([e for e in with_parent if depth_of(world, e) >= 3]), "a": "region"}
        if form == "chain2":
            return {"form": form, "e": rng.choice([e for e in with_parent if depth_of(world, e) >= 2]), "a": rng.choice(LOOKUP2)}
        if form == "chain3":
            return {"form": form, "e": rng.choice([e for e in with_parent if depth_of(world, e) >= 3]), "a": rng.choice(LOOKUP2)}
        if form == "agg_subs":
            x = rng.choice([p for p, ks in kids.items() if len(ks) >= 2])
            return {"form": form, "e": x, "a": rng.choice(["staff", "sites"]), "subs": rng.sample(kids[x], 2)}
        if form == "rev_lookup":                                    # the ONE subsidiary of x that the table lists (other children are not listed)
            x = rng.choice([p for p, ks in kids.items() if len(ks) >= 2] if rng.random() < 0.6 else list(kids))
            return {"form": form, "e": x, "a": rng.choice(LOOKUP2), "subs": [rng.choice(kids[x])]}
        a = rng.choice(NUMERIC)
        if form == "compare":
            if rng.random() < 0.6:                                  # two look-alikes: one family name
                x, y = rng.sample(rng.choice([m for m in stems.values() if len(m) >= 2]), 2)
            else:
                x, y = rng.sample(ents, 2)
            if world[x][a] != world[y][a]:
                return {"form": form, "x": x, "y": y, "a": a, "op": op}
        elif form == "compare_rel":
            x, y = rng.choice(ents), rng.choice(with_parent)
            if x != y and x != world[y]["parent"] and world[x][a] != world[world[y]["parent"]][a]:
                return {"form": form, "x": x, "y": y, "a": a, "op": op}
        elif form == "compare_parent":
            x = rng.choice(with_parent)
            if world[x][a] != world[world[x]["parent"]][a]:
                return {"form": form, "x": x, "a": a, "op": op}
        elif form == "compare_chain2":
            y = rng.choice([e for e in with_parent if depth_of(world, e) >= 2])
            p1 = world[y]["parent"]
            p2 = world[p1]["parent"]
            x = rng.choice(ents)
            if x not in (y, p1, p2) and world[x][a] != world[p2][a]:
                return {"form": form, "x": x, "y": y, "a": a, "op": op}
    raise RuntimeError("no question")


def named_entities_v2(q):
    return [q[k] for k in ("e", "x", "y") if k in q]


def needs_of_v2(world, q):
    """the rows the question needs: [(entity, attribute, role)] in reading order; for a region that is taken over from the parent
    the rows of the derivation (the link, the parent's own region row); for a total the link and the figure of every listed subsidiary"""
    f = q["form"]
    if f in ("rel_lookup", "compare", "compare_rel", "compare_parent", "chain2"):
        return needs_of(world, q)
    if f == "inherit":
        return [(q["e"], "parent", "link"), (world[q["e"]]["parent"], "region", "value")]
    if f == "inherit_rel":
        p1 = world[q["e"]]["parent"]
        return [(q["e"], "parent", "link1"), (p1, "parent", "link2"), (world[p1]["parent"], "region", "value")]
    if f == "inherit_chain2":
        p1 = world[q["e"]]["parent"]
        p2 = world[p1]["parent"]
        return [(q["e"], "parent", "link1"), (p1, "parent", "link2"), (p2, "parent", "link3"), (world[p2]["parent"], "region", "value")]
    if f == "chain3":
        p1 = world[q["e"]]["parent"]
        p2 = world[p1]["parent"]
        return [(q["e"], "parent", "link1"), (p1, "parent", "link2"), (p2, "parent", "link3"), (world[p2]["parent"], q["a"], "value")]
    if f == "compare_chain2":
        p1 = world[q["y"]]["parent"]
        p2 = world[p1]["parent"]
        return [(q["x"], q["a"], "left"), (q["y"], "parent", "link1"), (p1, "parent", "link2"), (p2, q["a"], "value")]
    if f == "agg_subs":
        k1, k2 = q["subs"]
        return [(k1, "parent", "link1"), (k1, q["a"], "value1"), (k2, "parent", "link2"), (k2, q["a"], "value2")]
    if f == "rev_lookup":
        k = q["subs"][0]
        return [(k, "parent", "link"), (k, q["a"], "value")]
    raise ValueError(f)


INHERIT_DEPTH = {"inherit": 0, "inherit_rel": 1, "inherit_chain2": 2}      # how many links from the named organisation to the one whose region is asked


def forbidden_v2(world, q):
    """rows that must not occur in the table: the region row of the organisation that has to take its region over, and the link
    row of every other child of the asked parent (so that exactly the chosen subsidiaries are listed)"""
    if q["form"] in INHERIT_DEPTH:                                  # the organisation whose region is asked has no region row of its own
        e = q["e"]
        for _ in range(INHERIT_DEPTH[q["form"]]):
            e = world[e]["parent"]
        return {(e, "region")}
    if "subs" in q:
        return {(c, "parent") for c in world if world[c]["parent"] == q["e"] and c not in q["subs"]}
    return set()


def build_rows_v2(rng, world, q, n_rows, forbidden):
    """-> (rows, layout, order, structural keys).  The base table: the needed rows; one more row for every organisation the question
    names; for every needed row the SAME attribute of a look-alike sibling (a near miss); a child row that names a named organisation
    as its parent (a link that points the other way); then random rows."""
    needs = needs_of_v2(world, q)
    chosen = []

    def add(key):
        if key in chosen or key in forbidden:
            return False
        chosen.append(key)
        return True

    for e, a, _ in needs:
        assert add((e, a))
    structural = set(chosen)
    for e in sorted(set(named_entities_v2(q))):
        free = [a for a in ATTRS2 if exists(world, e, a) and (e, a) not in chosen and (e, a) not in forbidden]
        key = (e, rng.choice(free))
        add(key)
        structural.add(key)
    reserved = set()                                                # one more look-alike row per needed row is kept back for the decoy
    for e, a, _ in needs:
        sibs = [s for s in world if s != e and stem_of(s) == stem_of(e) and exists(world, s, a)
                and (s, a) not in chosen and (s, a) not in forbidden and (s, a) not in reserved]
        rng.shuffle(sibs)
        for s in sibs[:NEAR2[n_rows]]:
            add((s, a))
            structural.add((s, a))
        rest = sibs[NEAR2[n_rows]:]
        if rest:
            reserved.add((rng.choice(rest), a))
    kids = children_of(world)
    for e in sorted(set(named_entities_v2(q))):
        free = [c for c in kids.get(e, []) if (c, "parent") not in chosen and (c, "parent") not in forbidden]
        if free and rng.random() < 0.7:
            key = (rng.choice(free), "parent")
            add(key)
            structural.add(key)
    pool = [(e, a) for e in world for a in ATTRS2 if exists(world, e, a) and (e, a) not in chosen and (e, a) not in forbidden and (e, a) not in reserved]
    rng.shuffle(pool)
    chosen += pool[:n_rows - len(chosen)]
    assert len(chosen) == n_rows, (len(chosen), n_rows)
    if rng.random() < 0.5:                                          # grouped by organisation
        order = list(world)
        rng.shuffle(order)
        chosen.sort(key=lambda k: (order.index(k[0]), ATTRS2.index(k[1])))
        layout = "grouped"
    else:
        order = None
        rng.shuffle(chosen)
        layout = "shuffled"
    return [(e, a, str(world[e][a])) for e, a in chosen], layout, order, structural


def decoy_row_v2(rng, world, rows, removed, kind, forbidden):
    """the row that takes the place of the removed row: the same attribute of a look-alike (same family name) when there is one
    (other_entity), or another attribute of the same organisation (other_attribute)"""
    keys = {(e, a) for e, a, _ in rows}
    e, a, _ = removed
    if kind == "other_entity":
        cands = [(e2, a) for e2 in world if e2 != e and exists(world, e2, a) and (e2, a) not in keys and (e2, a) not in forbidden]
        mates = [c for c in cands if stem_of(c[0]) == stem_of(e)]
        cands = mates or cands
    else:
        cands = [(e, a2) for a2 in ATTRS2 if a2 != a and exists(world, e, a2) and (e, a2) not in keys and (e, a2) not in forbidden]
    if not cands:
        return None
    e2, a2 = rng.choice(cands)
    return (e2, a2, str(world[e2][a2]))


def compensate_v2(rng, world, rows, dec, removed, kind, protected_entities, protected_keys, forbidden):
    """as in v1 (one neutral filler row is changed so that the asked organisation / attribute keeps its number of rows), with the
    forbidden rows excluded, the near-miss rows left alone and a filler of the same family preferred"""
    keys = {(r[0], r[1]) for r in rows}
    e0, a0, _ = removed
    cands = []
    for k, r in enumerate(rows):
        if r == dec or r[0] in protected_entities or (r[0], r[1]) in protected_keys or r[1] == a0:
            continue
        if kind == "other_entity":
            if exists(world, e0, r[1]) and (e0, r[1]) not in keys and (e0, r[1]) not in forbidden:
                cands.append((k, (e0, r[1], str(world[e0][r[1]]))))
        elif exists(world, r[0], a0) and (r[0], a0) not in keys and (r[0], a0) not in forbidden:
            cands.append((k, (r[0], a0, str(world[r[0]][a0]))))
    same = [c for c in cands if stem_of(rows[c[0]][0]) == stem_of(e0)]
    cands = same or cands
    if not cands:
        return None
    k, new = rng.choice(cands)
    return rows[:k] + [new] + rows[k + 1:], rows[k], new


# ------------------------------------------------------------------------------------------------------ rendering (v2)
TABLE_HEADERS = {"Entity · Attribute · Value", "| Entity | Attribute | Value |", "|---|---|---|"}


def with_article(label):
    return ("an " if label[0] in "aeiou" else "a ") + label


def render_facts_v2(rows, labels, style, phr, order):
    """the four rules of reading (one wording each, in a drawn order), then the table in one of four layouts"""
    text = {"closed": RULES2["closed"][phr["closed"]], "links": RULES2["links"][phr["links"]].format(P=labels["parent"]),
            "figures": RULES2["figures"][phr["figures"]], "region": RULES2["region"][phr["region"]].format(R=labels["region"], aR=with_article(labels["region"]))}
    lines = [text[k] for k in order]
    if style == 0:
        lines += ["Entity · Attribute · Value"] + [f"{e} · {labels[a]} · {v}" for e, a, v in rows]
    elif style == 1:
        lines += ["| Entity | Attribute | Value |", "|---|---|---|"] + [f"| {e} | {labels[a]} | {v} |" for e, a, v in rows]
    elif style == 2:
        lines += [f"- {e} — {labels[a]}: {v}" for e, a, v in rows]
    else:
        lines += [f"{n}. {e} | {labels[a]} | {v}" for n, (e, a, v) in enumerate(rows, 1)]
    return "\n".join(lines)


def render_question_v2(q, labels, frame):
    f, a, R, op = q["form"], labels.get(q.get("a")), labels["parent"], q.get("op")
    if f in INHERIT_DEPTH:                                          # worded like the plain look-up through 0, 1 or 2 links
        if f == "inherit":
            return ["What is the {a} of {e}?", "State the {a} of {e}.", "Give the {a} of {e}.", "Looking at {e}: what is its {a}?"
                    ][frame].format(a=a, e=q["e"])
        return render_question({**q, "form": {"inherit_rel": "rel_lookup", "inherit_chain2": "chain2"}[f]}, labels, frame)
    if f == "chain3":
        return ["What is the {a} of the {R} of the {R} of the {R} of {e}?",
                "Starting at {e}, follow the {R} link three times and state the {a} of the organisation you reach.",
                "Give the {a} of the {R} of the {R} of the {R} of {e}.", "For the {R} of the {R} of the {R} of {e}, what is the {a}?"
                ][frame].format(a=a, R=R, e=q["e"])
    if f == "compare_chain2":
        return ["Is the {a} of {x} {op} than the {a} of the {R} of the {R} of {y}?", "Does {x} have a {op} {a} than the {R} of the {R} of {y}?",
                "Which is {op}: the {a} of {x} or the {a} of the {R} of the {R} of {y}?",
                "Compare the {a} of {x} with the {a} of the {R} of the {R} of {y}: which is {op}?"
                ][frame].format(a=a, R=R, x=q["x"], y=q["y"], op=op)
    if f == "rev_lookup":
        return ["What is the {a} of the only subsidiary of {e} that the table lists?", "Find the one listed subsidiary of {e} and state its {a}.",
                "Give the {a} of the only subsidiary listed for {e}.", "For the only listed subsidiary of {e}, what is the {a}?"
                ][frame].format(a=a, e=q["e"])
    if f == "agg_subs":
        return ["What is the combined {a} of the listed subsidiaries of {e}?", "Add up the {a} of every subsidiary of {e} that the table lists.",
                "Give the total {a} of the subsidiaries of {e} listed in the table.", "What do the listed subsidiaries of {e} have as a combined {a}?"
                ][frame].format(a=a, e=q["e"])
    return render_question(q, labels, frame)                       # rel_lookup, compare, chain2, compare_rel, compare_parent


# ---------------------------------------------------------------------------------------- truth on the specification (v2)
def truth_v2(spec):
    """True when the question can be answered from the rows under the rules written in the state"""
    tbl = {(e, a): v for e, a, v in spec["rows"]}
    q, g = spec["q"], tbl.get
    f = q["form"]
    if f in INHERIT_DEPTH:                                          # follow the links to the organisation whose region is asked, then: its own row, or its parent's
        t = q["e"]
        for _ in range(INHERIT_DEPTH[f]):
            t = g((t, "parent"))
            if t is None:
                return False
        if (t, "region") in tbl:
            return True
        p = g((t, "parent"))
        return p is not None and (p, "region") in tbl
    if f == "chain3":
        p1 = g((q["e"], "parent"))
        p2 = g((p1, "parent")) if p1 is not None else None
        p3 = g((p2, "parent")) if p2 is not None else None
        return p3 is not None and (p3, q["a"]) in tbl
    if f == "compare_chain2":
        p1 = g((q["y"], "parent"))
        p2 = g((p1, "parent")) if p1 is not None else None
        return (q["x"], q["a"]) in tbl and p2 is not None and (p2, q["a"]) in tbl
    if f == "agg_subs":
        subs = [e for (e, a), v in tbl.items() if a == "parent" and v == q["e"]]
        return len(subs) >= 1 and all((s, q["a"]) in tbl for s in subs)
    if f == "rev_lookup":
        subs = [e for (e, a), v in tbl.items() if a == "parent" and v == q["e"]]
        return len(subs) == 1 and (subs[0], q["a"]) in tbl
    return truth(spec)


# ------------------------------------------------------------------ check (v2): the answer from the rendered text alone
ALL_LABELS2 = sorted({x for v in LABELS2.values() for x in v}, key=lambda x: (-len(x), x))
REGION_LABELS = set(LABELS2["region"])
LAB2 = "(?:" + "|".join(re.escape(x) for x in ALL_LABELS2) + ")"
REG2 = "(?:" + "|".join(re.escape(x) for x in sorted(REGION_LABELS, key=lambda x: (-len(x), x))) + ")"
REGA = "(?:an operating region|a home region|a region of operation|a base region)"          # the label with its article
# the rules of reading, written out again as patterns (the {P} / {R} slots take the labels of the item)
RULE_RX2 = {
    "closed": [re.escape(s) for s in RULES2["closed"]],
    "links": [rf"Organisations are related only where a row says so: a (?P<p>{PAR}) row makes an organisation a subsidiary of the one it names, and a shared family name proves nothing\.",
              rf"A (?P<p>{PAR}) row is the only evidence of a link between two organisations; an organisation is a subsidiary of another only if its own (?P=p) row names it\.",
              rf"Links exist only where a row states them: an organisation is a subsidiary of X only if it has a (?P<p>{PAR}) row that names X, and similar names do not count\.",
              rf"Do not infer links from names; an organisation counts as a subsidiary of another only when its (?P<p>{PAR}) row names it\."],
    "figures": [re.escape(s) for s in RULES2["figures"]],
    "region": [rf"One exception: an organisation that has no row for its (?P<r>{REG2}) takes over the (?P=r) of its parent, provided the parent has a row for its own (?P=r)\.",
               rf"The (?P<r>{REG2}) is the one fact that is inherited: when an organisation has no (?P=r) row, it takes the (?P=r) of its parent, if the parent has (?P<ra>{REGA}) row of its own\.",
               rf"If an organisation has no (?P<r>{REG2}) row, its (?P=r) is that of its parent, but only when the parent has (?P<ra>{REGA}) row; no other fact is taken over from a parent\.",
               rf"An organisation without (?P<ra>{REGA}) row shares the (?P<r>{REG2}) of its parent, as long as the parent has (?P=ra) row of its own\. Nothing else is inherited\."],
}


def _q_patterns2():
    L, P, E, O = LAB2, PAR, ENT, OP
    return [
        ("lookup", rf"What is the (?P<a>{L}) of (?P<e>{E})\?"), ("lookup", rf"State the (?P<a>{L}) of (?P<e>{E})\."),
        ("lookup", rf"Give the (?P<a>{L}) of (?P<e>{E})\."), ("lookup", rf"Looking at (?P<e>{E}): what is its (?P<a>{L})\?"),
        ("rel_lookup", rf"What is the (?P<a>{L}) of the (?P<r>{P}) of (?P<e>{E})\?"),
        ("rel_lookup", rf"Find the (?P<r>{P}) of (?P<e>{E}), then state its (?P<a>{L})\."),
        ("rel_lookup", rf"Look up the (?P<r>{P}) of (?P<e>{E}) and report its (?P<a>{L})\."),
        ("rel_lookup", rf"For the (?P<r>{P}) of (?P<e>{E}), what is the (?P<a>{L})\?"),
        ("chain2", rf"What is the (?P<a>{L}) of the (?P<r>{P}) of the (?P=r) of (?P<e>{E})\?"),
        ("chain2", rf"Starting at (?P<e>{E}), go to its (?P<r>{P}), then to that organisation's (?P=r), and state the (?P<a>{L}) of the one you reach\."),
        ("chain2", rf"Give the (?P<a>{L}) of the (?P<r>{P}) of the (?P=r) of (?P<e>{E})\."),
        ("chain2", rf"For the (?P<r>{P}) of the (?P=r) of (?P<e>{E}), what is the (?P<a>{L})\?"),
        ("chain3", rf"What is the (?P<a>{L}) of the (?P<r>{P}) of the (?P=r) of the (?P=r) of (?P<e>{E})\?"),
        ("chain3", rf"Starting at (?P<e>{E}), follow the (?P<r>{P}) link three times and state the (?P<a>{L}) of the organisation you reach\."),
        ("chain3", rf"Give the (?P<a>{L}) of the (?P<r>{P}) of the (?P=r) of the (?P=r) of (?P<e>{E})\."),
        ("chain3", rf"For the (?P<r>{P}) of the (?P=r) of the (?P=r) of (?P<e>{E}), what is the (?P<a>{L})\?"),
        ("compare", rf"Is the (?P<a>{L}) of (?P<x>{E}) (?P<op>{O}) than the (?P=a) of (?P<y>{E})\?"),
        ("compare", rf"Does (?P<x>{E}) have a (?P<op>{O}) (?P<a>{L}) than (?P<y>{E})\?"),
        ("compare", rf"Which has the (?P<op>{O}) (?P<a>{L}): (?P<x>{E}) or (?P<y>{E})\?"),
        ("compare", rf"Compare (?P<x>{E}) and (?P<y>{E}): which one has the (?P<op>{O}) (?P<a>{L})\?"),
        ("compare_rel", rf"Is the (?P<a>{L}) of (?P<x>{E}) (?P<op>{O}) than the (?P=a) of the (?P<r>{P}) of (?P<y>{E})\?"),
        ("compare_rel", rf"Does (?P<x>{E}) have a (?P<op>{O}) (?P<a>{L}) than the (?P<r>{P}) of (?P<y>{E})\?"),
        ("compare_rel", rf"Which is (?P<op>{O}): the (?P<a>{L}) of (?P<x>{E}) or the (?P=a) of the (?P<r>{P}) of (?P<y>{E})\?"),
        ("compare_rel", rf"Compare the (?P<a>{L}) of (?P<x>{E}) with the (?P=a) of the (?P<r>{P}) of (?P<y>{E}): which is (?P<op>{O})\?"),
        ("compare_parent", rf"Is the (?P<a>{L}) of (?P<x>{E}) (?P<op>{O}) than the (?P=a) of its (?P<r>{P})\?"),
        ("compare_parent", rf"Does (?P<x>{E}) have a (?P<op>{O}) (?P<a>{L}) than its (?P<r>{P})\?"),
        ("compare_parent", rf"Which is (?P<op>{O}): the (?P<a>{L}) of (?P<x>{E}) or the (?P=a) of its (?P<r>{P})\?"),
        ("compare_parent", rf"Compare (?P<x>{E}) with its (?P<r>{P}): which has the (?P<op>{O}) (?P<a>{L})\?"),
        ("compare_chain2", rf"Is the (?P<a>{L}) of (?P<x>{E}) (?P<op>{O}) than the (?P=a) of the (?P<r>{P}) of the (?P=r) of (?P<y>{E})\?"),
        ("compare_chain2", rf"Does (?P<x>{E}) have a (?P<op>{O}) (?P<a>{L}) than the (?P<r>{P}) of the (?P=r) of (?P<y>{E})\?"),
        ("compare_chain2", rf"Which is (?P<op>{O}): the (?P<a>{L}) of (?P<x>{E}) or the (?P=a) of the (?P<r>{P}) of the (?P=r) of (?P<y>{E})\?"),
        ("compare_chain2", rf"Compare the (?P<a>{L}) of (?P<x>{E}) with the (?P=a) of the (?P<r>{P}) of the (?P=r) of (?P<y>{E}): which is (?P<op>{O})\?"),
        ("rev_lookup", rf"What is the (?P<a>{L}) of the only subsidiary of (?P<e>{E}) that the table lists\?"),
        ("rev_lookup", rf"Find the one listed subsidiary of (?P<e>{E}) and state its (?P<a>{L})\."),
        ("rev_lookup", rf"Give the (?P<a>{L}) of the only subsidiary listed for (?P<e>{E})\."),
        ("rev_lookup", rf"For the only listed subsidiary of (?P<e>{E}), what is the (?P<a>{L})\?"),
        ("agg_subs", rf"What is the combined (?P<a>{L}) of the listed subsidiaries of (?P<e>{E})\?"),
        ("agg_subs", rf"Add up the (?P<a>{L}) of every subsidiary of (?P<e>{E}) that the table lists\."),
        ("agg_subs", rf"Give the total (?P<a>{L}) of the subsidiaries of (?P<e>{E}) listed in the table\."),
        ("agg_subs", rf"What do the listed subsidiaries of (?P<e>{E}) have as a combined (?P<a>{L})\?"),
    ]


Q_PATTERNS2 = _q_patterns2()


def parse_table_v2(lines):
    rows = []
    for line in lines:
        for pat in ROW_PATTERNS:
            m = re.fullmatch(pat, line)
            if m:
                e, a, v = m.groups()
                if (e, a) != ("Entity", "Attribute"):
                    rows.append((e, a, v))
                break
        else:
            assert line in TABLE_HEADERS, f"table line not parsed: {line!r}"
    return rows


def check_v2(item):
    """the answer (True / False) recomputed from the rendered state alone: the four rules of reading, the rows, the question"""
    st = item["state"]
    lines = st["facts"].split("\n")
    seen, used = {}, {}
    for ln in lines[:4]:
        hits = [(c, m.groupdict()) for c, pats in RULE_RX2.items() for p in pats for m in [re.fullmatch(p, ln)] if m]
        assert len(hits) == 1 and hits[0][0] not in seen, f"rule line not parsed: {ln!r}"
        seen[hits[0][0]] = ln
        used.update(hits[0][1])
    assert set(seen) == set(RULE_KEYS), set(seen)
    tbl = {}
    for e, a, v in parse_table_v2(lines[4:]):
        assert (e, a) not in tbl, f"duplicate row {e} {a}"
        tbl[(e, a)] = v
    plabels = {lab for (_, lab) in tbl if lab in PARENT_LABELS}
    assert plabels <= {used["p"]}, (plabels, used)                 # the rule names the label of the link rows
    if "ra" in used:
        assert used["ra"].split(" ", 1)[1] == used["r"], used       # the article agrees with the region label of the rule
    hits = [(f, m.groupdict()) for f, pat in Q_PATTERNS2 for m in [re.fullmatch(pat, st["question"])] if m]
    assert len(hits) == 1, f"question parsed {len(hits)} times: {st['question']}"
    f, g = hits[0]
    has, get = (lambda e, a: (e, a) in tbl), (lambda e, a: tbl.get((e, a)))
    link = used["p"]
    if f == "lookup":                                              # only a region can be asked for like this: from its own row or from the parent's
        assert g["a"] == used["r"], "a plain look-up of something that is not the region is not generated in v2"
        if has(g["e"], g["a"]):
            return True
        p = get(g["e"], link)
        return p is not None and has(p, g["a"])
    region = lambda t: t is not None and (has(t, used["r"]) or (get(t, link) is not None and has(get(t, link), used["r"])))   # own row, or the parent's own row
    if f == "rel_lookup":
        p = get(g["e"], g["r"])
        if g["a"] == used["r"]:
            return region(p)
        return p is not None and has(p, g["a"])
    if f == "compare":
        return has(g["x"], g["a"]) and has(g["y"], g["a"])
    if f in ("compare_rel", "compare_parent"):
        owner = g["y"] if f == "compare_rel" else g["x"]
        p = get(owner, g["r"])
        return has(g["x"], g["a"]) and p is not None and has(p, g["a"])
    if f == "chain2":
        p = get(g["e"], g["r"])
        p2 = get(p, g["r"]) if p is not None else None
        if g["a"] == used["r"]:
            return region(p2)
        return p2 is not None and has(p2, g["a"])
    if f == "chain3":
        p = get(g["e"], g["r"])
        p2 = get(p, g["r"]) if p is not None else None
        p3 = get(p2, g["r"]) if p2 is not None else None
        return p3 is not None and has(p3, g["a"])
    if f == "compare_chain2":
        p = get(g["y"], g["r"])
        p2 = get(p, g["r"]) if p is not None else None
        return has(g["x"], g["a"]) and p2 is not None and has(p2, g["a"])
    subs = [e for (e, lab), v in tbl.items() if lab == link and v == g["e"]]          # the listed subsidiaries: their own link row names the organisation
    if f == "rev_lookup":
        return len(subs) == 1 and has(subs[0], g["a"])
    return len(subs) >= 1 and all(has(s, g["a"]) for s in subs)


# ------------------------------------------------------------------------------------------------------- one pair (v2)
def valid_pair_v2(world, q, pos_rows, neg_rows, forbidden, removed):
    keys = lambda rows: {(r[0], r[1]) for r in rows}
    if keys(pos_rows) & forbidden or keys(neg_rows) & forbidden:
        return False
    if "subs" in q:                                                 # exactly the chosen subsidiaries name the organisation as parent (in the negative
        for rows, gone in ((pos_rows, None), (neg_rows, removed)):  # without the one whose link row was taken away)
            want = [s for s in q["subs"] if not (gone and gone[1] == "parent" and gone[0] == s)]
            if sorted(r[0] for r in rows if r[1] == "parent" and r[2] == q["e"]) != sorted(want):
                return False
    return truth_v2({"q": q, "rows": pos_rows}) and not truth_v2({"q": q, "rows": neg_rows})


def make_pair_v2(i, plan):
    """-> (positive spec, negative spec, info); retries with fresh random draws until the pair is valid"""
    for attempt in range(1000):
        rng = rng_for("v2-pair", i, attempt)
        n_rows = plan["rows"]
        try:
            world = make_world_v2(rng, N_ENT2[n_rows])
            q = make_question_v2(rng, world, plan["form"])
            forbidden = forbidden_v2(world, q)
            rows, layout, order, structural = build_rows_v2(rng, world, q, n_rows, forbidden)
        except (RuntimeError, IndexError, ValueError, AssertionError):
            continue
        needs = needs_of_v2(world, q)
        removable = [k for k, n in enumerate(needs) if n[2] not in UNREMOVABLE.get(q["form"], ())]
        if plan["miss"]:                                             # region forms (gen_v4): the missing row is the parent's region row ("value") or a link row, half and half
            removable = [k for k in removable if (needs[k][2] == "value") == (plan["miss"] == "value")]
        j = rng.choice(removable)
        removed = next(r for r in rows if (r[0], r[1]) == (needs[j][0], needs[j][1]))
        dec = decoy_row_v2(rng, world, rows, removed, plan["dev"], forbidden)
        if dec is None:
            continue
        neg_rows = [dec if r == removed else r for r in rows]
        protected = {n[0] for n in needs} | set(named_entities_v2(q)) | {dec[0]} | set(q.get("subs", ()))
        comp = compensate_v2(rng, world, neg_rows, dec, removed, plan["dev"], protected, structural, forbidden)
        if comp is None:
            continue
        neg_rows, old_row, new_row = comp
        if layout == "grouped":                                      # the changed rows take their natural place
            neg_rows.sort(key=lambda k: (order.index(k[0]), ATTRS2.index(k[1])))
        if not valid_pair_v2(world, q, rows, neg_rows, forbidden, removed):
            continue
        labels = {a: rng.choice(LABELS2[a]) for a in ATTRS2}
        look = {"labels": labels, "style": rng.randrange(4), "frame": rng.randrange(4),
                "phr": {k: rng.randrange(4) for k in RULE_KEYS}, "rule_order": rng.sample(RULE_KEYS, 4)}
        base = {"q": q, "layout": layout, **look}
        return ({**base, "rows": rows}, {**base, "rows": neg_rows},
                {"level": plan["level"], "role": needs[j][2], "removed": list(removed), "decoy": list(dec), "needs": [list(n) for n in needs],
                 "compensation": [list(old_row), list(new_row)], "near_miss": sorted(list(k) for k in structural)[:0]})
    raise RuntimeError(f"pair {i}: no valid draw")


def to_item_v2(n, pair, spec, info, dev):
    st = {"facts": render_facts_v2(spec["rows"], spec["labels"], spec["style"], spec["phr"], spec["rule_order"]),
          "question": render_question_v2(spec["q"], spec["labels"], spec["frame"])}
    q = spec["q"]
    return {"id": f"{TASK}:{n:05d}", "state": st,
            "questions": {"q": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": dict(OPTIONS)}},
            "gold": "yes" if dev is None else "no", "soft": None, "group": f"{TASK}:pair:{pair:03d}",
            "meta": {"source_id": f"{n:05d}", "pair": pair, "level": info["level"], "hops": HOPS2[q["form"]], "rows": len(spec["rows"]),
                     "form": q["form"], "deviation": dev or "none", "missing_role": info["role"] if dev else None,
                     "table_layout": spec["layout"], "table_style": spec["style"],
                     "spec": {"q": q, "rows": [list(r) for r in spec["rows"]], "labels": spec["labels"],
                              "needs": info["needs"], "removed": info["removed"] if dev else None,
                              "decoy": info["decoy"] if dev else None,
                              "compensation": info["compensation"] if dev else None}}}


def make_plan_v2():
    """300 pairs on the level ladder: 100 pairs per level (level 1 = hops 2 on 20 rows, 2 = hops 3 on 40 rows, 3 = hops 4 on 80 rows);
    per level the four forms 20 / 20 / 20 / 40 pairs (the region form 40, see FORM_PAIRS); inside every form the two deviation kinds
    half and half (so 50 / 50 per level); inside the region form the missing row is the parent's region row in half of the pairs
    and a link row in the other half, for either kind"""
    rng = rng_for("v2-plan")
    plan = []
    for level, (h, r) in LEVELS.items():
        cells = []
        for f in FORMS_BY_HOPS2[h]:
            n = FORM_PAIRS[f]
            if f in REGION_FORMS:
                combos = [(d, m) for d in ("other_entity", "other_attribute") for m in ("value", "link")]
            else:
                combos = [(d, None) for d in ("other_entity", "other_attribute")]
            lst = [c for c in combos for _ in range(n // len(combos))]
            assert len(lst) == n
            rng.shuffle(lst)
            cells += [(f, d, m) for d, m in lst]
        assert len(cells) == 100, (level, len(cells))
        rng.shuffle(cells)
        plan += [{"level": level, "hops": h, "rows": r, "form": f, "dev": d, "miss": m} for f, d, m in cells]
    rng.shuffle(plan)
    return plan


def main_v2():
    plan = make_plan_v2()
    items = []
    for i, p in enumerate(plan):
        pos, neg, info = make_pair_v2(i, p)
        e0, a0, _ = info["removed"]                                  # the asked organisation and attribute keep their row counts
        cnt = lambda rows: (sum(r[0] == e0 for r in rows), sum(r[1] == a0 for r in rows))
        assert cnt(pos["rows"]) == cnt(neg["rows"]), (i, cnt(pos["rows"]), cnt(neg["rows"]))
        assert len(set(pos["rows"]) - set(neg["rows"])) == 2 and len(pos["rows"]) == len(neg["rows"])   # needed row + one neutral row
        items.append((i, pos, info, None))
        items.append((i, neg, info, p["dev"]))
    rng_for("order").shuffle(items)
    rows = []
    for n, (pair, spec, info, dev) in enumerate(items, 1):
        it = to_item_v2(n, pair, spec, info, dev)
        q = spec["q"]
        # ---- truth twice
        assert truth_v2(spec) == (dev is None), f"{it['id']}: truth {truth_v2(spec)} but planted deviation {dev}"
        assert check_v2(it) == truth_v2(spec), f"{it['id']}: check {check_v2(it)} != truth {truth_v2(spec)}"
        assert (it["gold"] == "yes") == check_v2(it)
        # ---- exactly one needed fact affected
        tbl = {(e, a) for e, a, _ in spec["rows"]}
        missing = [k for k in info["needs"] if (k[0], k[1]) not in tbl]
        assert len(missing) == (0 if dev is None else 1), (it["id"], missing)
        assert len(spec["rows"]) == it["meta"]["rows"] in ROWS2
        assert len(parse_table_v2(it["state"]["facts"].split("\n")[4:])) == len(spec["rows"])
        text = it["state"]["facts"]
        for e in named_entities_v2(q):
            assert e in text, f"{it['id']}: {e} not mentioned any more"
        if q["form"] in INHERIT_DEPTH:                               # the organisation whose region is asked takes it over: it has no region row of its own,
            asked = info["needs"][INHERIT_DEPTH[q["form"]]][0]       # and the organisation it takes it from is the last (value) row of the needs
            assert (asked, "region") not in tbl and info["needs"][-1][1:] == ["region", "value"], (it["id"], asked)
        if dev:
            e0, a0, _ = info["removed"]
            e1, a1, _ = info["decoy"]
            assert (e1 != e0 and a1 == a0) if dev == "other_entity" else (e1 == e0 and a1 != a0), (it["id"], dev)
            assert (e1, a1) not in {(r[0], r[1]) for r in spec["rows"] if list(r) != info["decoy"]}
        it["_class"] = it["gold"]
        rows.append(it)
    rows.sort(key=lambda r: r["id"])
    assign_orders(rows)
    # ---- balance and dials (gen_v4: the level ladder)
    cls = collections.Counter(r["gold"] for r in rows)
    assert cls == {"yes": 300, "no": 300}, cls
    by = lambda key: collections.Counter(r["meta"][key] for r in rows)
    assert dict(by("level")) == {1: 200, 2: 200, 3: 200}, by("level")
    assert all((r["meta"]["hops"], r["meta"]["rows"]) == LEVELS[r["meta"]["level"]] for r in rows)
    assert set(by("hops").values()) == {200} and set(by("rows").values()) == {200}, (by("hops"), by("rows"))
    assert set(by("hops")) == {2, 3, 4} and set(by("rows")) == set(ROWS2)
    per = collections.Counter((r["meta"]["level"], r["gold"], r["meta"]["deviation"]) for r in rows)
    for lv in LEVELS:                                                # classes, deviation kinds and option positions are exactly balanced inside every level
        assert per[(lv, "yes", "none")] == 100 and per[(lv, "no", "other_entity")] == 50 and per[(lv, "no", "other_attribute")] == 50, (lv, per)
        for g in ("yes", "no"):
            first = sum(1 for r in rows if r["meta"]["level"] == lv and r["gold"] == g and r["meta"]["order"][0] == "yes")
            assert first == 50, (lv, g, first)
    for f in FORMS2:                                                 # pairs per form and the two kinds inside every form
        assert sum(1 for r in rows if r["meta"]["form"] == f and r["gold"] == "yes") == FORM_PAIRS[f], f
        assert {k: sum(1 for r in rows if r["meta"]["form"] == f and r["meta"]["deviation"] == k) for k in ("other_entity", "other_attribute")} \
            == {"other_entity": FORM_PAIRS[f] // 2, "other_attribute": FORM_PAIRS[f] // 2}, f
    dev = collections.Counter(r["meta"]["deviation"] for r in rows)
    assert dev["other_entity"] == dev["other_attribute"] == 150, dev
    # ---- founding years: in range, never clamped, a subsidiary later than its parent
    years = [int(v) for r in rows for e, a, v in r["meta"]["spec"]["rows"] if a == "founded"]
    assert YEAR_LO <= min(years) and max(years) <= YEAR_HI, (min(years), max(years))
    year_top = years.count(max(years)) / len(years)
    assert year_top < 0.02, f"founding years pile up at {max(years)}: {year_top:.3f}"
    for r in rows:
        t = {(e, a): v for e, a, v in r["meta"]["spec"]["rows"]}
        for (e, a), v in t.items():
            if a == "parent" and (e, "founded") in t and (v, "founded") in t:
                assert int(t[(e, "founded")]) > int(t[(v, "founded")]), (r["id"], e, v)
    ystat = {"n": len(years), "lo": min(years), "hi": max(years), "distinct": len(set(years)), "top": year_top,
             "share_2022": years.count(2022) / len(years)}
    fig = {}                                                         # the other two figures: range of the listed values (they were never clamped)
    for a in ("staff", "sites"):
        v = [int(x) for r in rows for e, aa, x in r["meta"]["spec"]["rows"] if aa == a]
        fig[a] = (min(v), max(v))
    # ---- questions that need the region taken over from the parent (rule 4), per level; the missing row of their negatives
    region = {lv: sum(1 for r in rows if r["meta"]["level"] == lv and r["meta"]["form"] in REGION_FORMS) / 200 for lv in LEVELS}
    reg_neg = [r for r in rows if r["gold"] == "no" and r["meta"]["form"] in REGION_FORMS]
    reg_parent_row = sum(1 for r in reg_neg if r["meta"]["missing_role"] == "value") / len(reg_neg)
    assert all(abs(v - 0.4) < 1e-9 for v in region.values()), region
    for f in REGION_FORMS:                                           # exactly half of the negatives of a region form miss the parent's region row
        roles_f = collections.Counter(r["meta"]["missing_role"] == "value" for r in rows if r["gold"] == "no" and r["meta"]["form"] == f)
        assert roles_f[True] == roles_f[False] == FORM_PAIRS[f] // 2, (f, roles_f)
    look_alike = sum(1 for r in rows if r["meta"]["deviation"] == "other_entity"
                     and stem_of(r["meta"]["spec"]["decoy"][0]) == stem_of(r["meta"]["spec"]["removed"][0]))
    tested, worst = vocabulary_test(rows, ["yes", "no"])
    lengths = [len(state_text(r)) for r in rows]
    for r in rows:
        del r["_class"]
    d = f"{HERE}/tasks/{TASK}"
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/items.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(rows, key=lambda r: r["id"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    task = {"task": TASK, "layer": "A", "title": "Generated facts tables: can the question be answered from the facts listed?",
            "decision": "whether a question can be answered from the facts of a table under the rules of reading written above it (yes) or at least one fact it needs is not listed (no)",
            "source": {"name": f"generator build/gen_{TASK}.py", "url": "", "files": [], "split": "generated, seed 20261007, DIFFICULTY v2",
                       "version": "gen_v4, 2026-10-08: founding years drawn from 1880-2024 without a clamp at 2022, level ladder meta.level 1 / 2 / 3 "
                                  "(hops 2 / 3 / 4 on 20 / 40 / 80 rows, 200 items each), 40 % region-inheritance questions on every level; "
                                  "DIFFICULTY = \"v1\" regenerates the first version"},
            "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
            "labels": "programmatic", "item_source": "generated", "metric": "accuracy", "chance": 0.5, "rows": len(rows),
            "groups": PAIRS, "question_type": "choice", "options": 2,
            "notes": ("Version v2 (harder than the first version, which is regenerated with DIFFICULTY = \"v1\"). 600 items = 300 contrast pairs (meta.pair, group): "
                      "a facts table with a question (yes) and the same table in which one needed row is replaced by another attribute of the same organisation "
                      "or the same attribute of a look-alike organisation (no); the asked organisation and attribute keep their number of rows (one neutral filler "
                      "row is changed as well). The first four lines of the state are the rules of reading (closed world, links only where a parent row says so, "
                      "every figure needs its own row, one fact - the region - is inherited from the parent). Levels (meta.level, 200 items each): "
                      "1 = hops 2 on 20 rows, 2 = hops 3 on 40 rows, 3 = hops 4 on 80 rows (hops = rows the question needs, includes a total over the listed "
                      "subsidiaries and a region taken over from the parent; rows 20 / 40 / 80 = 8 / 14 / 26 organisations of 2 to 4 families, a near-miss row for "
                      f"every needed row). gen_v4 fixes: founding years are drawn from {YEAR_LO}-{YEAR_HI} (a subsidiary {GAP[0]} to {GAP[1]} years after its parent) instead of being "
                      "clamped at 2022, the nine hops x rows cells are replaced by the level ladder, and 40 of the 100 pairs of every level need the region taken "
                      "over from the parent (rule 4). The metric is item accuracy; the group allows a pair analysis. Everything is invented and "
                      "every answer is computed twice (specification and a parser of the rendered text). State length %d to %d characters (median %d)."
                      % (min(lengths), max(lengths), sorted(lengths)[300]))}
    json.dump(task, open(f"{d}/task.json", "w"), indent=1)
    val = run_tool("validate.py", TASK)
    aud = run_tool("audit.py", TASK)
    print(val[1] if len(val) > 1 else val)
    print(aud[0])
    print(aud[1] if len(aud) > 1 else aud)
    sys.dont_write_bytecode = True
    sys.path.insert(0, AUDITS)
    import audit
    audit.HERE = HERE                       # the audit reads HERE/tasks/<family>/
    a = audit.audit(TASK)
    assert not a["flag"] and a["length"] < 0.55, a
    stats = {"year": ystat, "region": region, "reg_parent_row": reg_parent_row, "fig": fig}
    write_readme_v2(d, rows, dev, lengths, val, aud, tested, worst, look_alike, stats)
    print("vocabulary test:", tested, "tokens with frequency >= 20, worst ratio %.2f (%s)" % worst)
    print("counts per class", dict(cls), "| level", dict(by("level")), "| hops", dict(by("hops")), "| rows", dict(by("rows")), "| deviation", dict(dev))
    print("form (per class)", dict(collections.Counter(r["meta"]["form"] for r in rows if r["gold"] == "yes")))
    print("founding years: %d facts, %d..%d, %d distinct, %.2f %% equal to the maximum, %.2f %% equal to 2022" % (
        ystat["n"], ystat["lo"], ystat["hi"], ystat["distinct"], 100 * ystat["top"], 100 * ystat["share_2022"]))
    print("region questions per level:", {lv: f"{100 * v:.0f} %" for lv, v in region.items()}, "| negatives of region forms that miss the parent's region row: %.0f %%" % (100 * reg_parent_row))
    print("other_entity decoys from the same family:", look_alike, "of", dev["other_entity"])
    print("state length", min(lengths), max(lengths), "median", sorted(lengths)[300])


def write_readme_v2(d, rows, dev, lengths, val, aud, tested, worst, look_alike, stats):
    yes_of = lambda f: sum(1 for r in rows if r["meta"]["form"] == f and r["gold"] == "yes")
    forms = ", ".join(f"`{f}` {yes_of(f)}" for f in FORMS2)
    roles = collections.Counter(r["meta"]["missing_role"] for r in rows if r["gold"] == "no")
    roles = ", ".join(f"`{k}` {v}" for k, v in sorted(roles.items()))
    by_h = lambda h: ", ".join(f"`{f}` {yes_of(f)}" for f in FORMS_BY_HOPS2[h])
    pick = lambda level, form, gold, role=None: next(
        x for x in sorted(rows, key=lambda x: x["id"])
        if x["meta"]["level"] == level and x["meta"]["form"] == form and x["gold"] == gold and (role is None or x["meta"]["missing_role"] == role))
    ex = [pick(1, "inherit", "yes"), pick(2, "inherit_rel", "no", "value"), pick(3, "agg_subs", "no")]
    ys, reg = stats["year"], stats["region"]
    lens = {lv: sorted(len(state_text(r)) for r in rows if r["meta"]["level"] == lv) for lv in LEVELS}
    ladder = "\n".join(f"| {lv} | {h} | {n} | {N_ENT2[n]} ({ {8: 2, 14: 3, 26: 4}[N_ENT2[n]] }) | {NEAR2[n]} | 200 (100 yes, 100 no) | {lens[lv][0]} to {lens[lv][-1]} (median {lens[lv][100]}) | {100 * reg[lv]:.0f} % |"
                       for lv, (h, n) in LEVELS.items())
    reg_neg = sum(1 for r in rows if r["gold"] == "no" and r["meta"]["form"] in REGION_FORMS)
    txt = f"""# {TASK}

Generated facts tables: can the question be answered from the facts listed? (layer A, generated, programmatic truth; version v2, revised in gen_v4 on 2026-10-08)

- Decision: whether a question can be answered from the facts of a table under the rules of reading written above it (yes) or at least one fact it needs is not listed (no).
- Source: generator `build/gen_{TASK}.py` (standard library only, `random.Random(20261007)` and sub-generators; the output is identical on every run); no third-party text.
- Version: this directory holds **v2** (the harder dials) as revised in gen_v4: founding years are drawn from a wide range instead of being clamped at 2022, the nine hops x rows cells are replaced by a three-level ladder (`meta.level`), and 40 % of the questions of every level need the region taken over from the parent. The first version (hops 1 / 2 / 3 on 10 / 20 / 40 rows, hosted reference 0.98) is regenerated by setting `DIFFICULTY = "v1"` at the top of the script (or `BENCH_DIFFICULTY=v1`), which rewrites this directory (and brings its clamp back).
- Licence: generated by the benchmark's script (no third-party text); items included.
- Rows: {len(rows)} in {PAIRS} contrast pairs (300 yes, 300 no); metric: accuracy (chance 0.5).
- Rebuild: `python3 build/gen_{TASK}.py`

## What is generated

A table of facts about invented organisations (rows `entity · attribute · value`; attributes: founding year, headquarters, parent organisation, head count,
product line, number of sites, chief executive, operating region; every name is made by a syllable generator) and one question. The organisations form
2 to 4 families (one family name, one head, many suffixes, so most names look alike) with parent links up to three levels deep. The first four lines of the
state are the **rules of reading**, one wording of four for each (chosen per item, in a drawn order): (1) only the rows may be used, a fact without a row is unknown;
(2) organisations are related only where a parent row says so, and a shared family name proves nothing; (3) a comparison or a total needs the figure of every
organisation it covers, and no figure is worked out from other figures; (4) one fact is inherited: an organisation with no region row takes the region of its parent,
if the parent has a region row of its own (one step, nothing else is inherited). The table follows in one of four layouts with one of four label sets.

**Founding years** are drawn from {YEAR_LO}-{YEAR_HI} (listed in the tables: {ys['n']} values, {ys['lo']}-{ys['hi']}, {ys['distinct']} distinct). They are drawn family by family: every subsidiary is founded {GAP[0]} to {GAP[1]} years after its parent
(so the order parent, child holds by construction and is asserted wherever both rows are listed), and the year of the family's head is drawn uniformly from the window in which the
youngest member still fits below {YEAR_HI}. Nothing is clamped: {100 * ys['top']:.2f} % of the listed founding years equal the largest value of the file (the first release of v2 clamped a subsidiary's year to 2022, which made 25 % of all listed founding years exactly 2022).
Head count ({stats['fig']['staff'][0]:,} to {stats['fig']['staff'][1]:,} in the tables; log-uniform, no two organisations of an item alike) and number of sites ({stats['fig']['sites'][0]} to {stats['fig']['sites'][1]}; uniform) were never clamped and are unchanged.

## Levels

The only dial is the **level** (`meta.level`); with it both former dials rise (`meta.hops` = rows the question needs, `meta.rows` = rows of the table). The number of organisations, of families and of near-miss rows per needed row rise with it.

| `meta.level` | `meta.hops` | `meta.rows` | organisations (families) | near-miss rows per needed row | items | state length (characters) | region questions |
|---|---|---|---|---|---|---|---|
{ladder}

Inside every level the classes are exactly 100 / 100, the two deviation kinds 50 / 50 (also inside every form), and exactly half of the positives and half of the negatives list `yes` first (`meta.order`).

Question forms (`meta.form`; per level four forms, 20 pairs each and 40 pairs for the region form):

| level | hops | forms (yes items per form) | what they ask |
|---|---|---|---|
| 1 | 2 | {by_h(2)} | `rel_lookup`: a figure of the parent; `compare`: two figures, often of two look-alikes; `inherit`: the REGION of an organisation that has no region row of its own (the answer is yes when its link row and its parent's region row are both there, rule 4); `rev_lookup`: a figure of the ONE subsidiary of an organisation that the table lists (found through the value column) |
| 2 | 3 | {by_h(3)} | `chain2`: a figure two links up; `compare_rel`, `compare_parent`: a comparison with a figure reached through a link; `inherit_rel`: the region of the parent, which has no region row and takes the one of its own parent |
| 3 | 4 | {by_h(4)} | `chain3`: a figure three links up; `compare_chain2`: a comparison through two links; `agg_subs`: the combined head count (or number of sites) of the two subsidiaries whose own parent row names the asked organisation - both figures are needed, and a look-alike or a grandchild is not a subsidiary; `inherit_chain2`: the region two links up, taken over from its parent |

**Rule 4 is needed.** Every state carries the region rule, and {100 * reg[1]:.0f} % of the questions of every level are region questions (`inherit`, `inherit_rel`, `inherit_chain2`; in the first release it was one question in four). In all of them the
organisation whose region is asked has no region row of its own, in either member of a pair, so the answer rests on the rule: yes when the link rows and the parent's own region row are listed,
no when one of them is not. In {100 * stats['reg_parent_row']:.0f} % of the {reg_neg} negatives of these forms the missing row is the parent's region row (the parent has other rows, or the region row of a look-alike, but none of its own region): the case the rule says
"provided the parent has a region row of its own" about; in the others a link row is missing.

**Near misses.** For every needed row the base table holds the same attribute of one to three look-alike siblings (same family name; 1 / 2 / 3 at 20 / 40 / 80 rows) and one more look-alike row is kept back for the decoy, the asked organisation has at least one
more row, and where it exists a child row that names the asked organisation as its parent (a link that points the other way). The deviation then replaces a needed row
by the same attribute of another look-alike (`other_entity`: {look_alike} of {dev['other_entity']} from the same family) or by another attribute of the same organisation (`other_attribute`).
In the three region forms the table never has a region row for the organisation whose region is asked, in either member of a pair; in `agg_subs`
and `rev_lookup` items exactly the chosen subsidiaries have a parent row that names the asked organisation (in the negative of a `rev_lookup` pair without the one whose link row was removed), and no other
child of the organisation has its parent row in the table (`agg_subs` never removes a link row: that would only change which organisations are totalled).
The order of the two options is drawn per item (`meta.order`).

**Pairs.** The positive and the negative of a pair share the table except two rows: the negative replaces one row the question needs (`meta.missing_role` says which: a link, a
figure, one side of a comparison, one of the subsidiaries' figures) and one neutral filler row is changed so that the asked organisation (other_entity) or the asked attribute (other_attribute)
has the same number of rows as in the positive (`meta.spec.compensation`). The table keeps its size and still mentions every organisation of the question. In the grouped layout the changed rows
take their natural place. Length, vocabulary and structure of the two classes are therefore the same by construction.

## Deviation kinds (negatives)

| `meta.deviation` | items |
|---|---|
| `other_entity` | {dev['other_entity']} |
| `other_attribute` | {dev['other_attribute']} |

Question forms (yes items = pairs per form): {forms}. Missing fact (`meta.missing_role`, negatives): {roles}.

## Checks made by the script

- `truth_v2(spec)` (structured question over the structured table, with the rules of reading) and `check_v2(item)` (parses the rendered rules, rows and question) agree on all 600 items.
- Every planted deviation turns the answer from yes to no and exactly one needed row is missing; the table has the same number of rows; every organisation named in the question is still mentioned;
  the asked organisation and the asked attribute have the same number of rows in both members of a pair; no forbidden row (a region row of the inheriting organisation; the parent row of a third subsidiary) is in either table.
- Classes are exactly balanced; every level has exactly 200 items (hops and rows follow the level), and inside every level the classes, the deviation kinds and the option positions are balanced exactly; every form has its pairs (20 / 40) with the two kinds half and half.
- Founding years lie in {YEAR_LO}-{YEAR_HI}, fewer than 2 % of them equal the largest value, and a subsidiary is later than its parent wherever both rows are listed.
- Vocabulary test: {tested} tokens of frequency >= 20 are tested; none occurs in one class at more than twice the rate of the other (largest ratio {worst[0]:.2f}, `{worst[1]}`).
- Shortcut audit (`python3 audit.py {TASK}`), best length rule below 0.55:

```
{aud[0]}
{aud[1]}
```

Validator: `{val[1].strip() if len(val) > 1 else val}`

## Examples (one per level)

""" + "\n\n".join(f"### level = {x['meta']['level']}, hops = {x['meta']['hops']}, rows = {x['meta']['rows']}, form `{x['meta']['form']}`\n\n" + fmt_item(x) for x in ex) + """

## Independence from training generators

The items are disjoint from any training generator of the authors by construction: this is a new generator, written for the benchmark;
names, templates and fact tables share nothing with the generators used for training.
"""
    open(f"{d}/README.md", "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    (main_v2 if DIFFICULTY == "v2" else main_v1)()
