"""Independent second implementation for perm_inherit (is the request allowed?).

Works from the rendered state alone.  Every rule sentence of the state is looked up in a table of the sentences
that occur, and each sentence is mapped to the convention it states (membership flat / nested upward, scope downward,
seals, role extension, inclusions, deny entries, decision).  An unknown sentence, an unknown structure line, an
unresolved name or a count that does not fit raises ValueError - nothing is skipped silently.

The decision is made by explicit path enumeration:
    (membership chain)  x  (assignment)  x  (walk from the requested node up to the assignment, stopping at seals)
    x  (role extension chain)  x  (own action -> inclusion chain -> requested action)
and then every deny entry is tested on its own (exact action, walk from the requested node up to the entry's node,
requester is the user / has a membership chain to the group).
"""
import re

NOUNS = ("folder", "zone", "section", "namespace", "collection")
NM = r"[A-Za-z0-9_.\-]+"

# --------------------------------------------------------------------------------------------------------------
# the rule sentences that occur (the noun of the node type is replaced by NODE / NODEs) and what each one states
# --------------------------------------------------------------------------------------------------------------
_RULES = [
    ("MEM_FLAT", "Each assignment names a role and either a user or a group. If it names a group, exactly the users listed as members of that group hold the role."),
    ("MEM_FLAT", "An assignment gives one role to one user or to one group. An assignment to a group counts for every user on that group's member list and for nobody else."),
    ("MEM_FLAT", "A role is held by the user an assignment names or, when the assignment names a group, by each user listed in that group. Users who are not listed in the group get nothing from it."),
    ("MEM_NEST", "A role is held by the user an assignment names or, when it names a group, by every member of that group. The members of a group are the users on its list plus all members of each group on its list, and so on through further nesting. A group that is nested inside another gains no members from the group that contains it."),
    ("MEM_NEST", "An assignment gives one role to one user or to one group. An assignment to a group counts for every member of the group. Membership passes through nested groups: when group X is listed as a member of group Y, all members of X (also those X has through its own nested groups) are members of Y. It does not pass the other way: a user listed directly in Y is not thereby a member of X."),
    ("MEM_NEST", "Each assignment names a role and either a user or a group; if it names a group, every member of the group holds the role. Groups may list other groups as members. A user belongs to a group if the group lists the user or lists a group the user belongs to, over any number of steps. Belonging never runs downward: the users listed in an outer group do not belong to the groups listed inside it."),
    ("SCOPE", "An assignment is made at one NODE. It covers that NODE and every NODE below it (directly or further down), and nothing else."),
    ("SCOPE", "Assignments reach downward only: the NODE where an assignment is made and everything below it, however deep, are covered; NODEs beside it or above it are not."),
    ("SCOPE", "The role of an assignment is valid on the NODE named in the assignment and on all NODEs below that NODE at any depth, not on any other NODE."),
    ("SEAL", "A sealed NODE blocks assignments from above: an assignment made at a higher NODE covers neither the sealed NODE nor anything below it. An assignment made at the sealed NODE itself, or at a NODE below it, is not affected by that seal, and NODEs outside the sealed NODE are not affected either."),
    ("SEAL", "Exception for sealed NODEs: an assignment never passes into a sealed NODE from a NODE above it, so the sealed NODE and everything below it stay out of its reach. A seal does nothing to an assignment made at the sealed NODE or below it, and nothing to NODEs that are not inside the sealed NODE."),
    ("SEAL", "Sealing cuts off what comes from above. If the requested NODE is a sealed NODE or lies below one, an assignment made above that sealed NODE does not cover it. Assignments made at the sealed NODE or below it work as usual, and a sealed NODE elsewhere in the tree has no effect."),
    ("ROLE_OWN", "A role allows the actions listed for it."),
    ("ROLE_OWN", "The actions a role allows are the ones listed for that role."),
    ("ROLE_OWN", "Holding a role permits the actions on that role's list."),
    ("ROLE_EXT", "A role allows the actions listed for it. A role that extends another role also allows everything the other role allows, including what that role gets from a role it extends. Extension works one way only: the extended role gains nothing."),
    ("ROLE_EXT", "Holding a role permits the actions on its own list and, when the role extends a second role, every action the second role permits (its own list and whatever it takes over by extension). The second role takes over nothing from the first."),
    ("ROLE_EXT", "The actions a role allows are its own actions plus the actions of the role it extends, plus those of the role that one extends, and so on. Nothing is passed in the opposite direction, from the extending role to the extended one."),
    ("INCL", "Actions can include other actions, exactly as listed. Being allowed an action means being allowed every action it includes, directly or through a chain of listed inclusions. An inclusion is never read backwards, and actions without a listed link do not include each other."),
    ("INCL", "The inclusion list says which action includes which. If X includes Y, a role that allows X allows Y as well; inclusions chain, so if Y in turn includes Z, then X includes Z. Only the listed inclusions exist, and none works in reverse."),
    ("INCL", "Where the inclusion list states that one action includes another, permission for the first counts as permission for the second, and likewise onward along several such lines. There are no unlisted inclusions, and the included action never brings the including one."),
    ("DENY", "A deny entry forbids one action to one user, or to all direct and nested members of one group, on one NODE and all NODEs below it; seals make no difference to deny entries. When an entry matches the requester, the exact action and the NODE, the request is refused whatever the assignments say. An entry for a different action never matches, and inclusions between actions are ignored for deny entries."),
    ("DENY", "A deny entry names a user or a group, one action and one NODE. It applies to a request when the requester is that user or a member of that group (nested membership counts), the requested action is exactly the named action, and the requested NODE is the named NODE or lies below it; a seal does not stop a deny entry. A deny entry that applies beats every assignment. It affects no other action: denying X does not block Y, even if X includes Y or Y includes X."),
    ("DENY", "Deny entries win over assignments. An entry blocks its action for the user it names, or for every member of the group it names (members through nested groups included), on its NODE and on everything below that NODE, sealed or not. It blocks that single action only; requests for other actions are judged as if the entry were not there, also when the actions are linked by an inclusion."),
    ("DEC", "A request is allowed only when an assignment whose role the requester holds covers the requested NODE and that role allows the requested action."),
    ("DEC", "A request is allowed if at least one assignment gives the requester a role that allows the requested action and covers the requested NODE. Otherwise it is not allowed."),
    ("DEC", "Decision: a request is allowed when some assignment that counts for the requester covers the requested NODE with a role that allows the requested action. In every other case it is not allowed."),
    ("DEC_DENY", "A request is allowed only when an assignment whose role the requester holds covers the requested NODE and that role allows the requested action; in addition no deny entry may apply."),
    ("DEC_DENY", "A request is allowed if at least one assignment gives the requester a role that allows the requested action and covers the requested NODE, and no deny entry applies. Otherwise it is not allowed."),
    ("DEC_DENY", "Decision: a request is allowed when some assignment that counts for the requester covers the requested NODE with a role that allows the requested action, unless a deny entry applies. In every other case it is not allowed."),
]
RULE_TAG = {}
for _tag, _txt in _RULES:
    assert _txt not in RULE_TAG
    RULE_TAG[_txt] = _tag

RULE_HEADS = ("Access rules (they apply exactly as written):", "Rules:", "How access is decided:")
TITLES = (
    r"Permission data of a fictional (.+), followed by the rules that govern it\.",
    r"Access export of an invented (.+)\. The rules in this export decide every request\.",
    r"What follows are the access rules and the current permission records of an invented (.+)\.",
)
ACTION_HEADS = ("Actions of this system: ", "Actions: ", "Known actions: ")
USER_HEADS = ("Users: ", "User accounts: ", "People with an account: ")
INCL_HEADS = ("Inclusion list:", "Inclusions between actions:", "Listed inclusions (only these exist):")
ROLE_HEADS = ("Roles and what they allow:", "Roles:", "Role definitions:")
GROUP_HEADS = ("Groups:", "Group membership lists:", "Groups and their members:")
ASSIGN_HEADS = ("Assignments:", "Role assignments:", "Who holds which role where:")
DENY_HEADS = ("Deny entries:", "Denials:", "Explicit deny entries:")
REQ_HEADS = ("The request: ", "Request: ", "Request under review: ")


def _bad(msg):
    raise ValueError(msg)


def _split_items(s, what):
    """a list written with ', ' or with ' | ' (one style per line)"""
    if not s or s != s.strip():
        _bad("empty or padded list in " + what)
    comma, bar = ", " in s, " | " in s
    if comma and bar:
        _bad("mixed separators in " + what)
    parts = s.split(" | " if bar else ", ")
    if any(not re.fullmatch(NM, p) for p in parts):
        _bad("bad item in " + what + ": " + s[:60])
    return parts


def _bullet_lines(block_lines, what):
    """strip the bullet of a body line ('- ' or none); returns the stripped lines and whether bullets were used"""
    out = []
    for ln in block_lines:
        out.append(ln[2:] if ln.startswith("- ") else ln)
    return out


# --------------------------------------------------------------------------------------------------------------
def parse(state):
    if not isinstance(state, str):
        _bad("state is not a string")
    blocks = state.strip("\n").split("\n\n")
    if any(not b.strip() for b in blocks):
        _bad("empty block")
    P = {"rules": None, "actions": None, "incl": None, "roles": None, "users": None, "groups": None,
         "tree": None, "seals": None, "assign": None, "deny": None, "request": None, "noun": None}
    title_ok = False
    pending = []
    # first pass: tree header decides the noun
    noun = None
    for b in blocks:
        h = b.split("\n")[0]
        m = re.fullmatch(r"(Folder|Zone|Section|Namespace|Collection)s \(each line: a (\w+) and the (\w+) it lies in\):", h) \
            or re.fullmatch(r"(Folder|Zone|Section|Namespace|Collection) tree \(each line: a (\w+) and its parent\):", h) \
            or re.fullmatch(r"(Folder|Zone|Section|Namespace|Collection)s as full paths from the top (\w+) \(parts separated by /\):", h)
        if m:
            n = m.group(1).lower()
            if any(g.lower() != n for g in m.groups()[1:]):
                _bad("noun mismatch in tree header")
            if noun is not None:
                _bad("two tree blocks")
            noun = n
            lay = "lies" if "it lies in" in h else ("parent" if "its parent" in h else "path")
            P["tree"] = (lay, b.split("\n")[1:])
    if noun is None:
        _bad("no tree block")
    P["noun"] = noun
    Nn = noun
    for idx, b in enumerate(blocks):
        lines = b.split("\n")
        h = lines[0]
        body = lines[1:]
        if idx == 0:
            if not any(re.fullmatch(t, h) for t in TITLES) or body:
                _bad("unknown title: " + h[:80])
            title_ok = True
            continue
        if h in RULE_HEADS:
            if P["rules"] is not None:
                _bad("two rule blocks")
            P["rules"] = body
        elif h.startswith(ACTION_HEADS):
            if P["actions"] is not None or body:
                _bad("actions block")
            pre = [x for x in ACTION_HEADS if h.startswith(x)][0]
            P["actions"] = _split_items(h[len(pre):], "actions")
        elif h in INCL_HEADS:
            P["incl"] = body
        elif h in ROLE_HEADS:
            P["roles"] = body
        elif h.startswith(USER_HEADS):
            if body or P["users"] is not None:
                _bad("users block")
            pre = [x for x in USER_HEADS if h.startswith(x)][0]
            P["users"] = _split_items(h[len(pre):], "users")
        elif h in GROUP_HEADS:
            P["groups"] = body
        elif h in ASSIGN_HEADS:
            P["assign"] = body
        elif h in DENY_HEADS:
            P["deny"] = body
        elif h in ("Seals:", "Sealed %ss:" % Nn, "%ss marked as sealed:" % Nn.capitalize()):
            P["seals"] = body
        elif h.startswith(REQ_HEADS):
            if body or P["request"] is not None:
                _bad("request block")
            P["request"] = h
        elif re.search(r"\(each line: a \w+ and ", h) or " as full paths from the top " in h:
            pass                                    # the tree block, taken above
        else:
            _bad("unknown block header: " + h[:80])
    if not title_ok:
        _bad("no title")
    for k in ("rules", "actions", "incl", "roles", "users", "groups", "tree", "assign", "request"):
        if P[k] is None:
            _bad("missing block " + k)
    for k in ("rules", "incl", "roles", "groups", "assign"):
        if not P[k]:
            _bad("block without lines: " + k)
    if not P["tree"][1]:
        _bad("tree block without lines")
    return P


def _tag_rules(lines, noun):
    """returns the set of convention tags the rule block states (exactly once each)"""
    numbered = [bool(re.match(r"\d+\. ", ln)) for ln in lines]
    if any(numbered) and not all(numbered):
        _bad("mixed numbering")
    tags = []
    for i, ln in enumerate(lines):
        if all(numbered):
            m = re.match(r"(\d+)\. (.*)$", ln)
            if int(m.group(1)) != i + 1:
                _bad("rule numbering")
            s = m.group(2)
        else:
            if not ln.startswith("- "):
                _bad("rule line without bullet")
            s = ln[2:]
        s = re.sub(r"\b%ss\b" % noun, "NODEs", s)
        s = re.sub(r"\b%s\b" % noun, "NODE", s)
        if s not in RULE_TAG:
            _bad("unknown rule sentence: " + s[:90])
        tags.append(RULE_TAG[s])
    base = [t.split("_")[0] for t in tags]
    for fam in ("MEM", "SCOPE", "ROLE", "INCL", "DEC"):
        if base.count(fam) != 1:
            _bad("rule family %s stated %d times" % (fam, base.count(fam)))
    if base.count("SEAL") > 1 or base.count("DENY") > 1:
        _bad("repeated rule")
    if len(tags) != len(set(tags)):
        _bad("repeated rule tag")
    return set(tags)


def build(state):
    P = parse(state)
    noun = P["noun"]
    tags = _tag_rules(P["rules"], noun)
    W = {"nested": "MEM_NEST" in tags, "ext": "ROLE_EXT" in tags, "seal_rule": "SEAL" in tags,
         "deny_rule": "DENY" in tags}
    if ("DEC_DENY" in tags) != W["deny_rule"]:
        _bad("decision sentence and deny rule disagree")
    if W["seal_rule"] != (P["seals"] is not None):
        _bad("seal rule and seal block disagree")
    if W["deny_rule"] != (P["deny"] is not None):
        _bad("deny rule and deny block disagree")

    actions = P["actions"]
    if len(set(actions)) != len(actions):
        _bad("duplicate action")
    users = P["users"]
    if len(set(users)) != len(users):
        _bad("duplicate user")

    # inclusions
    incl = {}
    for ln in _bullet_lines(P["incl"], "incl"):
        m = re.fullmatch(r"(?:inclusion: )?(%s) includes (%s)" % (NM, NM), ln)
        if not m:
            _bad("inclusion line: " + ln[:80])
        a, b = m.groups()
        if a not in actions or b not in actions:
            _bad("inclusion names an unknown action")
        incl.setdefault(a, []).append(b)

    # roles
    own, ext = {}, {}
    for ln in _bullet_lines(P["roles"], "roles"):
        m = re.fullmatch(r"role (%s): allows (%s(?:, %s)*)(?:; extends role (%s))?" % (NM, NM, NM, NM), ln)
        e = None
        if m:
            r, al, e = m.groups()
        else:
            m = re.fullmatch(r"role: (%s) \| allows: (%s(?:, %s)*)(?: \| extends: (%s))?" % (NM, NM, NM, NM), ln)
            if not m:
                _bad("role line: " + ln[:90])
            r, al, e = m.groups()
            if e == "none":
                e = None
        if r in own:
            _bad("duplicate role")
        al = al.split(", ")
        if any(a not in actions for a in al):
            _bad("role allows an unknown action")
        own[r] = al
        if e is not None:
            ext[r] = e
    for r, e in ext.items():
        if e not in own:
            _bad("role extends an unknown role")
    if ext and not W["ext"]:
        _bad("extends line but the rule states no extension")

    # groups
    mem = {}                                    # group -> list of ('user'|'group', name)
    for ln in _bullet_lines(P["groups"], "groups"):
        m = re.fullmatch(r"group (%s): members (.+)" % NM, ln) or re.fullmatch(r"group: (%s) \| members: (.+)" % NM, ln)
        if not m:
            _bad("group line: " + ln[:90])
        g, rest = m.groups()
        if g in mem:
            _bad("duplicate group")
        items = []
        for it in rest.split(", "):
            mm = re.fullmatch(r"(user|group) (%s)" % NM, it)
            if not mm:
                _bad("group member: " + it[:60])
            items.append((mm.group(1), mm.group(2)))
        mem[g] = items
    for g, items in mem.items():
        for kind, nm in items:
            if kind == "user" and nm not in users:
                _bad("group lists an unknown user")
            if kind == "group" and nm not in mem:
                _bad("group lists an unknown group")
            if kind == "group" and not W["nested"]:
                _bad("nested group but the rule states flat membership")

    # tree
    lay, tl = P["tree"]
    parent, top = {}, []
    if lay == "path":
        seen_lines = set()
        for ln in tl:
            if not ln.startswith("- "):
                _bad("path line without bullet")
            parts = ln[2:].split("/")
            if any(not re.fullmatch(NM, p) for p in parts):
                _bad("path part: " + ln[:60])
            if ln in seen_lines:
                _bad("repeated path line")
            seen_lines.add(ln)
            for i, p in enumerate(parts):
                par = parts[i - 1] if i else None
                if p in parent and parent[p] != par:
                    _bad("node with two parents: " + p)
                parent[p] = par
        # every node must be named by a line of its own (full path)
        ends = [ln[2:].split("/")[-1] for ln in tl]
        if sorted(ends) != sorted(parent):
            _bad("node without its own path line")
    else:
        for ln in tl:
            if not ln.startswith("- "):
                _bad("tree line without bullet")
            s = ln[2:]
            if lay == "lies":
                m = re.fullmatch(r"(%s) is the top %s" % (NM, noun), s)
                if m:
                    n, p = m.group(1), None
                else:
                    m = re.fullmatch(r"(%s) lies in (%s)" % (NM, NM), s)
                    if not m:
                        _bad("tree line: " + s[:80])
                    n, p = m.groups()
            else:
                m = re.fullmatch(r"(%s) \(top %s, no parent\)" % (NM, noun), s)
                if m:
                    n, p = m.group(1), None
                else:
                    m = re.fullmatch(r"(%s) \(parent: (%s)\)" % (NM, NM), s)
                    if not m:
                        _bad("tree line: " + s[:80])
                    n, p = m.groups()
            if n in parent:
                _bad("node defined twice: " + n)
            parent[n] = p
    tops = [n for n, p in parent.items() if p is None]
    if len(tops) != 1:
        _bad("tree has %d tops" % len(tops))
    for n, p in parent.items():
        if p is not None and p not in parent:
            _bad("parent not a node: " + str(p))
        seen, cur = set(), n
        while cur is not None:                      # every node reaches the top, no loop
            if cur in seen:
                _bad("loop in the tree")
            seen.add(cur)
            cur = parent[cur]

    # seals
    sealed = set()
    if P["seals"] is not None:
        if not P["seals"]:
            _bad("empty seal block")
        for ln in _bullet_lines(P["seals"], "seals"):
            m = re.fullmatch(r"sealed %s: (%s)" % (noun, NM), ln) or re.fullmatch(r"(%s)" % NM, ln)
            if not m:
                _bad("seal line: " + ln[:80])
            if m.group(1) not in parent:
                _bad("seal names an unknown node")
            sealed.add(m.group(1))

    # assignments
    assigns = []
    for ln in _bullet_lines(P["assign"], "assign"):
        m = re.fullmatch(r"role (%s) given to (user|group) (%s) at %s (%s)" % (NM, NM, noun, NM), ln) \
            or re.fullmatch(r"assignment: role (%s) \| holder: (user|group) (%s) \| %s: (%s)" % (NM, NM, noun, NM), ln)
        if not m:
            _bad("assignment line: " + ln[:100])
        r, kind, who, n = m.groups()
        if r not in own or n not in parent:
            _bad("assignment names an unknown role or node")
        if (kind == "user" and who not in users) or (kind == "group" and who not in mem):
            _bad("assignment names an unknown holder")
        assigns.append((r, kind, who, n))

    # denies
    denies = []
    if P["deny"] is not None:
        if not P["deny"]:
            _bad("empty deny block")
        for ln in _bullet_lines(P["deny"], "deny"):
            m = re.fullmatch(r"deny (%s) to (user|group) (%s) at %s (%s)" % (NM, NM, noun, NM), ln) \
                or re.fullmatch(r"deny: action (%s) \| for: (user|group) (%s) \| %s: (%s)" % (NM, NM, noun, NM), ln)
            if not m:
                _bad("deny line: " + ln[:100])
            a, kind, who, n = m.groups()
            if a not in actions or n not in parent:
                _bad("deny names an unknown action or node")
            if (kind == "user" and who not in users) or (kind == "group" and who not in mem):
                _bad("deny names an unknown holder")
            denies.append((a, kind, who, n))

    # request
    rq = P["request"]
    m = re.fullmatch(r"The request: may user (%s) (%s) in the %s (%s)\?" % (NM, NM, noun, NM), rq) \
        or re.fullmatch(r"Request: user (%s) asks to (%s) at the %s (%s)\." % (NM, NM, noun, NM), rq) \
        or re.fullmatch(r"Request under review: (%s) wants to (%s) on %s (%s)\." % (NM, NM, noun, NM), rq)
    if not m:
        _bad("request line: " + rq[:100])
    ru, ra, rn = m.groups()
    if ru not in users or ra not in actions or rn not in parent:
        _bad("request names an unknown user, action or node")

    return {"W": W, "actions": actions, "users": users, "incl": incl, "own": own, "ext": ext, "mem": mem,
            "parent": parent, "sealed": sealed, "assigns": assigns, "denies": denies, "req": (ru, ra, rn)}


# --------------------------------------------------------------------------------------------------------------
def _membership_chains(B, user):
    """every chain  user -> g1 -> g2 ...  as a list of groups; result: group -> list of chains reaching it.
    A group lists the user (or an inner group); the chain is the list of groups passed from the inside out."""
    listed_in = {}
    for g, items in B["mem"].items():
        for kind, nm in items:
            listed_in.setdefault((kind, nm), []).append(g)
    out = {}

    def dfs(x, chain):
        for g in listed_in.get(x, []):
            if g in chain:
                _bad("group cycle")
            ch = chain + [g]
            out.setdefault(g, []).append(ch)
            if B["W"]["nested"]:
                dfs(("group", g), ch)

    dfs(("user", user), [])
    return out


def _includes(B, a, target, seen=None):
    """depth-first: does action a reach `target` through listed inclusions (a == target counts)?"""
    if a == target:
        return True
    seen = seen if seen is not None else set()
    if a in seen:
        return False
    seen.add(a)
    return any(_includes(B, b, target, seen) for b in B["incl"].get(a, []))


def _role_chain(B, r):
    chain, cur = [], r
    while cur is not None:
        if cur in chain:
            _bad("role extension loop")
        chain.append(cur)
        cur = B["ext"].get(cur) if B["W"]["ext"] else None
    return chain


def _walk_covers(B, a_node, n):
    """walk from the requested node n upwards; the assignment node a_node is reached -> covered; a sealed node met
    before that (it lies strictly below a_node on the way, or is n itself) -> cut off"""
    cur = n
    while cur is not None:
        if cur == a_node:
            return True
        if cur in B["sealed"]:
            return False
        cur = B["parent"][cur]
    return False


def _above_or_at(B, d_node, n):
    cur = n
    while cur is not None:
        if cur == d_node:
            return True
        cur = B["parent"][cur]
    return False


def paths(B):
    """all allowing paths (assignment index, membership chain, role chain, own action) and the applying denies"""
    u, act, n = B["req"]
    chains = _membership_chains(B, u)
    found = []
    for i, (r, kind, who, an) in enumerate(B["assigns"]):
        if kind == "user":
            if who != u:
                continue
            mchains = [[]]
        else:
            mchains = chains.get(who, [])
            if not mchains:
                continue
        if not _walk_covers(B, an, n):
            continue
        rc = _role_chain(B, r)
        for role in rc:
            for a in B["own"][role]:
                if _includes(B, a, act):
                    for mc in mchains:
                        found.append((i, mc, rc[:rc.index(role) + 1], a))
    hits = []
    for j, (da, kind, who, dn) in enumerate(B["denies"]):
        if da != act:
            continue
        if not _above_or_at(B, dn, n):
            continue
        if kind == "user":
            ok = who == u
        else:
            ok = who in chains
        if ok:
            hits.append(j)
    return found, hits


def decide(state):
    B = build(state)
    found, hits = paths(B)
    return bool(found) and not hits


def solve(state, question, options):
    if question.strip() != "Is the request allowed?":
        _bad("unknown question: " + question[:80])
    keys = list(options)
    yes = [k for k in keys if options[k].strip() == "The request is allowed."]
    no = [k for k in keys if options[k].strip() == "The request is not allowed."]
    if len(keys) != 2 or len(yes) != 1 or len(no) != 1:
        _bad("unexpected options")
    return yes[0] if decide(state) else no[0]


def explain(state):
    """for reports: number of separate facts on the allowing path(s)"""
    B = build(state)
    found, hits = paths(B)
    facts = set()
    for i, mc, rc, a in found:
        facts.add(("assign", i))
        for g in mc:
            facts.add(("member", g))
        for r in rc:
            facts.add(("role", r))
        facts.add(("own", a))
    return {"paths": len(found), "denies": hits, "facts": sorted(facts, key=str), "n": len(facts)}
