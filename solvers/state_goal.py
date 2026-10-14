"""Independent solver for `state_goal` (second author of the gen_v4 label audit).

Reads only the rendered text: the initial file store (four layouts), the five step definitions (four phrasings each),
the goal conditions (four headers, many wordings, five kinds of condition) and the numbered trace (four notations x four
numberings).  It replays the trace twice - once on a nested folder tree, once on a flat path table - and answers
`yes` only if every goal condition holds on the final store.

Everything it does not recognise raises `Unreadable`; so does a trace that contradicts the preamble of the state
(a step whose source file is missing, a step that leaves the store unchanged).

Conventions the text does not spell out (kept in `DIAG`, see `analyze`): a content / same-content condition on a file
that does not exist is taken as false; the argument order of the compact notations `copy A B`, `rename A B`, `move A F`,
`set P W` is taken as source/destination, old/new name, file/folder, path/content.
"""
import json
import posixpath
import re


class Unreadable(ValueError):
    pass


def _fail(msg):
    raise Unreadable(msg)


# ----------------------------------------------------------------------------------------------- fixed texts
LEADS = (
    "A small file store was edited step by step by an agent; the trace shows every step.",
    "Below are the starting files of a small file store, the goal an agent was given, and the steps it ran.",
    "The trace below lists the steps that an agent ran on a small file store.",
    "An agent changed a small file store by running the steps of the trace below.",
)
DOMAIN = re.compile(r"^The store holds the [a-z ,]+ of an? [a-z ]+\.$")
# preamble sentences -> claims about the steps
#   ran = no step failed, src = the source of delete/rename/copy/move was in the store, set = set creates or replaces,
#   chg = every step changed the store
PREAMBLE = {
    "All steps ran.": {"ran"},
    "The source file of every delete, rename, copy and move was in the store when the step started, a set writes "
    "its file whether or not it exists yet, and each step changed the store.": {"src", "set", "chg"},
    "No step failed: deletes, renames, copies and moves always found their source file, sets create or overwrite "
    "their file, and every step made the store different from before.": {"ran", "src", "set", "chg"},
    "Every delete, rename, copy and move found its source file; set creates the file or replaces its content; "
    "every step changed the store.": {"src", "set", "chg"},
    "Each delete, rename, copy and move was run on a file that existed at that moment, a set either creates its "
    "file or overwrites its content, and no step left the store as it was.": {"src", "set", "chg"},
}
FILE_HEADERS = (
    "Files at the start, with their content:",
    "At the start the store holds these files and contents:",
    "Initial content of the store:",
    "Store before the first step (one file per line, with its content):",
)
SEM_HEADERS = (
    "How each kind of step works:",
    "Meaning of the steps (arguments in the order given in the trace):",
    "Step semantics:",
    "What the steps do:",
)
GOAL_HEADERS = (
    "After the last step the store has to satisfy every one of these conditions; file counts ignore sub-folders:",
    "Goal conditions, to be true after the final step; a count only includes files directly in the named folder:",
    "The agent was asked to reach these conditions, and every one of them must hold after the last step "
    "(file counts refer to the files directly inside a folder, not those in sub-folders):",
    "Goal (all conditions must hold after the last step; a folder's file count includes only the files directly "
    "inside it):",
)
TRACE_HEADERS = (
    "Operations, first to last:",
    "Trace:",
    "Log of the agent's steps:",
    "Steps run by the agent, in order:",
)
# every phrasing of the five definitions; all four phrasings of an operation say the same thing:
#   set: create or replace content | delete: remove | rename: new name in the same folder, a file with the new name is
#   replaced | copy: destination gets the content (replacing), source stays | move: file goes into the folder under the
#   same name, a file there is replaced, old path gone
SEMANTICS = {
    "set": (
        "writes the content to the path; the file is created if it is missing and its content is replaced if it exists.",
        "puts the content into the file at the path, whether or not the file exists yet; an existing file loses its old content.",
        "the file at the path gets the given content (a new file if there was none, otherwise the old content is overwritten).",
        "stores the given content under the path, creating the file or replacing the content of the existing one.",
    ),
    "delete": (
        "removes the file at the path.",
        "erases the file at the path from the store.",
        "takes the file at the path out of the store.",
        "the file at the path is gone afterwards.",
    ),
    "rename": (
        "gives the file a new name inside its folder; if a file with that name is already there it is replaced.",
        "the file keeps its folder and content and takes the new name; an existing file of that name is lost.",
        "changes the file's name but not its folder; a file already holding the new name is overwritten.",
        "new name, same folder; when the new name is taken, the other file is replaced.",
    ),
    "copy": (
        "duplicates the source file to the destination, overwriting a file that is there; the source remains.",
        "writes the content of the source file to the destination path; a file already at the destination is replaced and the source stays.",
        "the destination path receives the source's content (replacing any file there); the source is not changed.",
        "creates or overwrites the destination with the content of the source, which stays in place.",
    ),
    "move": (
        "puts the file into the target folder under the same name; a file of that name in the folder is replaced, and the old path is gone.",
        "relocates the file to the folder, keeping its file name; an existing file with that name in the folder is overwritten.",
        "the file leaves its folder for the target folder and keeps its name; whatever file had that path there is lost.",
        "transfers the file into the target folder with the same name, replacing a file of that name if present; nothing is left at the old path.",
    ),
}
QUESTION = "After these operations, are all goal conditions satisfied?"

PATH = r"[A-Za-z0-9_][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.-]*)*"
WORD = r"[a-z][a-z0-9]*"
PATH_RE = re.compile("^" + PATH + "$")
WORD_RE = re.compile("^" + WORD + "$")

# ----------------------------------------------------------------------------------------------- file list layouts
FILE_LAYOUTS = (
    ("colon", re.compile(r'^  (' + PATH + r'): (' + WORD + r')$')),
    ("equals", re.compile(r'^  (' + PATH + r') = (' + WORD + r')$')),
    ("paren", re.compile(r'^  (' + PATH + r') \((' + WORD + r')\)$')),
    ("quoted", re.compile(r'^  "(' + PATH + r')": "(' + WORD + r')"$')),
)

# ----------------------------------------------------------------------------------------------- goal wordings
P, W, N = "(" + PATH + ")", "(" + WORD + ")", r"(\d+)"
GOAL_FORMS = (
    ("exists", re.compile("^" + P + " is in the tree$")),
    ("exists", re.compile("^" + P + " exists$")),
    ("exists", re.compile("^the file " + P + " is present$")),
    ("exists", re.compile("^there is a file " + P + "$")),
    ("absent", re.compile("^" + P + " is not in the tree$")),
    ("absent", re.compile("^there is no file " + P + "$")),
    ("absent", re.compile("^" + P + " does not exist$")),
    ("absent", re.compile("^the file " + P + " is absent$")),
    ("content", re.compile("^" + P + " reads " + W + "$")),
    ("content", re.compile("^the content of " + P + " is " + W + "$")),
    ("content", re.compile("^" + P + " contains " + W + "$")),
    ("content", re.compile("^" + P + " holds " + W + "$")),
    ("count", re.compile("^the folder " + P + " has " + N + r" files?$")),
    ("count", re.compile("^folder " + P + " holds " + N + r" files?$")),
    ("count", re.compile("^" + P + " contains exactly " + N + r" files?$")),
    ("count_rev", re.compile("^there are " + N + " files in " + P + "$")),
    ("count_rev", re.compile("^there is " + N + " file in " + P + "$")),
    ("same", re.compile("^the contents of " + P + " and " + P + " match$")),
    ("same", re.compile("^" + P + " and " + P + " are identical in content$")),
    ("same", re.compile("^" + P + " and " + P + " have the same content$")),
    ("same", re.compile("^" + P + " has the same content as " + P + "$")),
)

# ----------------------------------------------------------------------------------------------- trace notations
NUMBERINGS = (
    ("dot", re.compile(r"^  (\d+)\. (.+)$")),
    ("step", re.compile(r"^  step (\d+): (.+)$")),
    ("bracket", re.compile(r"^  \[(\d+)\] (.+)$")),
    ("hash", re.compile(r"^  #(\d+) (.+)$")),
)
JSON_KEYS = {
    "set": ("path", "content"),
    "delete": ("path",),
    "rename": ("path", "new_name"),
    "copy": ("source", "destination"),
    "move": ("path", "folder"),
}


def _forms(templates):
    return tuple((op, re.compile(t)) for op, t in templates)


Q = r'"(' + PATH + r')"'
QW = r'"(' + WORD + r')"'
PROSE = _forms((
    ("set", r"^Set (\S+) to (\S+)\.$"),
    ("delete", r"^Delete (\S+)\.$"),
    ("rename", r"^Rename (\S+) to (\S+)\.$"),
    ("copy", r"^Copy (\S+) to (\S+)\.$"),
    ("move", r"^Move (\S+) into (\S+)\.$"),
))
CALL = _forms((
    ("set", r"^set\(" + Q + ", " + QW + r"\)$"),
    ("delete", r"^delete\(" + Q + r"\)$"),
    ("rename", r"^rename\(" + Q + ", " + Q + r"\)$"),
    ("copy", r"^copy\(" + Q + ", " + Q + r"\)$"),
    ("move", r"^move\(" + Q + ", " + Q + r"\)$"),
))
SHELL = _forms((
    ("set", r"^set (\S+) (\S+)$"),
    ("delete", r"^delete (\S+)$"),
    ("rename", r"^rename (\S+) (\S+)$"),
    ("copy", r"^copy (\S+) (\S+)$"),
    ("move", r"^move (\S+) (\S+)$"),
))
NOTATIONS = (("prose", PROSE), ("call", CALL), ("shell", SHELL))

DIAG = {}      # filled by `analyze`; conventions the text leaves open


# ================================================================================================== parsing
def _section(paras, k, headers, what):
    lines = paras[k].split("\n")
    if lines[0] not in headers:
        _fail("unknown %s header: %r" % (what, lines[0][:60]))
    return lines[1:]


def parse_intro(text):
    sents = re.split(r"(?<=\.)\s+", text)
    if sents[0] not in LEADS:
        _fail("unknown lead sentence")
    if not DOMAIN.match(sents[1]):
        _fail("unknown domain sentence: %r" % sents[1][:60])
    claims = set()
    for s in sents[2:]:
        if s not in PREAMBLE:
            _fail("unknown preamble sentence: %r" % s[:60])
        claims |= PREAMBLE[s]
    if not {"src", "set", "chg"} <= claims:
        _fail("preamble does not make all three claims about the steps")
    return claims


def parse_files(lines):
    store, layouts = {}, set()
    for ln in lines:
        for name, rx in FILE_LAYOUTS:
            m = rx.match(ln)
            if m:
                break
        else:
            _fail("unknown file line: %r" % ln)
        layouts.add(name)
        if m.group(1) in store:
            _fail("file listed twice: " + m.group(1))
        store[m.group(1)] = m.group(2)
    if len(layouts) > 1:
        _fail("mixed file layouts")
    return store, (layouts.pop() if layouts else None)


def parse_semantics(lines):
    seen = {}
    for ln in lines:
        m = re.match(r"^  (set|delete|rename|copy|move): (.+)$", ln)
        if not m:
            _fail("unknown definition line: %r" % ln[:60])
        op, text = m.groups()
        if op in seen:
            _fail("operation defined twice: " + op)
        if text not in SEMANTICS[op]:
            _fail("unknown phrasing of %s: %r" % (op, text[:70]))
        seen[op] = text
    if set(seen) != set(SEMANTICS):
        _fail("definitions missing for " + ", ".join(sorted(set(SEMANTICS) - set(seen))))


def parse_goal(lines):
    goals = []
    for i, ln in enumerate(lines, 1):
        m = re.match(r"^  G(\d+)\. (.+)$", ln)
        if not m or int(m.group(1)) != i:
            _fail("goal line out of sequence: %r" % ln[:60])
        text = m.group(2)
        for kind, rx in GOAL_FORMS:
            g = rx.match(text)
            if g:
                break
        else:
            _fail("unknown goal wording: %r" % text[:80])
        a = g.groups()
        if kind == "count":
            goals.append(("count", a[0], int(a[1]), text))
        elif kind == "count_rev":
            goals.append(("count", a[1], int(a[0]), text))
        elif kind == "content":
            goals.append(("content", a[0], a[1], text))
        elif kind == "same":
            goals.append(("same", a[0], a[1], text))
        else:
            goals.append((kind, a[0], None, text))
        if kind.startswith("count"):          # grammatical number must agree with the figure
            nn = re.search(r"\b(\d+) (files?)\b", text)
            if not nn or (int(nn.group(1)) == 1) != (nn.group(2) == "file"):
                _fail("count and noun number disagree: " + text)
    if not goals:
        _fail("no goal conditions")
    return goals


def _body(body):
    """-> (notation, op, args)"""
    if body.startswith("{"):
        try:
            d = json.loads(body)
        except ValueError:
            _fail("bad json step: " + body[:60])
        op = d.get("op")
        if op not in JSON_KEYS or set(d) != {"op"} | set(JSON_KEYS[op]):
            _fail("json step with unexpected keys: " + body[:80])
        return "json", op, tuple(d[k] for k in JSON_KEYS[op])
    for name, forms in NOTATIONS:
        for op, rx in forms:
            m = rx.match(body)
            if m:
                return name, op, m.groups()
    _fail("unknown step notation: " + body[:80])


def parse_trace(lines):
    steps, numb, nots = [], set(), set()
    for i, ln in enumerate(lines, 1):
        for name, rx in NUMBERINGS:
            m = rx.match(ln)
            if m:
                break
        else:
            _fail("unknown trace line: %r" % ln[:60])
        if int(m.group(1)) != i:
            _fail("step numbers not consecutive at line %d: %r" % (i, ln[:40]))
        numb.add(name)
        nota, op, args = _body(m.group(2))
        nots.add(nota)
        if op == "rename" and "/" in args[1]:
            _fail("rename target is not a plain name: " + args[1])
        for j, a in enumerate(args):
            ok = WORD_RE if (op == "set" and j == 1) else PATH_RE
            if not ok.match(a):
                _fail("argument not recognised as %s: %r" % ("content" if ok is WORD_RE else "path", a))
        steps.append((op, args))
    if len(numb) > 1 or len(nots) > 1:
        _fail("mixed numbering or notation in one trace")
    if not steps:
        _fail("empty trace")
    return steps, numb.pop(), nots.pop()


def parse_state(state):
    paras = state.strip("\n").split("\n\n")
    if len(paras) != 5:
        _fail("expected 5 paragraphs, found %d" % len(paras))
    claims = parse_intro(paras[0])
    start, layout = parse_files(_section(paras, 1, FILE_HEADERS, "file list"))
    parse_semantics(_section(paras, 2, SEM_HEADERS, "definition"))
    goals = parse_goal(_section(paras, 3, GOAL_HEADERS, "goal"))
    steps, numbering, notation = parse_trace(_section(paras, 4, TRACE_HEADERS, "trace"))
    return {"claims": claims, "start": start, "layout": layout, "goals": goals, "steps": steps,
            "numbering": numbering, "notation": notation}


# ================================================================================================== simulation 1: tree
class Tree:
    """Nested dicts: a folder is a dict, a file is its content string."""

    def __init__(self, files):
        self.root = {}
        for p, c in files.items():
            self.put(p, c)

    def _dir(self, parts, create):
        node = self.root
        for part in parts:
            nxt = node.get(part)
            if nxt is None:
                if not create:
                    return None
                nxt = node[part] = {}
            elif not isinstance(nxt, dict):
                _fail("a file is used as a folder: " + "/".join(parts))
            node = nxt
        return node

    def get(self, path):
        *head, leaf = path.split("/")
        d = self._dir(head, False)
        if d is None or leaf not in d:
            return None
        if isinstance(d[leaf], dict):
            _fail("a folder is used as a file: " + path)
        return d[leaf]

    def put(self, path, content):
        *head, leaf = path.split("/")
        d = self._dir(head, True)
        if isinstance(d.get(leaf), dict):
            _fail("a folder is used as a file: " + path)
        d[leaf] = content

    def remove(self, path):
        *head, leaf = path.split("/")
        d = self._dir(head, False)
        del d[leaf]

    def count(self, folder):
        d = self._dir(folder.split("/"), False)
        return 0 if d is None else sum(1 for v in d.values() if not isinstance(v, dict))

    def files(self):
        out = {}

        def walk(node, prefix):
            for k, v in node.items():
                if isinstance(v, dict):
                    walk(v, prefix + k + "/")
                else:
                    out[prefix + k] = v
        walk(self.root, "")
        return out


def run_tree(start, steps, claims):
    t = Tree(start)
    for i, (op, a) in enumerate(steps, 1):
        before = t.files()
        if op == "set":
            t.put(a[0], a[1])
        else:
            src = a[0]
            content = t.get(src)
            if content is None:
                _fail("step %d (%s): source %s is not in the store, contradicting the preamble" % (i, op, src))
            if op == "delete":
                t.remove(src)
            elif op == "rename":
                t.remove(src)
                t.put(posixpath.join(posixpath.dirname(src), a[1]), content)
            elif op == "copy":
                t.put(a[1], content)
            elif op == "move":
                t.remove(src)
                t.put(a[1] + "/" + src.split("/")[-1], content)
        if t.files() == before:
            _fail("step %d (%s %s) leaves the store unchanged, contradicting the preamble" % (i, op, " ".join(a)))
    return t


# ================================================================================================== simulation 2: flat
def run_flat(start, steps):
    table = dict(start)
    for op, a in steps:
        if op == "set":
            table[a[0]] = a[1]
        elif op == "delete":
            table.pop(a[0])
        elif op == "rename":
            head, _, _ = a[0].rpartition("/")
            c = table.pop(a[0])
            table[(head + "/" if head else "") + a[1]] = c
        elif op == "copy":
            table[a[1]] = table[a[0]]
        elif op == "move":
            c = table.pop(a[0])
            table[a[1] + "/" + a[0].rsplit("/", 1)[-1]] = c
    return table


def flat_count(table, folder):
    pre = folder + "/"
    return sum(1 for p in table if p.startswith(pre) and "/" not in p[len(pre):])


# ================================================================================================== goals
def evaluate(goals, tree, table):
    results = []
    for kind, a, b, text in goals:
        if kind == "exists":
            r = tree.get(a) is not None
        elif kind == "absent":
            r = tree.get(a) is None
        elif kind == "content":
            r = tree.get(a) == b             # a missing file reads nothing -> false
        elif kind == "count":
            r = tree.count(a) == b
            if r != (flat_count(table, a) == b):
                _fail("tree and table disagree on the count of " + a)
        elif kind == "same":
            ca, cb = tree.get(a), tree.get(b)
            r = ca is not None and cb is not None and ca == cb   # a missing file has no content to be equal
        else:
            _fail("goal kind " + kind)
        results.append(r)
    return results


def analyze(state):
    """Parsed facts, the final store and the value of every condition (for the audit report)."""
    p = parse_state(state)
    tree = run_tree(p["start"], p["steps"], p["claims"])
    table = run_flat(p["start"], p["steps"])
    if tree.files() != table:
        _fail("tree and table replay disagree")
    p["final"] = table
    p["results"] = evaluate(p["goals"], tree, table)
    return p


def solve(state, question, options):
    if question.strip() != QUESTION:
        _fail("unknown question: %r" % question[:80])
    holds = [k for k, v in options.items() if v.startswith("Every goal condition holds")]
    fails = [k for k, v in options.items() if v.startswith("At least one goal condition does not hold")]
    if len(options) != 2 or len(holds) != 1 or len(fails) != 1:
        _fail("unknown options")
    return holds[0] if all(analyze(state)["results"]) else fails[0]
