"""Independent solver for `toolcall_valid` (second author, works from the rendered text only).

solve(state, question, options) -> 'yes' | 'no'

Reading order of a careful human:
  1. the state has five blocks: the judging conventions, the tool schema (JSON), the user request, the proposed call (JSON)
  2. the call is checked against the schema (types, required fields on every level, enum, minimum / maximum, array size,
     undefined names, date format)
  3. every rule sentence of the tool description is parsed into a rule and evaluated on the call
  4. the request is parsed clause by clause (a closed list of phrasings; anything else raises) into the values it fixes,
     and the call must carry exactly these values (dates computed here, quantity * price kept as exact decimals)
Anything that is not recognised raises `Unrecognised`; nothing is skipped silently.
"""
import calendar
import datetime
import json
import re
from decimal import Decimal

QUESTION = "Is the proposed call correct for the request under this schema?"

PREAMBLE = (
    "You are given the schema of a tool, a user request, and the call that an agent proposes for that request.\n"
    "How a call is judged:\n"
    "- Every object (the arguments, a nested object, each entry of an array) must give all parameters listed under its "
    "\"required\" and may not contain a name that is not under its \"properties\".\n"
    "- Every value must have its declared type and, where the schema says so, be one of the \"enum\" values, lie between "
    "\"minimum\" and \"maximum\" (both included), or (for an array) hold between \"minItems\" and \"maxItems\" entries "
    "(both included); a \"date\" is written YYYY-MM-DD.\n"
    "- Every rule in the tool description must hold for the call.\n"
    "- The request fixes the value of every parameter that it names, also when it gives the value indirectly (a date as a "
    "calendar rule or as a number of days from another date, a count as a word); an amount is a number and a currency "
    "code, and a price \"each\" is the price of one unit. An identifier in brackets after another one and marked \"not\" "
    "is a look-alike that must not be used. The call must pass exactly the values that the request fixes, and the entries "
    "of an array in the order of the request.\n"
    "- A parameter that the request does not name may be left out or set to any value the schema allows."
)


class Unrecognised(Exception):
    pass


def fail(msg):
    raise Unrecognised(msg)


# ------------------------------------------------------------------------------------------------ small helpers
_UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
    "eighteen nineteen".split())}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}


def num(tok):
    """'7' -> 7, 'seven' -> 7, 'twenty-one' -> 21"""
    if re.fullmatch(r"\d+", tok):
        return int(tok)
    if tok in _UNITS:
        return _UNITS[tok]
    if tok in _TENS:
        return _TENS[tok]
    m = re.fullmatch(r"(%s)-(%s)" % ("|".join(_TENS), "|".join(w for w in _UNITS if 1 <= _UNITS[w] <= 9)), tok)
    if m:
        return _TENS[m.group(1)] + _UNITS[m.group(2)]
    fail("number word not understood: %r" % tok)


NUMTOK = r"(?:\d+|[a-z]+(?:-[a-z]+)?)"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "last": -1}

DX = (r"(?:(?P<iso>\d{4}-\d{2}-\d{2})"
      r"|the last day of (?P<m1>%(M)s) (?P<y1>\d{4})"
      r"|the (?P<ord>first|second|third|fourth|fifth|last) (?P<wd>%(W)s) of (?P<m2>%(M)s) (?P<y2>\d{4})"
      r"|the date (?P<n>%(N)s) days? (?P<dir>after|before) (?P<base>\d{4}-\d{2}-\d{2}))"
      % {"M": "|".join(MONTHS), "W": "|".join(WEEKDAYS), "N": NUMTOK})


def iso(d):
    return d.isoformat()


def parse_iso(s):
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        fail("not a date: %r" % s)
    return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def eval_dx(m):
    """value of the date expression matched by DX in match m (an ISO string)"""
    if m.group("iso"):
        return iso(parse_iso(m.group("iso")))
    if m.group("m1"):
        mon = MONTHS.index(m.group("m1")) + 1
        y = int(m.group("y1"))
        return iso(datetime.date(y, mon, calendar.monthrange(y, mon)[1]))
    if m.group("ord"):
        mon = MONTHS.index(m.group("m2")) + 1
        y = int(m.group("y2"))
        wd = WEEKDAYS.index(m.group("wd"))
        days = [datetime.date(y, mon, d) for d in range(1, calendar.monthrange(y, mon)[1] + 1)
                if datetime.date(y, mon, d).weekday() == wd]
        k = ORDINALS[m.group("ord")]
        if k == -1:
            return iso(days[-1])
        if k > len(days):
            fail("month has no %s %s" % (m.group("ord"), m.group("wd")))
        return iso(days[k - 1])
    n = num(m.group("n"))
    base = parse_iso(m.group("base"))
    return iso(base + datetime.timedelta(days=n if m.group("dir") == "after" else -n))


# ------------------------------------------------------------------------------------------------ state blocks
def split_state(state):
    m = re.match(r"^(?P<pre>.*?)\n\nTool schema:\n(?P<schema>\{.*?\})\n\nUser request:\n(?P<req>.*?)\n\n"
                 r"Proposed call:\n(?P<call>\{.*\})$", state, re.S)
    if not m:
        fail("state has not the expected five blocks")
    if m.group("pre").strip() != PREAMBLE:
        fail("judging conventions differ from the ones this solver was written for")
    return m.group("schema"), m.group("req"), m.group("call")


def load(text):
    return json.loads(text, parse_float=Decimal)


# ------------------------------------------------------------------------------------------------ schema validation
KNOWN_KEYS = {"type", "description", "enum", "minimum", "maximum", "minItems", "maxItems", "items", "properties",
              "required", "additionalProperties", "format"}


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def is_num(v):
    return (isinstance(v, (int, Decimal))) and not isinstance(v, bool)


def valid_date_string(s):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return False
    try:
        datetime.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    except ValueError:
        return False
    return True


def validate(val, sch, path, out):
    unknown = set(sch) - KNOWN_KEYS
    if unknown:
        fail("schema keyword not understood: %s" % sorted(unknown))
    t = sch["type"]
    if t == "object":
        if not isinstance(val, dict):
            out.append("%s: type, object expected" % path)
            return
        for k in sch.get("required", []):
            if k not in val:
                out.append("%s.%s: required, missing" % (path, k))
        props = sch.get("properties", {})
        if sch.get("additionalProperties") is not False:
            fail("object without additionalProperties=false")
        for k, v in val.items():
            if k not in props:
                out.append("%s.%s: undefined name" % (path, k))
            else:
                validate(v, props[k], "%s.%s" % (path, k), out)
    elif t == "array":
        if not isinstance(val, list):
            out.append("%s: type, array expected" % path)
            return
        if len(val) < sch.get("minItems", 0):
            out.append("%s: fewer than %s entries" % (path, sch.get("minItems")))
        if "maxItems" in sch and len(val) > sch["maxItems"]:
            out.append("%s: more than %s entries" % (path, sch["maxItems"]))
        for i, e in enumerate(val):
            validate(e, sch["items"], "%s[%d]" % (path, i), out)
    elif t == "string":
        if not isinstance(val, str):
            out.append("%s: type, string expected" % path)
            return
        if "enum" in sch and val not in sch["enum"]:
            out.append("%s: %r not in enum" % (path, val))
        if sch.get("format") == "date" and not valid_date_string(val):
            out.append("%s: %r is not a YYYY-MM-DD date" % (path, val))
    elif t in ("integer", "number"):
        if isinstance(val, Decimal) and t == "integer":
            fail("%s: a decimal written number %s where an integer is declared" % (path, val))
        ok = is_int(val) if t == "integer" else is_num(val)
        if not ok:
            out.append("%s: type, %s expected" % (path, t))
            return
        if "minimum" in sch and val < sch["minimum"]:
            out.append("%s: %s below minimum %s" % (path, val, sch["minimum"]))
        if "maximum" in sch and val > sch["maximum"]:
            out.append("%s: %s above maximum %s" % (path, val, sch["maximum"]))
    elif t == "boolean":
        if not isinstance(val, bool):
            out.append("%s: type, boolean expected" % path)
    else:
        fail("schema type not understood: %r" % t)


# ------------------------------------------------------------------------------------------------ rules of the description
B = r"`(\w+)`"
BD = r"`(\w+)\.(\w+)`"
EXPR = r"`(\w+)`(?: (times|minus) `(\w+)`)?"

# every entry: (regex, kind, function mapping the groups to the rule parameters)
RULE_FORMS = [
    # later day / earlier day / strict
    (r"The date in %s cannot come before the date in %s\." % (B, B), "date", lambda g: (g[0], g[1], False)),
    (r"The date in %s has to be later than the date in %s\." % (B, B), "date", lambda g: (g[0], g[1], True)),
    (r"%s may not be before %s\." % (B, B), "date", lambda g: (g[0], g[1], False)),
    (r"%s must be after %s\." % (B, B), "date", lambda g: (g[0], g[1], True)),
    (r"%s must be on or after %s\." % (B, B), "date", lambda g: (g[0], g[1], False)),
    (r"%s must come at least one day after %s\." % (B, B), "date", lambda g: (g[0], g[1], True)),
    (r"%s has to be earlier than %s\." % (B, B), "date", lambda g: (g[1], g[0], True)),
    (r"%s has to be the same day as %s or earlier\." % (B, B), "date", lambda g: (g[1], g[0], False)),
    # exactly one of the two contact fields: (object, field a, field b)
    (r"Exactly one of %s and %s must be given\." % (BD, BD), "oneof", lambda g: (g[0], g[1], g[3])),
    (r"Give either %s or %s, but not both and not neither\." % (BD, BD), "oneof", lambda g: (g[0], g[1], g[3])),
    (r"One, and only one, of %s and %s has to be present\." % (BD, BD), "oneof", lambda g: (g[0], g[1], g[3])),
    (r"%s and %s are alternatives: exactly one of them is required\." % (BD, BD), "oneof",
     lambda g: (g[0], g[1], g[3])),
    # code only when condition: (code, condition parameter, value)
    (r"Give %s only if %s is '([^']*)'\." % (B, B), "onlywhen", lambda g: (g[0], g[1], g[2])),
    (r"When %s is not '([^']*)', %s must be left out\." % (B, B), "onlywhen", lambda g: (g[2], g[0], g[1])),
    (r"%s is only allowed when %s is '([^']*)'\." % (B, B), "onlywhen", lambda g: (g[0], g[1], g[2])),
    (r"%s may be used only when %s equals '([^']*)'\." % (B, B), "onlywhen", lambda g: (g[0], g[1], g[2])),
    # total = sum over an array: (array, total, field a, op, field b)
    (r"Adding up %s over every entry of %s must give %s\." % (EXPR, B, B), "sum",
     lambda g: (g[3], g[4], g[0], g[1], g[2])),
    (r"The value of %s is the total of %s over all entries of %s; it has to match exactly\." % (B, EXPR, B), "sum",
     lambda g: (g[4], g[0], g[1], g[2], g[3])),
    (r"%s is computed from %s: the sum of %s for all entries\." % (B, B, EXPR), "sum",
     lambda g: (g[1], g[0], g[2], g[3], g[4])),
    (r"%s must equal the sum, over all entries of %s, of %s\." % (B, B, EXPR), "sum",
     lambda g: (g[1], g[0], g[2], g[3], g[4])),
    # every entry's day inside the period: (array, day field, start, end)
    (r"Every %s in %s must lie between %s and %s, both included\." % (B, B, B, B), "within",
     lambda g: (g[1], g[0], g[2], g[3])),
    (r"For all entries of %s, %s is on or after %s and on or before %s\." % (B, B, B, B), "within",
     lambda g: (g[0], g[1], g[2], g[3])),
    (r"No entry of %s may have %s before %s or after %s\." % (B, B, B, B), "within",
     lambda g: (g[0], g[1], g[2], g[3])),
    (r"The %s of each entry in %s falls within %s to %s \(ends included\)\." % (B, B, B, B), "within",
     lambda g: (g[1], g[0], g[2], g[3])),
    # hour window runs forward in every entry: (array, start field, end field)
    (r"No entry of %s may have %s less than or equal to %s\." % (B, B, B), "forward",
     lambda g: (g[0], g[2], g[1])),
    (r"For each entry of %s, %s has to be less than %s\." % (B, B, B), "forward", lambda g: (g[0], g[1], g[2])),
    (r"In every entry of %s, %s must be greater than %s\." % (B, B, B), "forward", lambda g: (g[0], g[2], g[1])),
    (r"%s must exceed %s in all entries of %s\." % (B, B, B), "forward", lambda g: (g[2], g[1], g[0])),
    # count of entries: (array, count parameter)
    (r"The number of entries of %s has to be %s\." % (B, B), "count", lambda g: (g[0], g[1])),
    (r"%s counts the entries of %s\." % (B, B), "count", lambda g: (g[1], g[0])),
    (r"%s must equal the number of entries in %s\." % (B, B), "count", lambda g: (g[1], g[0])),
    (r"%s must have exactly %s entries\." % (B, B), "count", lambda g: (g[0], g[1])),
]
RULE_RX = [(re.compile("^" + rx + "$"), kind, fn) for rx, kind, fn in RULE_FORMS]


def parse_rules(schema):
    desc = schema["description"]
    sentences = re.split(r"(?<=\.)\s+(?=[A-Z`])", desc.strip())
    if "`" in sentences[0]:
        fail("first sentence of the description is not the plain purpose of the tool")
    rules = []
    for s in sentences[1:]:
        for rx, kind, fn in RULE_RX:
            m = rx.match(s)
            if m:
                rules.append((kind, fn(m.groups()), s))
                break
        else:
            fail("rule sentence not understood: %r" % s)
    return rules


def day_of(v):
    if not isinstance(v, str) or not valid_date_string(v):
        return None
    return parse_iso(v)


def eval_rules(rules, args, schema, out, notes):
    props = schema["parameters"]["properties"]

    def need(name):
        if name not in props:
            fail("rule names a parameter that the schema does not have: %s" % name)

    for kind, p, text in rules:
        if kind == "date":
            later, earlier, strict = p
            need(later), need(earlier)
            if later not in args or earlier not in args:
                notes.append("absent operand: %s" % text)
                continue
            a, b = day_of(args[later]), day_of(args[earlier])
            if a is None or b is None:
                continue                                    # already reported as a type / format problem
            if (a <= b) if strict else (a < b):
                out.append("rule: %s" % text)
        elif kind == "oneof":
            obj, fa, fb = p
            need(obj)
            if obj not in args:
                notes.append("absent object: %s" % text)
                continue
            o = args[obj]
            if not isinstance(o, dict):
                continue
            if (fa in o) + (fb in o) != 1:
                out.append("rule: %s" % text)
        elif kind == "onlywhen":
            code, cond, val = p
            need(code), need(cond)
            if code in args and args.get(cond) != val:
                out.append("rule: %s" % text)
        elif kind == "sum":
            arr, tot, fa, op, fb = p
            need(arr), need(tot)
            if arr not in args or tot not in args:
                notes.append("absent operand: %s" % text)
                continue
            a = args[arr]
            if not isinstance(a, list) or not all(isinstance(e, dict) for e in a) or not is_num(args[tot]):
                continue
            s = Decimal(0)
            okk = True
            for e in a:
                x = e.get(fa)
                y = e.get(fb) if fb else None
                if not is_num(x) or (fb and not is_num(y)):
                    okk = False
                    break
                s += Decimal(x) * Decimal(y) if op == "times" else (Decimal(x) - Decimal(y) if op == "minus" else Decimal(x))
            if okk and s != Decimal(args[tot]):
                out.append("rule: %s (sum %s, given %s)" % (text, s, args[tot]))
        elif kind == "within":
            arr, day, lo, hi = p
            need(arr), need(lo), need(hi)
            if arr not in args or lo not in args or hi not in args:
                notes.append("absent operand: %s" % text)
                continue
            a, d1, d2 = args[arr], day_of(args[lo]), day_of(args[hi])
            if not isinstance(a, list) or d1 is None or d2 is None:
                continue
            for e in a:
                dd = day_of(e.get(day)) if isinstance(e, dict) else None
                if dd is not None and not (d1 <= dd <= d2):
                    out.append("rule: %s (day %s)" % (text, e.get(day)))
        elif kind == "forward":
            arr, lo, hi = p
            need(arr)
            if arr not in args:
                notes.append("absent array: %s" % text)
                continue
            a = args[arr]
            if not isinstance(a, list):
                continue
            for e in a:
                if isinstance(e, dict) and is_int(e.get(lo)) and is_int(e.get(hi)) and not e[lo] < e[hi]:
                    out.append("rule: %s (%s..%s)" % (text, e[lo], e[hi]))
        elif kind == "count":
            arr, cnt = p
            need(arr), need(cnt)
            if arr not in args or cnt not in args:
                notes.append("absent operand: %s" % text)
                continue
            if isinstance(args[arr], list) and is_int(args[cnt]) and len(args[arr]) != args[cnt]:
                out.append("rule: %s (%d entries, given %s)" % (text, len(args[arr]), args[cnt]))
        else:
            fail("rule kind")


# ------------------------------------------------------------------------------------------------ the request
OPENERS = {
    "Roster the following shifts": "schedule_shifts",
    "Can you plan shifts for a crew": "schedule_shifts",
    "Please schedule some shifts": "schedule_shifts",
    "I need a rota entered": "schedule_shifts",
    "I would like to place an order": "create_order",
    "Can you enter an order for me": "create_order",
    "Set up an order for us": "create_order",
    "Please create an order": "create_order",
    "Please file a claim": "file_claim",
    "Open a claim for us": "file_claim",
    "I need a claim entered": "file_claim",
    "Can you register an insurance claim": "file_claim",
    "Please book a trip": "book_trip",
    "Can you arrange travel for a group": "book_trip",
    "I need a journey booked": "book_trip",
    "Set up a trip for us": "book_trip",
    "I need a round entered": "plan_delivery",
    "Can you set up a delivery run": "plan_delivery",
    "Organise a delivery for us": "plan_delivery",
    "Please plan a delivery": "plan_delivery",
}

FILLERS = set("""A colleague asked me to do this.|Apologies for the late request.|Good to have this sorted.|Have a good one.|Hope this is clear.|I am doing this for the first time.|I am glad we can do this.|I am grateful for the help.|I am writing this between meetings.|I appreciate the quick help.|I have been meaning to get this done.|I hope the system is behaving.|I will explain the background later.|I will go through the output later.|I will look at the outcome later.|It follows what we discussed earlier.|It has been on my list for a while.|It is a quiet week for us.|It is needed for the yearly meeting.|It is part of the yearly planning.|Many thanks.|Much appreciated.|My colleagues are aware of this.|My manager asked me to take care of it.|Please keep this between us.|Sorry for the short notice.|Thanks in advance.|Thanks.|That would be a great help.|The manager already knows about it.|The same thing came up last season.|Things are calm on my side at the moment.|Things have been busy this month.|This comes up every season.|This is a one-off.|This is for the autumn planning round.|This is needed for the spring planning round.|This is the last thing on my list.|This should not take long.|This was agreed in the last meeting.|This will make things easier for everyone.|We have been waiting for this for some time.""".split("|"))

INTROS = {   # array parameter -> phrases that open the sentence with the entries (and are not part of an entry)
    "items": ["Lines:", "The goods are", "The order lines are:", "The order should contain"],
    "shifts": ["Shifts:", "The rota consists of", "The shifts are:", "Please schedule"],
    "expenses": ["Charges:", "Expenses:", "The expenses are:", "The claim covers"],
    "passengers": ["The group consists of", "Passengers:", "The passengers are:", "Travelling:"],
    "stops": ["The stops are:", "Round:", "Drop off", "The delivery plan has"],
}

LANGUAGES = {"English": "en", "German": "de", "French": "fr", "Dutch": "nl", "Spanish": "es", "Italian": "it",
             "Portuguese": "pt", "Polish": "pl", "Swedish": "sv", "Danish": "da", "Czech": "cs", "Turkish": "tr"}

LK = r"(?:\s*\((?:not to be confused with|careful: not|and not|not) (?P<lk>[A-Z]{2}-\d+)\))?"
NAME = r'"(?P<name>[^"]*)"'
QVV = r'"(?P<v>[^"]*)"'
EMAILRX = r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
PHONERX = r"\d{3}-\d{4}"
CUR = r"[A-Z]{3}"
AMT = r"\d+(?:\.\d+)?"


class Facts(object):
    def __init__(self):
        self.top = {}            # parameter -> fixed value
        self.obj = {}            # object parameter -> {field: value}
        self.arr_name = None
        self.arr = []            # list of {field: value}
        self.lookalikes = []     # strings that must not be used
        self.currency = None

    def set(self, key, value):
        if key in self.top and self.top[key] != value:
            fail("the request fixes %s twice, differently" % key)
        self.top[key] = value


CLAUSES = []     # (compiled regex, handler(m, facts))


def add_clause(rx, handler):
    CLAUSES.append((re.compile(rx), handler))


def simple(param, leads, value_rx, conv=None):
    rx = r"(?:%s) %s" % ("|".join(leads), value_rx)

    def h(m, F):
        v = m.group("v")
        F.set(param, conv(v) if conv else v)
        if m.groupdict().get("lk"):
            F.lookalikes.append(m.group("lk"))
    add_clause(rx, h)


def dated(param, leads):
    rx = r"(?:%s) %s" % ("|".join(leads), DX)

    def h(m, F):
        F.set(param, eval_dx(m))
    add_clause(rx, h)


def flag(param, value, phrases):
    rx = r"(?:%s)" % "|".join(phrases)

    def h(m, F):
        F.set(param, value)
    add_clause(rx, h)


def contact(param, leads, roles):
    suffix = (r"(?:(?: (?:at|reachable at) (?P<e1>%s))|(?: (?:on|reachable on) (?P<p1>%s))"
              r"|(?: with e-mail (?P<e2>%s))|(?: with phone (?P<p2>%s))"
              r"|(?: \(e-mail (?P<e3>%s)\))|(?: \(phone (?P<p3>%s)\)))?" % ((EMAILRX, PHONERX) * 3))
    rx = r"(?:(?:%s) %s|with %s (?:%s))%s" % ("|".join(leads), NAME, NAME.replace("name", "name2"), "|".join(roles),
                                             suffix)

    def h(m, F):
        d = {"name": m.group("name") if m.group("name") is not None else m.group("name2")}
        e = m.group("e1") or m.group("e2") or m.group("e3")
        p = m.group("p1") or m.group("p2") or m.group("p3")
        if e:
            d["email"] = e
        if p:
            d["phone"] = p
        if param in F.obj:
            fail("contact object fixed twice")
        F.obj[param] = d
    add_clause(rx, h)


# ---- generic parameters (all tools)
simple("reference", ["quoting reference", "under reference", "referenced as", "with reference"],
       r"(?P<v>RF-\d+)" + LK)
simple("cost_centre", ["assigned to cost centre", "charged to cost centre", "booked on cost centre",
                       "against cost centre"], r"(?P<v>CC-\d+)" + LK)
simple("memo", ["with the comment", "adding the remark", "noting", "with the memo"], QVV)
simple("approver", ["authorised by", "approved by", "signed off by", "with approval from"], QVV)
add_clause(r"(?:in region (?P<a>[a-z]+)|(?:listed under|for) the (?P<b>[a-z]+) region"
           r"|handled by the (?P<c>[a-z]+) office)",
           lambda m, F: F.set("region", m.group("a") or m.group("b") or m.group("c")))
flag("notify", True, ["telling the requester", "with a notification to the requester", "keeping the requester informed",
                      "letting the requester know"])
flag("notify", False, ["with the requester not told", "without notifying the requester",
                       "with no notification to the requester", "keeping the requester out of it"])
flag("urgent", True, ["flagged as urgent", "marked urgent", "treated as urgent", "as an urgent matter"])
flag("urgent", False, ["as a routine matter", "not urgent", "without any rush", "with no urgency"])


def _language(m, F):
    name = m.group("v")
    if name not in LANGUAGES:
        fail("language not known: %s" % name)
    F.set("language", LANGUAGES[name])


add_clause(r"(?:with the confirmation in|replying in|answered in|confirmed in) (?P<v>[A-Z][a-z]+)", _language)

# ---- create_order
simple("channel", ["booked on the", "via the", "through the", "coming from the"], r"(?P<v>[a-z]+) channel")
simple("discount_code", ["quoting discount code", "applying the code", "using discount code", "with discount code"],
       r"(?P<v>[A-Z]{3}\d{2})")
flag("gift", True, ["wrapped as a gift", "packed as a present"])
flag("gift", False, ["without gift wrapping", "as an ordinary parcel"])
dated("order_date", ["dated", "entered on", "placed on", "with order date"])
dated("delivery_date", ["arriving on", "for delivery on", "to be delivered on", "with delivery on"])
add_clause(r"(?:with (?P<a>[a-z]+) shipping|using (?P<b>[a-z]+) shipping|shipped as (?P<c>[a-z]+)"
           r"|on (?P<d>[a-z]+) shipping terms)",
           lambda m, F: F.set("shipping", m.group("a") or m.group("b") or m.group("c") or m.group("d")))
simple("customer_id", ["billed to customer", "placed by customer", "on behalf of customer", "for customer"],
       r"(?P<v>CU-\d+)" + LK)
contact("contact", ["contact person", "ask for", "contact name"], ["as the contact"])

# ---- schedule_shifts
simple("team_id", ["assigned to team", "covering team", "for team", "on behalf of team"], r"(?P<v>TM-\d+)" + LK)
simple("site", ["based at the", "for the", "on the", "at the"], r"(?P<v>[a-z]+) site")
dated("period_start", ["starting on", "running from", "beginning on", "with the period opening on"])
dated("period_end", ["until", "through", "ending on", "with the period closing on"])
simple("min_staff", ["requiring", "with at least", "staffed by", "needing"],
       r"(?P<v>%s) staff members? (?:on each|per) shift" % NUMTOK, num)
flag("overtime_ok", True, ["overtime is fine", "allowing overtime", "overtime allowed", "with overtime permitted"])
flag("overtime_ok", False, ["no overtime", "disallowing overtime", "overtime not permitted",
                            "with overtime forbidden"])
contact("supervisor", ["supervisor", "supervised by", "overseen by"], ["in charge"])

# ---- file_claim
simple("claim_ref", ["referring to claim", "registered as claim", "under claim number", "for claim"],
       r"(?P<v>CL-\d+)" + LK)
simple("policy_id", ["covered by policy", "against policy", "on policy", "under policy"], r"(?P<v>PL-\d+)" + LK)
dated("incident_date", ["occurring on", "for an incident on", "that happened on", "relating to"])
dated("filed_date", ["reported on", "filed on", "lodged on", "submitted on"])
add_clause(r"(?:classified as (?P<a>[a-z]+) damage|for (?P<b>[a-z]+) damage|under the heading (?P<c>[a-z]+)"
           r"|of the type (?P<d>[a-z]+))",
           lambda m, F: F.set("claim_type", m.group("a") or m.group("b") or m.group("c") or m.group("d")))
simple("waiver_code", ["with waiver code", "applying waiver code", "quoting waiver code", "using the waiver"],
       r"(?P<v>[A-Z]{3}\d{2})")
simple("adjuster", ["assigned to adjuster", "handled by adjuster", "under adjuster"], QVV)
contact("claimant", ["submitted by", "claimant", "on behalf of"], ["as claimant"])

# ---- book_trip
simple("booking_ref", ["tied to booking", "under booking", "against booking", "for the booking"],
       r"(?P<v>BK-\d+)" + LK)
dated("depart_on", ["leaving on", "departing on", "setting off on", "with departure on"])
dated("return_on", ["returning on", "coming back on", "arriving home on", "with the return on"])
add_clause(r"(?:travelling (?P<a>[a-z]+) class|in (?P<b>[a-z]+) class|in the (?P<c>[a-z]+) cabin"
           r"|booked in the (?P<d>[a-z]+) cabin)",
           lambda m, F: F.set("cabin", m.group("a") or m.group("b") or m.group("c") or m.group("d")))
simple("upgrade_code", ["quoting upgrade code", "applying code", "with upgrade code"], r"(?P<v>[A-Z]{3}\d{2})")
flag("insurance", True, ["including insurance", "insured for the trip", "with travel insurance"])
flag("insurance", False, ["not insured", "without insurance"])


def _budget(m, F):
    F.set("budget", Decimal(m.group("amt")))
    F.set("budget_currency", m.group("cur"))


add_clause(r"(?:with a budget of|up to|for no more than|with a ceiling of) (?P<amt>%s) (?P<cur>%s)(?: in total)?"
           % (AMT, CUR), _budget)
contact("traveller_contact", ["booked for", "main traveller", "lead traveller"], ["as lead traveller"])

# ---- plan_delivery
simple("route_id", ["along route", "assigned to route", "on route", "for route"], r"(?P<v>RT-\d+)" + LK)
dated("ship_date", ["dispatched on", "leaving the depot on", "shipping on", "with dispatch on"])
dated("deliver_by", ["to arrive by", "due at the last drop-off by", "delivered by", "with a delivery deadline of"])
add_clause(r"(?:on a (?P<a>[a-z]+)|with a (?P<b>[a-z]+)|by (?P<c>[a-z]+)|using a (?P<d>[a-z]+))",
           lambda m, F: F.set("vehicle", m.group("a") or m.group("b") or m.group("c") or m.group("d")))
add_clause(r"(?:in the (?P<a>[a-z]+) zone|within the (?P<b>[a-z]+) zone|for the (?P<c>[a-z]+) zone"
           r"|as (?P<d>[a-z]+) freight)",
           lambda m, F: F.set("zone", m.group("a") or m.group("b") or m.group("c") or m.group("d")))
add_clause(r"(?:using customs code (?P<a>[A-Z]{3}\d{2})|quoting code (?P<b>[A-Z]{3}\d{2}) for customs"
           r"|declared with customs code (?P<c>[A-Z]{3}\d{2})|with customs code (?P<d>[A-Z]{3}\d{2}))",
           lambda m, F: F.set("customs_code", m.group("a") or m.group("b") or m.group("c") or m.group("d")))
flag("fragile", True, ["handled as fragile goods", "marked as fragile"])
flag("fragile", False, ["not fragile", "with no fragile goods", "with nothing fragile inside", "as ordinary goods"])
contact("driver", ["assigned to", "driver", "driven by"], ["at the wheel"])


def split_sentences(text):
    return re.split(r"(?<=[.?!])\s+(?=[A-Z])", text.strip())


def parse_lead(sentence, F):
    opener = None
    for o in OPENERS:
        if sentence.startswith(o) and (opener is None or len(o) > len(opener)):
            opener = o
    if opener is None:
        fail("request opening not recognised: %r" % sentence[:60])
    pos = len(opener)
    n = len(sentence)
    while pos < n:
        m = re.compile(r"\s*,\s*(?:and\s+)?|\s+and\s+|\s+").match(sentence, pos)
        if m:
            pos = m.end()
        if pos >= n:
            fail("dangling separator at the end of the first sentence")
        if sentence[pos] in ".?" and pos == n - 1:
            break
        hits = []
        for rx, handler in CLAUSES:
            mm = rx.match(sentence, pos)
            if not mm:
                continue
            # a clause must end where the next separator, the closing punctuation or the end begins
            tail = sentence[mm.end():]
            if re.match(r"(?:\s*,|\s+and\s|[.?]?$)", tail):
                hits.append((mm, handler))
        if not hits:
            fail("clause not recognised at: %r" % sentence[pos:pos + 70])
        if len(hits) > 1:
            fail("clause ambiguous (%d patterns) at: %r" % (len(hits), sentence[pos:pos + 70]))
        mm, handler = hits[0]
        handler(mm, F)
        pos = mm.end()
    return OPENERS[opener]


# ---- the entries of the array
ENTRY_FORMS = {}


def entry_form(array, rx, handler):
    ENTRY_FORMS.setdefault(array, []).append((re.compile("^" + rx + "$"), handler))


def _lk(m, F):
    if m.groupdict().get("lk"):
        F.lookalikes.append(m.group("lk"))


def _money(m, F, cur):
    if F.currency is None:
        F.currency = cur
    elif F.currency != cur:
        fail("more than one currency in the entries")


# order lines
def _item(m, F):
    _lk(m, F)
    _money(m, F, m.group("cur"))
    F.arr.append({"sku": m.group("sku"), "quantity": num(m.group("qty")), "unit_price": Decimal(m.group("price"))})


SKU = r"(?P<sku>KX-\d+)" + LK
entry_form("items", r"(?P<qty>%s) units of %s priced at (?P<price>%s) (?P<cur>%s) apiece" % (NUMTOK, SKU, AMT, CUR), _item)
entry_form("items", r"(?P<qty>%s) pieces of %s at (?P<price>%s) (?P<cur>%s) per piece" % (NUMTOK, SKU, AMT, CUR), _item)
entry_form("items", r"%s in a quantity of (?P<qty>%s) at (?P<price>%s) (?P<cur>%s) each" % (SKU, NUMTOK, AMT, CUR), _item)
entry_form("items", r"(?P<qty>%s) of SKU %s at (?P<price>%s) (?P<cur>%s) each" % (NUMTOK, SKU, AMT, CUR), _item)


# shifts
def _shift(m, F):
    _lk(m, F)
    F.arr.append({"employee_id": m.group("emp"), "day": eval_dx(m), "start_hour": int(m.group("h1")),
                  "end_hour": int(m.group("h2"))})


EMP = r"(?P<emp>EM-\d+)" + LK
H1 = r"(?P<h1>\d{1,2}):00"
H2 = r"(?P<h2>\d{1,2}):00"
entry_form("shifts", r"%s covering %s between %s and %s" % (EMP, DX, H1, H2), _shift)
entry_form("shifts", r"%s on %s from %s to %s" % (EMP, DX, H1, H2), _shift)
entry_form("shifts", r"a shift for %s on %s, %s until %s" % (EMP, DX, H1, H2), _shift)
entry_form("shifts", r"employee %s working %s to %s on %s" % (EMP, H1, H2, DX), _shift)


# cost items
def _expense(m, F):
    _lk(m, F)
    _money(m, F, m.group("cur"))
    F.arr.append({"item_ref": m.group("ref"), "kind": m.group("kind"), "amount": Decimal(m.group("amt"))})


REF = r"(?P<ref>EX-\d+)" + LK
KIND = r"(?P<kind>[a-z]+)"
entry_form("expenses", r"an item %s \(%s\) costing (?P<amt>%s) (?P<cur>%s)" % (REF, KIND, AMT, CUR), _expense)
entry_form("expenses", r"the %s bill %s for (?P<amt>%s) (?P<cur>%s)" % (KIND, REF, AMT, CUR), _expense)
entry_form("expenses", r"(?P<amt>%s) (?P<cur>%s) for %s item %s" % (AMT, CUR, KIND, REF), _expense)
entry_form("expenses", r"%s expense %s of (?P<amt>%s) (?P<cur>%s)" % (KIND, REF, AMT, CUR), _expense)


# passengers
def _passenger(m, F):
    F.arr.append({"name": m.group("name"), "age": num(m.group("age"))})


AGE = r"(?P<age>\d+)"
entry_form("passengers", r"%s, aged %s" % (NAME, AGE), _passenger)
entry_form("passengers", r"the passenger %s \(%s years old\)" % (NAME, AGE), _passenger)
entry_form("passengers", r"%s who is %s" % (NAME, AGE), _passenger)
entry_form("passengers", r"%s-year-old %s" % (AGE, NAME), _passenger)


# stops
def _stop(m, F):
    _lk(m, F)
    F.arr.append({"stop_id": m.group("stop"), "parcels": num(m.group("n")), "window_start": int(m.group("h1")),
                  "window_end": int(m.group("h2"))})


STOP = r"(?P<stop>ST-\d+)" + LK
NP = r"(?P<n>%s) parcels?" % NUMTOK
entry_form("stops", r"%s \(%s, window %s to %s\)" % (STOP, NP, H1, H2), _stop)
entry_form("stops", r"%s for %s, to be delivered from %s until %s" % (NP, STOP, H1, H2), _stop)
entry_form("stops", r"%s to stop %s between %s and %s" % (NP, STOP, H1, H2), _stop)
entry_form("stops", r"stop %s receiving %s within the %s to %s window" % (STOP, NP, H1, H2), _stop)


def parse_array_sentence(sentence, arr_name, F):
    intro = None
    for i in INTROS[arr_name]:
        if sentence.startswith(i) and (intro is None or len(i) > len(intro)):
            intro = i
    if intro is None:
        fail("the sentence with the entries does not open with a known introduction: %r" % sentence[:50])
    body = sentence[len(intro):].strip()
    if not body.endswith("."):
        fail("entries do not end with a full stop")
    body = body[:-1]
    entries = re.split(r";\s+", body)
    F.arr_name = arr_name
    for e in entries:
        for rx, handler in ENTRY_FORMS[arr_name]:
            m = rx.match(e)
            if m:
                handler(m, F)
                break
        else:
            fail("entry not recognised: %r" % e)
    assert len(F.arr) == len(entries)


def parse_request(text, schema):
    sentences = split_sentences(text)
    F = Facts()
    tool = parse_lead(sentences[0], F)
    if tool != schema["name"]:
        fail("the request is for another tool than the schema (%s)" % tool)
    arrays = [k for k, v in schema["parameters"]["properties"].items() if v["type"] == "array"]
    if len(arrays) != 1:
        fail("expected exactly one array parameter")
    if len(sentences) < 2:
        fail("no sentence with the entries")
    parse_array_sentence(sentences[1], arrays[0], F)
    for s in sentences[2:]:
        if s not in FILLERS:
            fail("sentence after the entries is not a known filler: %r" % s)
    # the currency of the entries fixes the currency parameter
    if F.currency is not None:
        F.set("currency", F.currency)
    props = schema["parameters"]["properties"]
    for p in list(F.top) + list(F.obj):
        if p not in props:
            fail("the request names a parameter that the schema does not have: %s" % p)
    check_fact_types(F, schema)
    return F


def type_fits(value, sch):
    """a value read from the request must be of the kind the schema declares for its slot"""
    t = sch["type"]
    if isinstance(value, bool):
        return t == "boolean"
    if isinstance(value, int):
        return t == "integer"
    if isinstance(value, Decimal):
        return t == "number"
    if isinstance(value, str):
        return t == "string" and (sch.get("format") != "date" or valid_date_string(value))
    return False


def check_fact_types(F, schema):
    props = schema["parameters"]["properties"]
    for p, v in F.top.items():
        if not type_fits(v, props[p]):
            fail("value read for %s does not fit its declared type: %r" % (p, v))
    for p, d in F.obj.items():
        if props[p]["type"] != "object":
            fail("%s is not an object parameter" % p)
        for k, v in d.items():
            if k not in props[p]["properties"] or not type_fits(v, props[p]["properties"][k]):
                fail("field %s.%s read from the request does not fit the schema" % (p, k))
        for k in props[p].get("required", []):
            if k not in d:
                fail("the request does not fix the required field %s.%s" % (p, k))
    item = props[F.arr_name]["items"]
    for e in F.arr:
        for k, v in e.items():
            if k not in item["properties"] or not type_fits(v, item["properties"][k]):
                fail("entry field %s read from the request does not fit the schema: %r" % (k, v))
        for k in item.get("required", []):
            if k not in e:
                fail("an entry of the request does not fix the required field %s" % k)


# ------------------------------------------------------------------------------------------------ call versus request
def same(got, want):
    if isinstance(want, bool):
        return isinstance(got, bool) and got == want
    if isinstance(want, Decimal):
        return is_num(got) and Decimal(got) == want
    if isinstance(want, int):
        return is_int(got) and got == want
    return isinstance(got, str) and got == want


def all_strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            for s in all_strings(x):
                yield s
    elif isinstance(v, list):
        for x in v:
            for s in all_strings(x):
                yield s


def check_facts(F, args, out):
    for p, want in F.top.items():
        if p not in args:
            out.append("request: %s is named but not passed" % p)
        elif not same(args[p], want):
            out.append("request: %s should be %r, call has %r" % (p, want, args[p]))
    for p, want in F.obj.items():
        if p not in args:
            out.append("request: %s is named but not passed" % p)
            continue
        got = args[p]
        if not isinstance(got, dict):
            continue
        for k, v in want.items():
            if k not in got or not same(got[k], v):
                out.append("request: %s.%s should be %r, call has %r" % (p, k, v, got.get(k)))
    if F.arr_name:
        got = args.get(F.arr_name)
        if F.arr_name not in args:
            out.append("request: %s is named but not passed" % F.arr_name)
        elif isinstance(got, list):
            if len(got) != len(F.arr):
                out.append("request: %d entries asked, call has %d" % (len(F.arr), len(got)))
            for i, (w, g) in enumerate(zip(F.arr, got)):
                if not isinstance(g, dict):
                    continue
                for k, v in w.items():
                    if k not in g or not same(g[k], v):
                        out.append("request: %s[%d].%s should be %r, call has %r" % (F.arr_name, i, k, v, g.get(k)))
    used = set(all_strings(args))
    for lk in F.lookalikes:
        if lk in used:
            out.append("request: the look-alike %s is used" % lk)


def analyse(state):
    schema_text, req_text, call_text = split_state(state)
    schema = load(schema_text)
    call = load(call_text)
    problems = []
    notes = []
    if not isinstance(call, dict) or set(call) != {"name", "arguments"}:
        problems.append("call: not {name, arguments}")
        return problems, notes
    if call["name"] != schema["name"]:
        problems.append("call: another tool name %r" % call["name"])
    args = call["arguments"]
    validate(args, schema["parameters"], "arguments", problems)
    rules = parse_rules(schema)
    if isinstance(args, dict):
        eval_rules(rules, args, schema, problems, notes)
        F = parse_request(req_text, schema)
        check_facts(F, args, problems)
    return problems, notes


def solve(state, question, options):
    if question.strip() != QUESTION:
        fail("question not the expected one")
    if set(options) != {"yes", "no"}:
        fail("options are not yes / no")
    problems, _ = analyse(state)
    return "no" if problems else "yes"
