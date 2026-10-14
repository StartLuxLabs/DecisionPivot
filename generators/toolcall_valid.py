"""Task toolcall_valid (layer D, generated): "is the proposed tool call correct for the request under this schema?"
    python3 generators/toolcall_valid.py [v1|v2]    (standard library only; no input file, no download)

DIFFICULTY.  The constant DIFFICULTY near the top of the script (or the optional argument) selects the version.  "v2" is the default and
what tasks/toolcall_valid holds; "v1" regenerates the first version byte for byte (flat schemas, params 4 / 6 / 8, five deviation kinds).
The question and the two options are the same in both versions.

GEN_V4 (2026-10-08, the default v2 path; v1 is unchanged).  Three fixes after the blind review:
  * NAME COLLISIONS.  No word of the request equals a parameter name of the schema (the whole name, singular or plural, or one part of it split at the
    underscores) unless the phrase sets that parameter: a cost item is a "bill", not a "receipt" next to the flag `receipt`; "cost", "filed", "claimed",
    "party", "route", "team", "stop", "passenger", "reference", "deliver" and the enum value "phone" were reworded.  Words of the tool's own name
    (create_order: create, order) and date expressions are exempt.  `library_collisions()` tests every phrasing, filler sentence and enum word of every tool
    against every name the tool can have, `name_collisions(spec)` the request of every item (both members of a pair; a pair with a collision is redrawn),
    and invented names / titles / e-mail domains avoid the name words (FORBID).
  * FILLER SENTENCES come from ADDONS2 (44 neutral sentences, no time words, no talk of confirming, replying, telling or hurrying) instead of 8.
  * ENUM NAMES.  A language is named in the request ("replying in Dutch"), the call carries the code (`nl`): the enum unit has `names`, `slot_text` writes the
    name, `slot_regex` / `parse_leaf` map it back, so `check2` and `truth2` agree; the schema description says "two-letter ISO 639-1 code".
  * `meta.level` = 1, 2, 3 for `params` = 6, 9, 12 (the old field stays).

VERSION v2.  `state` = a fixed block of judging conventions, a tool schema in JSON, a user request of two to four sentences and a proposed
call in JSON.  Five invented tools (order, rota, trip, claim, delivery run); the schema of a tool has a pool of 15 to 19 top-level
properties of which a dial level takes 6, 9 or 12 (dial `params`, 200 rows each), always with
  * an array of objects (order lines, shifts, passengers, cost items, delivery stops) with its own required fields, ranges and size limits,
    two to eight entries in the call;  from 9 properties on usually a nested object (name, e-mail, phone);  and one computed parameter (a total,
    a count) whenever a rule needs one;
  * 1, 2 or 3 rules across parameters in the tool description (four phrasings each): a date may not be before another (also strictly after);
    a code is only allowed when another parameter has a given value; exactly one of the e-mail and the phone number is given; a total equals the
    sum over the array of quantity times price / of a field / of end hour minus start hour; a count equals the number of entries; every entry's
    day lies in the period; every hour window runs forward;
  * a request that fixes values indirectly as well as directly: a date as the last day of a month, the n-th (or last) weekday of a month, or the
    date n days after or before another date; line items as "three of SKU KX-4417 at 12.40 EUR each" (so the sum must be computed); and
    look-alike identifiers: "KX-4417 (not KX-4471)" names an identifier with one transposed pair of digits that must not be used.
DESIGN.  Matched pairs as in v1: a correct call (gold yes) that exercises these structures (boundary values, equal dates, entries at the limits,
rules at their edge) and its twin with exactly one planted deviation (gold no, `meta.deviation`):
    missing  a required field is missing: at the top level (an unnamed optional parameter takes its place, so the number of arguments stays
             the same), in one entry of the array, or in the nested object
    enum     one step outside an enum, a range (quantity 21 of 20, price 500.01 of 500, hour 25) or the size of the array; in most cases the request itself
             asks for that value and the call copies it, otherwise the call sets an unnamed field
    type     a string for an integer, a number or a boolean ("3" for 3), an object where the schema says array, a string where it says object
    value    a near miss that contradicts the request: a computed date one day off, a transposed pair of digits (often the look-alike), a price one hundredth
             off, a count off by one, a name with a letter changed, the other currency
    extra    an undefined field at the top level, in an entry or in the object, or a field of another level put at the wrong level
    rule     one rule of the description is broken at its limit: a date one day early, a total or a count off by the smallest step, a second contact
             field, a code without its condition, a day one day outside the period, an hour window of length zero
A computed parameter is recomputed from the call's own entries in every item except the one that breaks its rule, so exactly one thing is wrong.
Each deviation is searched among many candidate edits and kept only when the text-based checker finds exactly one violation of the intended kind.
Dial and counts: 100 pairs per level; deviation kinds 17 / 17 / 17 / 17 / 16 / 16 per level, rotated so that every kind has 50 no-items; the
`rule` deviations are spread evenly over the seven families of rules (`meta.deviation_detail.rule`); 20 pairs per tool and level.
TRUTH TWICE.  `truth2(spec)` validates the structured call (schema nodes, rules, the values named by the request).  `check2(item)` recomputes the
answer from the state text alone: schema JSON, the rules parsed back from the description (28 phrasings), the request parsed with the clause patterns
of the tool (four phrasings per clause, per array entry, per object form and per lead-in) including the date expressions, and the call JSON.  The
script asserts that the two agree on all 600 items, that every negative has exactly one violation of the planted kind at the recorded path, that
the classes, levels and kinds are exactly balanced, that the two members of a pair have the same number of top-level arguments, and the
vocabulary test of rule 4 (no word or token of frequency >= 20 at more than twice the rate in one class).

VERSION v1 (DIFFICULTY = "v1"; the text of the first version, unchanged):

ITEM.  `state` is one text with a fixed block of judging conventions, the tool schema (JSON: name, description, 4 / 6 / 8
properties with type, `enum` or `minimum`/`maximum` where they apply, `required`, `additionalProperties: false`), a user
request of one or two sentences that fixes values (ISO dates, amounts with a currency code, identifiers, counts, words from
an enum, quoted names, yes/no wishes) and a proposed call in JSON.  Question: "Is the proposed call correct for the request
under this schema?"  yes / no.  A call is correct when (1) every required parameter is given and no argument is outside
`properties`, (2) every value has its type and respects `enum` / `minimum` / `maximum` (inclusive) / the date format, and
(3) every value the request fixes is passed unchanged; a parameter the request does not name may be left out or set to any
value the schema allows.  All of this is written in the state (the same block in every item).

DESIGN.  The items come in matched pairs.  A *base* is a correct call (gold yes).  Its twin is the same item with exactly one
planted deviation (gold no), recorded in `meta.deviation`:
    missing  a required parameter is dropped (an unnamed optional one is added, so the number of arguments stays the same)
    enum     a value lies outside the `enum` or the `minimum`/`maximum` range (one step beyond the limit; in half of the
             cases the request itself asks for that value and the call copies it, in the other half the call sets a
             parameter the request does not name)
    type     a string is passed where the schema says integer, number or boolean ("3" for 3)
    value    a value contradicts the request by a near miss (date one day off or day and month swapped, one digit of an
             identifier or amount changed, count off by one, another enum word, another currency, flipped yes/no, a name
             with one letter changed) while it is still valid under the schema
    extra    an argument that the schema does not define (an unnamed optional one is dropped, so the count stays the same)
Both members of a pair share the schema, the phrasing and every other value, so positives and negatives have the same
distribution of sizes, of vocabulary and of numbers of arguments by construction; a pair is two independent rows (the id of the
pair is `meta.pair`).  Values near the limits occur in positives as often as in negatives (the twin of an `enum` item sits on
the limit).

DIAL.  `params` = number of properties of the schema: 4, 6 or 8 (an amount and its currency are two properties).  100 pairs per
level and 20 pairs per deviation kind and level: 600 rows, 300 yes and 300 no, 200 rows per level, 60 no-items per kind.

TRUTH TWICE.  `truth(spec)` decides on the structured specification (`meta.spec`).  `check(item)` recomputes the answer from
the rendered state text alone: it cuts the schema JSON, the request and the call JSON out of the text, parses the request
with the clause patterns of the tool, and validates the call against the schema it just parsed.  The script asserts that the
two agree on all 600 items, that every negative has exactly one violation and that it is of the planted kind, that the
number of arguments is the same in both members of a pair, that the classes are exactly balanced, and that no token of
frequency >= 20 is more than twice as frequent in one class as in the other (vocabulary test of rule 4; checked for words and
for all tokens).  Names of people, titles and identifiers come from syllable generators and code-like patterns; every clause
of the request has four phrasings, every tool four openers, and 40 percent of the requests carry a second sentence."""
import calendar
import collections
import copy
import datetime
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))                    # generators/
ROOT = os.path.join(os.path.dirname(HERE), "generated")              # the items are written to ROOT/tasks/<family>/
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "audits"))    # validate.py and audit.py (run on ROOT/tasks/<family>/)
TASK, SEED = "toolcall_valid", 20261007
DIFFICULTY = "v2"                                  # "v1": the first version (flat schemas, params 4/6/8); "v2": the default, see the docstring
OUT = os.path.join(ROOT, "tasks", TASK)
LEVELS = [4, 6, 8]
KINDS = ["missing", "enum", "type", "value", "extra"]
PER_CELL = 20                                   # pairs per (level, deviation kind)
QUESTION = {"type": "choice", "instructions": "Is the proposed call correct for the request under this schema?",
            "criteria": {"yes": "The call is valid under the schema and matches the request.",
                         "no": "The call violates the schema or does not match the request."}}

# ----------------------------------------------------------------------------------------------------------------
# names from syllables
# ----------------------------------------------------------------------------------------------------------------
SYL = ("ka ke ki ko la le li lo ma me mi mo na ne ni no ra re ri ro sa se si so ta te ti to va ve vi vo za ze zi zo "
       "dor kel mar ven tor quin fal gor hal jor nil pel rud sev tas bren dar").split()
TITLE_A = ["rollout", "billing", "intake", "handover", "audit", "migration", "renewal", "cleanup"]
TITLE_B = ["plan", "review", "batch", "check", "list", "report"]


def sub(label):
    """a sub-generator derived from the master generator random.Random(20261007) and a label (deterministic)"""
    return random.Random(f"{random.Random(SEED).getrandbits(64)}/{label}")


FORBID = frozenset()          # v2 only (set by main_v2): words that no invented name, title or e-mail domain may equal (parameter-name words)


def word(rng, lo=2, hi=3):
    while True:
        w = "".join(rng.choice(SYL) for _ in range(rng.randint(lo, hi)))
        if w not in FORBID:                                 # v1: FORBID is empty, the first draw is taken (same stream as before)
            return w


def person(rng):
    return word(rng).capitalize() + " " + word(rng).capitalize()


def title(rng):
    return f"{word(rng).capitalize()} {rng.choice(TITLE_A)} {rng.choice(TITLE_B)}"


# ----------------------------------------------------------------------------------------------------------------
# the tool library: 8 invented tools, each with a pool of 10 parameters ("units"); every unit carries four
# phrasings of the request clause that fixes its value
# ----------------------------------------------------------------------------------------------------------------
def ID(name, prefix, digits, desc, clauses):
    return dict(kind="id", name=name, prefix=prefix, digits=digits, desc=desc, clauses=clauses, req=True, free=False)


def DATE(name, desc, clauses):
    return dict(kind="date", name=name, desc=desc, clauses=clauses, req=True, free=False)


def INT(name, lo, hi, desc, clauses, free=False):
    return dict(kind="int", name=name, lo=lo, hi=hi, desc=desc, clauses=clauses, req=True, free=free)


def ENUM(name, values, wrong, desc, clauses, free=False, names=None):
    """names (v2): {code: word of the request}; the request says the word, the call carries the code"""
    return dict(kind="enum", name=name, values=values, wrong=wrong, desc=desc, clauses=clauses, req=True, free=free, names=names)


def FLAG(name, desc, yes, no):
    return dict(kind="flag", name=name, desc=desc, yes=yes, no=no, req=False, free=True)


def TEXT(name, gen, desc, clauses):
    return dict(kind="text", name=name, gen=gen, desc=desc, clauses=clauses, req=True, free=False)


def MONEY(name, cur_name, lo, hi, curs, desc, cur_desc, clauses):
    return dict(kind="money", name=name, cur_name=cur_name, lo=lo, hi=hi, curs=curs, desc=desc, cur_desc=cur_desc,
                clauses=clauses, req=True, free=False)


CUR = ["EUR", "USD", "GBP"]
LIB = {}


def domain(tool, desc, openers, units):
    LIB[tool] = dict(tool=tool, desc=desc, openers=openers, units=units)


domain("reserve_room", "Reserve a hotel room for a stay.",
       ["Please book a room", "I need a hotel room booked", "Can you reserve a room for me", "Book a room for our guest"],
       [ID("hotel_id", "HT", 4, "Identifier of the hotel.", ["at hotel {v}", "in hotel {v}", "at the property {v}", "at the hotel {v}"]),
        DATE("check_in", "First night of the stay.",
             ["arriving on {v}", "checking in on {v}", "with check-in on {v}", "starting the stay on {v}"]),
        INT("nights", 1, 14, "Number of nights.",
            ["for {v} night{s}", "staying {v} night{s}", "for a stay of {v} night{s}", "lasting {v} night{s}"]),
        INT("guests", 1, 6, "Number of guests.",
            ["for {v} guest{s}", "with {v} guest{s} in the party", "for a group of {v} guest{s}", "with room for {v} guest{s}"]),
        ENUM("room_type", ["single", "double", "suite"], ["twin", "family", "penthouse"], "Kind of room.",
             ["in {a} {v} room", "as {a} {v} room", "choosing {a} {v} room", "taking {a} {v} room"], free=True),
        FLAG("breakfast", "Whether breakfast is included.",
             ["with breakfast included", "including breakfast", "breakfast included", "with breakfast for everyone"],
             ["without breakfast", "excluding breakfast", "with no breakfast", "with breakfast not wanted"]),
        MONEY("max_price", "currency", 20, 5000, CUR, "Highest total price accepted.", "Currency of max_price.",
              ["with a budget of {amount} {cur}", "for no more than {amount} {cur} in total", "up to {amount} {cur}",
               "with a ceiling of {amount} {cur}"]),
        TEXT("guest_name", "person", "Name of the booking holder.",
             ['under the name "{v}"', 'in the name of "{v}"', 'for the booking holder "{v}"', 'booked by "{v}"']),
        ENUM("view", ["sea", "garden", "city"], ["mountain", "courtyard", "lake"], "Preferred view.",
             ["with {a} {v} view", "offering {a} {v} view", "that has {a} {v} view", "featuring {a} {v} view"], free=True),
        FLAG("late_checkout", "Whether a late check-out is arranged.",
             ["with late check-out", "including late check-out", "late check-out included", "with a late check-out requested"],
             ["without late check-out", "with no late check-out", "normal check-out only", "with check-out at the usual time"])])

domain("schedule_pickup", "Schedule a courier pickup of parcels.",
       ["Please arrange a pickup", "Can you schedule a courier collection", "I would like a parcel pickup booked",
        "Set up a pickup for us"],
       [ID("depot_id", "DP", 3, "Identifier of the sending depot.",
           ["from depot {v}", "at depot {v}", "starting at depot {v}", "collected from the depot {v}"]),
        DATE("pickup_date", "Day of the pickup.", ["on {v}", "for the date {v}", "scheduled for {v}", "planned for {v}"]),
        INT("parcels", 1, 20, "Number of parcels.",
            ["for {v} parcel{s}", "covering {v} parcel{s}", "with {v} parcel{s}", "to collect {v} parcel{s}"]),
        INT("weight_kg", 1, 40, "Total weight in kilograms.",
            ["weighing {v} kg in total", "with a total weight of {v} kg", "totalling {v} kg", "at {v} kg altogether"]),
        ENUM("service", ["standard", "express", "overnight"], ["economy", "freight", "priority"], "Delivery service level.",
             ["with {v} service", "using the {v} service", "as {v} delivery", "on the {v} service"], free=True),
        FLAG("signature", "Whether a signature is required on delivery.",
             ["with signature on delivery", "requiring a signature", "signature required", "with a signature at the door"],
             ["without a signature", "no signature needed", "with signature waived", "with no signature at the door"]),
        MONEY("insured_value", "insured_currency", 10, 5000, CUR, "Value to insure.", "Currency of insured_value.",
              ["insured for {amount} {cur}", "with insurance of {amount} {cur}", "covered up to {amount} {cur}",
               "with cover worth {amount} {cur}"]),
        TEXT("contact_name", "person", "Contact person at the depot.",
             ['contact person "{v}"', 'asking for "{v}" at the depot', 'with "{v}" as the contact', 'for the attention of "{v}"']),
        FLAG("fragile", "Whether the parcels are fragile.",
             ["marked as fragile", "handled as fragile goods", "flagged fragile", "labelled fragile"],
             ["not fragile", "as ordinary goods", "with no fragile goods", "with nothing fragile inside"]),
        ENUM("pickup_window", ["morning", "afternoon", "evening"], ["night", "noon", "midday"], "Part of the day for the pickup.",
             ["in the {v}", "during the {v}", "within the {v} slot", "at some point in the {v}"], free=True)])

domain("pay_invoice", "Record the payment of a supplier invoice.",
       ["Please pay an invoice", "Can you settle a supplier invoice", "I want an invoice paid", "Go ahead and pay this invoice"],
       [ID("vendor_id", "VN", 4, "Identifier of the supplier.",
           ["to supplier {v}", "owed to supplier {v}", "from supplier {v}", "billed by supplier {v}"]),
        ID("invoice_no", "INV", 6, "Number of the invoice.",
           ["numbered {v}", "with invoice number {v}", "referenced as {v}", "carrying the number {v}"]),
        MONEY("amount", "currency", 1, 20000, CUR, "Amount to pay.", "Currency of amount.",
              ["for {amount} {cur}", "of {amount} {cur}", "worth {amount} {cur}", "totalling {amount} {cur}"]),
        DATE("pay_on", "Day on which the payment is made.",
             ["to be paid on {v}", "with payment on {v}", "paid out on {v}", "settled on {v}"]),
        ENUM("method", ["transfer", "card", "cheque"], ["cash", "voucher", "barter"], "Payment method.",
             ["by {v}", "paying by {v}", "via {v}", "through {v}"], free=True),
        ID("cost_centre", "CC", 3, "Cost centre to charge.",
           ["charged to cost centre {v}", "booked on cost centre {v}", "against cost centre {v}", "assigned to cost centre {v}"]),
        TEXT("approver", "person", "Person who approved the payment.",
             ['approved by "{v}"', 'with approval from "{v}"', 'signed off by "{v}"', 'authorised by "{v}"']),
        FLAG("send_receipt", "Whether a receipt is e-mailed.",
             ["e-mailing a receipt", "with a receipt by e-mail", "sending a receipt", "with an e-mailed receipt"],
             ["without a receipt", "no receipt by e-mail", "skipping the receipt", "with no receipt sent"]),
        ENUM("category", ["travel", "equipment", "training", "supplies"], ["catering", "software", "rent"], "Spending category.",
             ["filed under {v}", "as {v} spending", "in the {v} category", "under the {v} heading"], free=True),
        INT("instalments", 1, 12, "Number of instalments.",
            ["in {v} instalment{s}", "split into {v} instalment{s}", "over {v} instalment{s}", "payable in {v} instalment{s}"], free=True)])

domain("open_ticket", "Open a support ticket in a queue.",
       ["Please open a ticket", "Can you file a support ticket", "I need a ticket created", "Create a ticket for this issue"],
       [ID("queue_id", "QU", 3, "Queue that receives the ticket.",
           ["in queue {v}", "for queue {v}", "routed to queue {v}", "sent to queue {v}"]),
        ID("customer_id", "CU", 4, "Customer the ticket is about.",
           ["for customer {v}", "on behalf of customer {v}", "about customer {v}", "raised by customer {v}"]),
        ENUM("priority", ["low", "normal", "high", "urgent"], ["critical", "medium", "blocker"], "Handling priority.",
             ["at {v} priority", "with {v} priority", "marked as {v} priority", "set to {v} priority"], free=True),
        DATE("due_date", "Day by which the ticket should be resolved.",
             ["due on {v}", "to be solved by {v}", "with a deadline of {v}", "to be closed by {v}"]),
        INT("estimate_hours", 1, 80, "Estimated effort in hours.",
            ["estimated at {v} hour{s}", "with an estimate of {v} hour{s}", "expected to take {v} hour{s}", "budgeted at {v} hour{s}"]),
        TEXT("title", "title", "Short title of the ticket.",
             ['titled "{v}"', 'with the title "{v}"', 'named "{v}"', 'called "{v}"']),
        TEXT("assignee", "person", "Person who handles the ticket.",
             ['assigned to "{v}"', 'handled by "{v}"', 'owned by "{v}"', 'given to "{v}"']),
        FLAG("notify", "Whether the customer is notified.",
             ["keeping the customer informed", "with a notification to the customer", "telling the customer", "letting the customer know"],
             ["without notifying the customer", "with no notification to the customer", "keeping the customer out of it",
              "with the customer not told"]),
        ENUM("channel", ["mail", "phone", "chat", "portal"], ["fax", "post", "walk-in"], "Channel the request arrived on.",
             ["received by {v}", "raised via {v}", "reported through {v}", "which arrived by {v}"], free=True),
        FLAG("reopen_allowed", "Whether the ticket may be reopened.",
             ["with reopening allowed", "which may be reopened", "open to reopening", "that can be reopened"],
             ["not to be reopened", "with reopening disabled", "with no reopening", "that cannot be reopened"])])

domain("rent_vehicle", "Rent a vehicle from a branch.",
       ["Please rent a vehicle", "Can you arrange a rental car", "I need a vehicle reserved", "Book a rental vehicle"],
       [ID("branch_id", "BR", 3, "Branch that hands out the vehicle.",
           ["from branch {v}", "at branch {v}", "picked up at branch {v}", "collected at branch {v}"]),
        DATE("pickup_date", "First day of the rental.",
             ["starting on {v}", "from {v}", "with pickup on {v}", "beginning on {v}"]),
        DATE("return_date", "Last day of the rental.",
             ["returned on {v}", "until {v}", "to be handed back on {v}", "ending on {v}"]),
        ENUM("vehicle_class", ["compact", "estate", "van", "minibus"], ["convertible", "truck", "limousine"], "Class of vehicle.",
             ["as {a} {v}", "of class {v}", "in the {v} class", "in the category {v}"], free=True),
        INT("drivers", 1, 4, "Number of registered drivers.",
            ["with {v} driver{s}", "for {v} driver{s}", "registering {v} driver{s}", "listing {v} driver{s}"]),
        FLAG("insurance", "Whether full insurance is added.",
             ["with full insurance", "including full insurance", "plus full insurance cover", "with full cover"],
             ["without insurance", "with no insurance cover", "excluding insurance", "with no cover at all"]),
        MONEY("deposit", "deposit_currency", 50, 3000, CUR, "Deposit to be held.", "Currency of deposit.",
              ["with a deposit of {amount} {cur}", "holding {amount} {cur} as deposit", "against a deposit of {amount} {cur}",
               "leaving a deposit of {amount} {cur}"]),
        TEXT("driver_name", "person", "Name of the main driver.",
             ['for the driver "{v}"', 'with "{v}" as main driver', 'under the name "{v}"', 'driven by "{v}"']),
        INT("child_seats", 0, 3, "Number of child seats.",
            ["with {v} child seat{s}", "adding {v} child seat{s}", "including {v} child seat{s}", "fitted with {v} child seat{s}"], free=True),
        ENUM("fuel_plan", ["prepaid", "refill", "flat"], ["none", "partial", "free"], "Fuel arrangement.",
             ["on a {v} fuel plan", "with a {v} fuel plan", "under a {v} fuel plan", "using a {v} fuel plan"], free=True)])

domain("order_parts", "Order spare parts from a supplier.",
       ["Please order some parts", "Can you place a parts order", "I need spare parts ordered", "Place an order for parts"],
       [ID("supplier_id", "SU", 4, "Identifier of the supplier.",
           ["from supplier {v}", "with supplier {v}", "through supplier {v}", "sourced from supplier {v}"]),
        ID("part_no", "PT", 6, "Catalogue number of the part.",
           ["of part {v}", "for part number {v}", "covering part {v}", "of the part numbered {v}"]),
        INT("quantity", 1, 500, "Number of units.",
            ["for {v} unit{s}", "in a quantity of {v} unit{s}", "totalling {v} unit{s}", "amounting to {v} unit{s}"]),
        DATE("deliver_by", "Latest delivery day.",
             ["delivered by {v}", "to arrive by {v}", "needed no later than {v}", "due at the warehouse by {v}"]),
        ENUM("shipping", ["standard", "express", "freight"], ["air", "sea", "courier"], "Shipping method.",
             ["with {v} shipping", "shipped as {v}", "using {v} shipping", "on {v} shipping"], free=True),
        MONEY("budget", "budget_currency", 10, 50000, CUR, "Spending limit for the order.", "Currency of budget.",
              ["within a budget of {amount} {cur}", "capped at {amount} {cur}", "not exceeding {amount} {cur}",
               "with a spending limit of {amount} {cur}"]),
        FLAG("rush", "Whether the order is a rush order.",
             ["as a rush order", "flagged as rush", "marked rush", "treated as urgent"],
             ["as a normal order", "not as a rush", "marked non-rush", "with no rush"]),
        TEXT("contact", "person", "Contact person for the delivery.",
             ['delivered to "{v}"', 'attention "{v}"', 'with "{v}" as contact', 'care of "{v}"']),
        ID("warehouse", "WH", 2, "Receiving warehouse.",
           ["into warehouse {v}", "for warehouse {v}", "delivered to warehouse {v}", "bound for warehouse {v}"]),
        FLAG("partial_ok", "Whether a partial delivery is accepted.",
             ["accepting partial delivery", "with partial delivery allowed", "partial shipments are fine", "with split deliveries accepted"],
             ["with no partial delivery", "complete delivery only", "partial shipments not accepted", "with split deliveries refused"])])

domain("book_meeting", "Book a meeting room.",
       ["Please book a meeting", "Can you set up a meeting room", "I need a room reserved for a meeting",
        "Schedule a meeting for us"],
       [ID("room_id", "RM", 3, "Identifier of the room.",
           ["in room {v}", "using room {v}", "in meeting room {v}", "held in room {v}"]),
        DATE("date", "Day of the meeting.", ["on {v}", "for {v}", "on the day {v}", "taking place on {v}"]),
        INT("duration_min", 15, 240, "Length of the meeting in minutes.",
            ["lasting {v} minute{s}", "for {v} minute{s}", "of {v} minute{s}", "running {v} minute{s}"]),
        INT("attendees", 2, 30, "Number of attendees.",
            ["for {v} attendee{s}", "with {v} attendee{s}", "expecting {v} attendee{s}", "seating {v} attendee{s}"]),
        ENUM("layout", ["theatre", "boardroom", "classroom"], ["cabaret", "banquet", "horseshoe"], "Seating layout.",
             ["in {a} {v} layout", "with {a} {v} layout", "arranged in {a} {v} layout", "set up with {a} {v} layout"], free=True),
        FLAG("catering", "Whether catering is ordered.",
             ["with catering", "including catering", "catering included", "with catering ordered"],
             ["without catering", "no catering needed", "excluding catering", "with no catering"]),
        TEXT("organiser", "person", "Organiser of the meeting.",
             ['organised by "{v}"', 'hosted by "{v}"', 'on behalf of "{v}"', 'run by "{v}"']),
        ID("project_id", "PJ", 4, "Project the meeting is charged to.",
           ["charged to project {v}", "for project {v}", "billed to project {v}", "booked under project {v}"]),
        FLAG("recording", "Whether the meeting is recorded.",
             ["with the session recorded", "recorded for the archive", "with recording on", "with a recording made"],
             ["not to be recorded", "with recording off", "unrecorded", "with no recording"]),
        MONEY("room_budget", "room_currency", 10, 2000, CUR, "Limit for the room fee.", "Currency of room_budget.",
              ["with a room budget of {amount} {cur}", "at a cost of up to {amount} {cur}", "within {amount} {cur}",
               "with a room fee limit of {amount} {cur}"])])

domain("export_report", "Export a report from a data set.",
       ["Please export a report", "Can you generate a report export", "I need a data export prepared", "Run an export of the report"],
       [ID("dataset_id", "DS", 4, "Identifier of the data set.",
           ["from data set {v}", "of data set {v}", "based on data set {v}", "built on data set {v}"]),
        DATE("from_date", "First day covered.", ["covering {v}", "starting on {v}", "from {v}", "beginning with {v}"]),
        DATE("to_date", "Last day covered.", ["until {v}", "up to {v}", "ending on {v}", "through {v}"]),
        ENUM("format", ["csv", "json", "pdf"], ["xml", "docx", "txt"], "Output format.",
             ["as {v}", "in {v} format", "formatted as {v}", "saved as {v}"], free=True),
        INT("max_rows", 100, 50000, "Maximum number of rows.",
            ["limited to {v} row{s}", "with at most {v} row{s}", "capped at {v} row{s}", "returning no more than {v} row{s}"]),
        FLAG("compress", "Whether the file is compressed.",
             ["compressed into an archive", "as a compressed file", "with compression on", "packed as an archive"],
             ["uncompressed", "without compression", "with compression off", "left uncompressed"]),
        TEXT("recipient", "person", "Person who receives the export.",
             ['sent to "{v}"', 'for "{v}"', 'addressed to "{v}"', 'delivered to "{v}"']),
        ID("cost_centre", "CC", 3, "Cost centre charged for the export.",
           ["charged to cost centre {v}", "on cost centre {v}", "billed to cost centre {v}", "booked to cost centre {v}"]),
        FLAG("include_totals", "Whether a totals row is added.",
             ["with a totals row", "including totals", "plus a totals line", "with totals added"],
             ["without totals", "no totals row", "excluding totals", "with no totals line"]),
        ENUM("priority", ["low", "normal", "high"], ["urgent", "bulk", "rush"], "Scheduling priority.",
             ["at {v} priority", "with {v} priority", "queued as {v} priority", "scheduled at {v} priority"], free=True)])

TOOLS = list(LIB)
PREPOSITIONS = {"at", "in", "for", "from", "to", "with", "on", "of", "by", "as", "into", "through", "within", "during", "using", "via",
                "under", "against", "about", "over", "up", "without", "until"}
ADDONS = ["Thanks.", "This is for the autumn planning round.", "Please confirm once it is done.",
          "It is needed for the regional audit.", "There is no rush on the confirmation.", "I will check the result tomorrow.",
          "The team lead already knows about it.", "Keep the confirmation short, please."]
EXTRAS = [("reference", lambda r: "RF-%04d" % r.randrange(1000, 9999)), ("region", lambda r: r.choice(["north", "south", "east", "west"])),
          ("timeout", lambda r: r.choice([10, 30, 60])), ("locale", lambda r: r.choice(["en", "de", "fr", "nl"])),
          ("tag", lambda r: r.choice(["internal", "pilot", "audit", "trial"])), ("retries", lambda r: r.choice([1, 2, 3])),
          ("comment", lambda r: r.choice(["by phone", "as agreed", "see request"])), ("source", lambda r: r.choice(["web", "app", "desk"])),
          ("verbose", lambda r: r.choice([True, False])), ("dry_run", lambda r: r.choice([True, False])),
          ("channel_hint", lambda r: r.choice(["mail", "chat"])), ("owner", lambda r: r.choice(["ops", "finance", "sales"]))]


def unit_props(u):
    """[(property name, JSON-schema dict)] of a unit (an amount carries its currency as a second property)"""
    k, d = u["kind"], u["desc"]
    if k == "money":
        return [(u["name"], {"type": "number", "minimum": u["lo"], "maximum": u["hi"], "description": d}),
                (u["cur_name"], {"type": "string", "enum": u["curs"], "description": u["cur_desc"]})]
    if k == "date":
        return [(u["name"], {"type": "string", "format": "date", "description": d})]
    if k == "int":
        return [(u["name"], {"type": "integer", "minimum": u["lo"], "maximum": u["hi"], "description": d})]
    if k == "enum":
        return [(u["name"], {"type": "string", "enum": u["values"], "description": d})]
    if k == "flag":
        return [(u["name"], {"type": "boolean", "description": d})]
    return [(u["name"], {"type": "string", "description": d})]


def n_props(u):
    return 2 if u["kind"] == "money" else 1


# ----------------------------------------------------------------------------------------------------------------
# clause patterns: the request is built from these templates and parsed back with the regular expressions made from them
# ----------------------------------------------------------------------------------------------------------------
def compile_template(tmpl, value_re):
    out = []
    for part in re.split(r"(\{[a-z]+\})", tmpl):
        if part == "{v}":
            out.append("(?P<v>%s)" % value_re)
        elif part == "{a}":
            out.append("an?")
        elif part == "{s}":
            out.append("s?")
        elif part == "{amount}":
            out.append(r"(?P<amount>\d+\.\d{2})")
        elif part == "{cur}":
            out.append(r"(?P<cur>[A-Z]{3})")
        else:
            out.append(re.escape(part))
    return re.compile(r"(?<![A-Za-z0-9\-])" + "".join(out) + r"(?![A-Za-z0-9\-])")


def unit_patterns(u):
    """[(compiled regex, flag value or None)] for the clause templates of a unit"""
    if "_rx" in u:
        return u["_rx"]
    k = u["kind"]
    if k == "flag":
        pats = [(compile_template(t, None), True) for t in u["yes"]] + [(compile_template(t, None), False) for t in u["no"]]
    else:
        vre = {"id": r"[A-Z]{2,3}-\d+", "date": r"\d{4}-\d{2}-\d{2}", "int": r"\d+", "text": r'[^"]+', "money": None,
               "enum": "|".join(re.escape(w) for w in sorted(u.get("values", []) + u.get("wrong", []), key=len, reverse=True))}[k]
        pats = [(compile_template(t, vre), None) for t in u["clauses"]]
    u["_rx"] = pats
    return pats


def parse_request(tool, text):
    """{property: value} that the request text fixes, found with the clause patterns of the tool"""
    got = {}
    for u in LIB[tool]["units"]:
        hits = []
        for rx, flag in unit_patterns(u):
            m = rx.search(text)
            if m:
                k = u["kind"]
                if k == "flag":
                    hits.append({u["name"]: flag})
                elif k == "money":
                    hits.append({u["name"]: float(m.group("amount")), u["cur_name"]: m.group("cur")})
                elif k == "int":
                    hits.append({u["name"]: int(m.group("v"))})
                else:
                    hits.append({u["name"]: m.group("v")})
        if hits:
            if any(h != hits[0] for h in hits):
                raise AssertionError(f"ambiguous request for {u['name']}: {hits}")
            got.update(hits[0])
    return got


def fill(tmpl, value):
    """clause text for one value; value is (amount, currency) for an amount"""
    s = tmpl
    if isinstance(value, tuple):
        return s.replace("{amount}", "%.2f" % value[0]).replace("{cur}", value[1])
    if isinstance(value, int) and not isinstance(value, bool):
        return s.replace("{v}", str(value)).replace("{s}", "" if value == 1 else "s")
    return s.replace("{v}", str(value)).replace("{a}", "an" if str(value)[0] in "aeiou" else "a")


# ----------------------------------------------------------------------------------------------------------------
# values and near misses
# ----------------------------------------------------------------------------------------------------------------
def gen_id(rng, u):
    return u["prefix"] + "-" + str(rng.randrange(10 ** (u["digits"] - 1), 10 ** u["digits"]))


def gen_date(rng):
    return (datetime.date(2026, 1, 5) + datetime.timedelta(days=rng.randrange(0, 520))).isoformat()


def gen_amount(rng, u, edge=None):
    if edge == "hi":
        return float(u["hi"])
    if edge == "lo":
        return float(u["lo"])
    whole = rng.randrange(u["lo"], u["hi"])
    return round(whole + rng.choice([0, 0, 0, 0.5, 0.25, 0.75, 0.9]), 2)


def gen_value(rng, u, edge=None):
    """value of a unit: a scalar, or (amount, currency) for an amount"""
    k = u["kind"]
    if k == "id":
        return gen_id(rng, u)
    if k == "date":
        return gen_date(rng)
    if k == "int":
        return u["hi"] if edge == "hi" else (u["lo"] if edge == "lo" else rng.randint(u["lo"], u["hi"]))
    if k == "enum":
        return rng.choice(u["values"])
    if k == "flag":
        return rng.random() < 0.5
    if k == "text":
        return person(rng) if u["gen"] == "person" else title(rng)
    return (gen_amount(rng, u, edge), rng.choice(u["curs"]))


def near_id(rng, v):
    prefix, digits = v.rsplit("-", 1)
    for _ in range(50):
        d = list(digits)
        if rng.random() < 0.5:
            i = rng.randrange(len(d))
            d[i] = rng.choice([c for c in "0123456789" if c != d[i] and not (i == 0 and c == "0")])
        else:
            i = rng.randrange(len(d) - 1)
            d[i], d[i + 1] = d[i + 1], d[i]
        if d[0] != "0" and "".join(d) != digits:
            return prefix + "-" + "".join(d)
    raise AssertionError("no near id")


def near_date(rng, v):
    d = datetime.date.fromisoformat(v)
    cands = [d + datetime.timedelta(days=1), d - datetime.timedelta(days=1)] * 3 + [d + datetime.timedelta(days=7), d - datetime.timedelta(days=7)]
    if d.day <= 12 and d.day != d.month:
        cands += [datetime.date(d.year, d.day, d.month)] * 2
    return rng.choice(cands).isoformat()


def near_amount(rng, u, a):
    cands = {round(a + x, 2) for x in (1, -1, 10, -10, 0.5, -0.5, 100, -100)}
    s = ("%d" % int(a))
    if len(s) >= 2:
        i = rng.randrange(len(s) - 1)
        t = list(s)
        t[i], t[i + 1] = t[i + 1], t[i]
        if t[0] != "0":
            cands.add(round(int("".join(t)) + (a - int(a)), 2))
    cands = sorted(c for c in cands if c != a and u["lo"] <= c <= u["hi"])
    return rng.choice(cands)


def near_text(rng, v):
    words = v.split(" ")
    if len(words) >= 2 and rng.random() < 0.3 and words[0] != words[1]:
        return " ".join(reversed(words))
    for _ in range(50):
        i = rng.randrange(len(words))
        w = list(words[i])
        pos = [j for j, c in enumerate(w) if c in "aeiou"]
        if not pos:
            continue
        j = rng.choice(pos)
        w[j] = rng.choice([c for c in "aeiou" if c != w[j]])
        words[i] = "".join(w)
        out = " ".join(words)
        if out != v:
            return out
    raise AssertionError("no near text")


def near_value(rng, u, v, prop):
    """a value that differs a little from the one the request fixes and is still valid under the schema"""
    k = u["kind"]
    if k == "id":
        return near_id(rng, v)
    if k == "date":
        return near_date(rng, v)
    if k == "int":
        return rng.choice([c for c in (v - 1, v + 1) if u["lo"] <= c <= u["hi"]])
    if k == "enum":
        return rng.choice([w for w in u["values"] if w != v])
    if k == "flag":
        return not v
    if k == "text":
        return near_text(rng, v)
    if prop == u["cur_name"]:
        return rng.choice([c for c in u["curs"] if c != v])
    return near_amount(rng, u, v)


# ----------------------------------------------------------------------------------------------------------------
# building a base (a correct call) and planting one deviation
# ----------------------------------------------------------------------------------------------------------------
def pick_units(rng, dom, P):
    pool = list(dom["units"])
    for _ in range(60):
        rng.shuffle(pool)
        chosen, total = [], 0
        for u in pool:
            if total + n_props(u) <= P:
                chosen.append(u)
                total += n_props(u)
            if total == P:
                break
        if total == P:
            return sorted(chosen, key=lambda u: dom["units"].index(u))
    return None


def eligible(kind, variant, units, roles):
    """candidate (unit, property) targets of the planted deviation in this role assignment"""
    req = [u for u in units if roles[u["name"]] == "req"]
    named = [u for u in units if roles[u["name"]] in ("req", "named")]
    free = [u for u in units if roles[u["name"]] == "free"]
    unused_free = [u for u in units if roles[u["name"]] == "unused" and u["free"]]
    if kind == "missing":
        return [(u, p) for u in req for p, _ in unit_props(u)] if unused_free else []
    if kind == "extra":
        return [(u, u["name"]) for u in free]
    if kind == "enum":
        pool = named if variant == "request" else free
        return [(u, u["name"]) for u in pool if u["kind"] in ("enum", "int", "money")]
    if kind == "type":
        return [(u, u["name"]) for u in units if roles[u["name"]] in ("req", "named", "free") and u["kind"] in ("int", "money", "flag")]
    return [(u, p) for u in named for p, _ in unit_props(u)]            # value


def build_pair(rng, dom, P, kind, variant):
    """-> (base spec, deviated spec) or None when this draw cannot carry the planted deviation"""
    units = pick_units(rng, dom, P)
    if units is None:
        return None
    # roles: req (required, named in the request), named (optional, named in the request), free (optional, in the call with a
    # value the request does not name), unused (optional, not in the call)
    n_req = P // 2 + rng.choice([0, 1])
    order = [u for u in units if u["req"]]
    rng.shuffle(order)
    order.sort(key=lambda u: 0 if u["kind"] in ("id", "date") and rng.random() < 0.7 else 1)   # ids and dates are usually required
    roles, total = {}, 0
    for u in order:
        if total >= n_req or len(roles) + 1 >= len(units):
            break
        roles[u["name"]] = "req"
        total += n_props(u)
    if total < 2:
        return None
    for u in units:
        if u["name"] not in roles:
            r = rng.random()
            roles[u["name"]] = "named" if r < 0.5 else ("free" if r < 0.8 and u["free"] else "unused")
    cands = eligible(kind, variant, units, roles)
    if not cands:
        return None
    tu, tprop = rng.choice(cands)
    edge = None
    if kind == "enum":                              # the correct twin sits on the limit, the deviated one a step beyond it
        edge = "hi" if (tu["kind"] in ("int", "money") and tu["lo"] < 1) else rng.choice(["hi", "lo"])
    vals = {u["name"]: gen_value(rng, u, edge if u is tu else None) for u in units if roles[u["name"]] != "unused"}
    schema_props = [pp for u in units for pp in unit_props(u)]
    props = [p for p, _ in schema_props]
    required = [p for u in units if roles[u["name"]] == "req" for p, _ in unit_props(u)]
    schema = {"name": dom["tool"], "description": dom["desc"],
              "parameters": {"type": "object", "properties": dict(schema_props), "required": required,
                             "additionalProperties": False}}
    request_values, call = {}, {}
    for u in units:
        r = roles[u["name"]]
        if r == "unused":
            continue
        v = vals[u["name"]]
        pv = {u["name"]: v} if u["kind"] != "money" else {u["name"]: v[0], u["cur_name"]: v[1]}
        for p, _ in unit_props(u):
            call[p] = pv[p]
            if r in ("req", "named"):
                request_values[p] = pv[p]
    mentioned = [u["name"] for u in units if roles[u["name"]] in ("req", "named")]
    rng.shuffle(mentioned)
    ids = [u["name"] for u in units if u["kind"] == "id" and u["name"] in mentioned]
    if ids and rng.random() < 0.8:                  # an identifier clause usually comes first ("... a room at hotel HT-2231, ...")
        mentioned.remove(ids[0])
        mentioned.insert(0, ids[0])
    phr = {"opener": rng.randrange(len(dom["openers"])), "order": mentioned,
           "variants": {n: rng.randrange(4) for n in mentioned},
           "addon": rng.randrange(len(ADDONS)) if rng.random() < 0.4 else None}
    base = {"tool": dom["tool"], "params": P, "schema": schema, "roles": roles, "request_values": request_values,
            "call": {p: call[p] for p in props if p in call}, "phrasing": phr, "deviation": None}
    dev = copy.deepcopy(base)
    detail = {"kind": kind, "unit": tu["name"], "prop": tprop}
    if kind == "missing":
        del dev["call"][tprop]
        pad = rng.choice([u for u in units if roles[u["name"]] == "unused" and u["free"]])
        dev["call"][pad["name"]] = gen_value(rng, pad)
        detail["padded"] = pad["name"]
    elif kind == "extra":
        del dev["call"][tprop]
        taken = {p for x in dom["units"] for p, _ in unit_props(x)}
        name, gen = rng.choice([e for e in EXTRAS if e[0] not in taken])
        dev["call"][name] = gen(rng)
        detail["replaced"], detail["prop"] = tprop, name
    elif kind == "enum":
        lim = schema["parameters"]["properties"][tprop]
        if tu["kind"] == "enum":
            bad, detail["limit"] = rng.choice(tu["wrong"]), "enum"
        else:
            bad = lim["maximum"] + 1 if edge == "hi" else lim["minimum"] - 1
            bad = float(bad) if tu["kind"] == "money" else bad
            detail["limit"] = "range"
        dev["call"][tprop] = bad
        if tprop in dev["request_values"]:
            dev["request_values"][tprop] = bad
        detail["variant"] = "request" if tprop in base["request_values"] else "call_only"
    elif kind == "type":
        v = base["call"][tprop]
        dev["call"][tprop] = ("true" if v else "false") if isinstance(v, bool) else str(v)
    else:                                                           # value
        dev["call"][tprop] = near_value(rng, tu, base["request_values"][tprop], tprop)
    names = list(dev["call"])
    if kind == "extra":                                             # the undefined argument sits at a random place
        names.remove(detail["prop"])
        names.insert(rng.randrange(len(names) + 1), detail["prop"])
    else:
        names = [p for p in props if p in dev["call"]]
    dev["call"] = {p: dev["call"][p] for p in names}
    dev["deviation"] = detail
    return base, dev


# ----------------------------------------------------------------------------------------------------------------
# rendering
# ----------------------------------------------------------------------------------------------------------------
CONVENTIONS = (
    "You are given the schema of a tool, a user request, and the call that an agent proposes for that request.\n"
    "How a call is judged:\n"
    "- Every parameter listed under \"required\" must be given, and no argument may have a name that is not under \"properties\".\n"
    "- Every value must have its declared type and, where the schema says so, be one of the \"enum\" values or lie between "
    "\"minimum\" and \"maximum\" (both included); a \"date\" is written YYYY-MM-DD.\n"
    "- The request fixes the value of every parameter that it names (an amount is a number and a currency code, which are "
    "two parameters); the call must pass exactly those values.\n"
    "- A parameter that the request does not name may be left out or set to any value the schema allows.")


def render_schema(schema):
    props = list(schema["parameters"]["properties"].items())
    lines = ["{", f'  "name": {json.dumps(schema["name"])},', f'  "description": {json.dumps(schema["description"])},',
             '  "parameters": {', '    "type": "object",', '    "properties": {']
    for i, (p, d) in enumerate(props):
        lines.append(f"      {json.dumps(p)}: {json.dumps(d)}" + ("," if i < len(props) - 1 else ""))
    lines += ["    },", f'    "required": {json.dumps(schema["parameters"]["required"])},',
              '    "additionalProperties": false', "  }", "}"]
    return "\n".join(lines)


def render_request(spec):
    dom, phr, rv = LIB[spec["tool"]], spec["phrasing"], spec["request_values"]
    clauses = []
    for name in phr["order"]:
        u = next(x for x in dom["units"] if x["name"] == name)
        i = phr["variants"][name]
        if u["kind"] == "flag":
            clauses.append((u["yes"] if rv[name] else u["no"])[i])
        elif u["kind"] == "money":
            clauses.append(fill(u["clauses"][i], (rv[name], rv[u["cur_name"]])))
        else:
            clauses.append(fill(u["clauses"][i], rv[name]))
    body = clauses[0] if len(clauses) == 1 else ", ".join(clauses[:-1]) + " and " + clauses[-1]
    opener = dom["openers"][phr["opener"]]
    sep = " " if clauses[0].split()[0] in PREPOSITIONS else ", "          # "... a room at hotel X" but "... a pickup for us, signature required"
    s = f"{opener}{sep}{body}{'?' if opener.startswith('Can you') else '.'}"
    if phr["addon"] is not None:
        s += " " + ADDONS[phr["addon"]]
    return s


def render_state(spec):
    call = {"name": spec["tool"], "arguments": spec["call"]}
    return (CONVENTIONS + "\n\nTool schema:\n" + render_schema(spec["schema"]) + "\n\nUser request:\n" + render_request(spec) +
            "\n\nProposed call:\n" + json.dumps(call, indent=2))


# ----------------------------------------------------------------------------------------------------------------
# truth and check
# ----------------------------------------------------------------------------------------------------------------
def truth(spec):
    """gold answer from the structured specification"""
    props = spec["schema"]["parameters"]["properties"]
    call, fixed = spec["call"], spec["request_values"]
    if any(r not in call for r in spec["schema"]["parameters"]["required"]):
        return "no"
    for k, v in call.items():
        if k not in props:
            return "no"
        t = props[k]["type"]
        if t == "string" and not isinstance(v, str):
            return "no"
        if t == "integer" and (isinstance(v, bool) or not isinstance(v, int)):
            return "no"
        if t == "number" and (isinstance(v, bool) or not isinstance(v, (int, float))):
            return "no"
        if t == "boolean" and not isinstance(v, bool):
            return "no"
        if "enum" in props[k] and v not in props[k]["enum"]:
            return "no"
        if "minimum" in props[k] and not props[k]["minimum"] <= v <= props[k]["maximum"]:
            return "no"
    for k, v in fixed.items():
        if k not in call or call[k] != v:
            return "no"
    return "yes"


def type_ok(v, t):
    return {"string": isinstance(v, str), "boolean": isinstance(v, bool),
            "integer": isinstance(v, int) and not isinstance(v, bool),
            "number": isinstance(v, (int, float)) and not isinstance(v, bool)}[t]


def violations(state):
    """list of (kind, property) found by reading the state text: schema JSON, request text and call JSON"""
    m = re.search(r"Tool schema:\n(.*)\n\nUser request:\n(.*)\n\nProposed call:\n(.*)\Z", state, re.S)
    schema, request, call = json.loads(m.group(1)), m.group(2), json.loads(m.group(3))
    props, required = schema["parameters"]["properties"], schema["parameters"]["required"]
    args, named, out = call["arguments"], parse_request(schema["name"], m.group(2)), []
    if call["name"] != schema["name"]:
        out.append(("name", call["name"]))
    for r in required:
        if r not in args:
            out.append(("missing", r))
    for k, v in args.items():
        if k not in props:
            out.append(("extra", k))
            continue
        d = props[k]
        if not type_ok(v, d["type"]):
            out.append(("type", k))
            continue
        if "enum" in d and v not in d["enum"]:
            out.append(("enum", k))
        if "minimum" in d and not (d["minimum"] <= v <= d["maximum"]):
            out.append(("enum", k))                                  # outside the range counts as "enum" (outside the allowed values)
        if d.get("format") == "date":
            try:
                datetime.date.fromisoformat(v)
            except ValueError:
                out.append(("format", k))
        if k in named and not (abs(v - named[k]) < 1e-9 if isinstance(named[k], float) else v == named[k]):
            out.append(("value", k))
    for k in named:
        if k not in args and k not in required:
            out.append(("value", k))
    return out


def check(item):
    return "no" if violations(item["state"]) else "yes"


# ----------------------------------------------------------------------------------------------------------------
# vocabulary test, output
# ----------------------------------------------------------------------------------------------------------------
def vocab_test(states, gold, min_freq=20, max_ratio=2.0, pattern=r"[a-z]+"):
    """tokens (lower-cased matches of `pattern`) with document frequency >= min_freq in one class at more than max_ratio times
    the rate of the other (document frequency / class size); returns (offenders, number of tokens tested, worst ratio)"""
    n = collections.Counter(gold)
    df = {c: collections.Counter() for c in n}
    for s, g in zip(states, gold):
        df[g].update(set(re.findall(pattern, s.lower())))
    bad, tested, worst = [], 0, 1.0
    for t in set(df["yes"]) | set(df["no"]):
        a, b = df["yes"][t], df["no"][t]
        if a + b < min_freq:
            continue
        tested += 1
        ra, rb = a / n["yes"], b / n["no"]
        ratio = max(ra, rb) / min(ra, rb) if min(ra, rb) > 0 else float("inf")
        worst = max(worst, ratio)
        if ratio > max_ratio:
            bad.append((t, a, b))
    return sorted(bad), tested, worst


def dumps(item):
    return (json.dumps(item, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
            .replace("\x85", "\\u0085"))


def self_test_library(rng):
    """every clause of every unit is parsed back to the unit's own value and to nothing else"""
    for tool, dom in LIB.items():
        for u in dom["units"]:
            for rep in range(6):
                v = gen_value(rng, u)
                for i in range(4):
                    if u["kind"] == "flag":
                        for val in (True, False):
                            text = (u["yes"] if val else u["no"])[i]
                            assert parse_request(tool, "Please do it " + text + ".") == {u["name"]: val}, (tool, u["name"], text)
                        continue
                    pv = (v[0], v[1]) if u["kind"] == "money" else v
                    text = fill(u["clauses"][i], pv)
                    want = {u["name"]: v[0], u["cur_name"]: v[1]} if u["kind"] == "money" else {u["name"]: v}
                    got = parse_request(tool, "Please do it " + text + " and more.")
                    assert got == want, (tool, u["name"], text, got)


def main_v1():
    master = random.Random(SEED)
    self_test_library(sub("self-test"))
    seeds = [master.getrandbits(64) for _ in range(len(LEVELS) * len(KINDS) * PER_CELL)]
    cells = []
    for level in LEVELS:
        doms = [TOOLS[i % len(TOOLS)] for i in range(len(KINDS) * PER_CELL)]
        master.shuffle(doms)
        for ki, kind in enumerate(KINDS):
            for j in range(PER_CELL):
                variant = None
                if kind == "enum":
                    variant = "request" if j % 2 == 0 else "call_only"
                cells.append((level, kind, variant, doms[ki * PER_CELL + j]))
    rows, pair_no = [], 0
    for (level, kind, variant, tool), seed in zip(cells, seeds):
        pair_no += 1
        rng = random.Random(seed)
        got = None
        for attempt in range(2000):
            dom = LIB[tool if attempt < 400 else rng.choice(TOOLS)]
            got = build_pair(rng, dom, level, kind, "request" if variant == "request" else "call_only")
            if got:
                break
        assert got, (level, kind, variant, tool)
        base, dev = got
        for spec, gold in ((base, "yes"), (dev, "no")):
            assert truth(spec) == gold, (pair_no, kind, gold)
            assert parse_request(spec["tool"], render_request(spec)) == spec["request_values"], (pair_no, kind)
            state = render_state(spec)
            rows.append({"pair": pair_no, "level": level, "gold": gold, "spec": spec, "state": state})
        assert len(base["call"]) == len(dev["call"]), (pair_no, kind)
    sub("shuffle").shuffle(rows)
    items = []
    for i, r in enumerate(rows, 1):
        spec, state = r["spec"], r["state"]
        item = {"id": f"{TASK}:{i:05d}", "state": state, "questions": {"q": copy.deepcopy(QUESTION)}, "gold": r["gold"],
                "soft": None, "group": None,
                "meta": {"source_id": f"{i:05d}", "pair": f"{r['pair']:05d}", "tool": spec["tool"], "params": r["level"],
                         "deviation": spec["deviation"]["kind"] if spec["deviation"] else None,
                         "deviation_param": spec["deviation"]["prop"] if spec["deviation"] else None,
                         "deviation_detail": ({k: v for k, v in spec["deviation"].items() if k in ("limit", "variant", "padded", "replaced")}
                                              if spec["deviation"] else None),
                         "n_args": len(spec["call"]), "n_required": len(spec["schema"]["parameters"]["required"]),
                         "n_named": len(spec["request_values"]), "spec": spec}}
        # truth twice
        viol = violations(state)
        assert check(item) == item["gold"] == truth(spec), (item["id"], viol)
        if item["gold"] == "yes":
            assert viol == [], (item["id"], viol)
        else:
            assert len(viol) == 1 and viol[0][0] == spec["deviation"]["kind"] and viol[0][1] == spec["deviation"]["prop"], (item["id"], viol, spec["deviation"])
        items.append(item)
    # ---- balance and tests
    gold = [it["gold"] for it in items]
    assert collections.Counter(gold) == {"yes": 300, "no": 300}
    for lv in LEVELS:
        assert collections.Counter(it["gold"] for it in items if it["meta"]["params"] == lv) == {"yes": 100, "no": 100}
        for k in KINDS:
            assert sum(1 for it in items if it["meta"]["params"] == lv and it["meta"]["deviation"] == k) == PER_CELL
    for pat, name in ((r"[a-z]+", "words"), (r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", "all tokens")):
        bad, tested, worst = vocab_test([it["state"] for it in items], gold, pattern=pat)
        print(f"vocabulary test ({name}): {tested} tokens with frequency >= 20, worst rate ratio {worst:.2f}, offenders {bad[:10]}")
        assert not bad
    for p in sorted({it["meta"]["pair"] for it in items}):
        pr = [it for it in items if it["meta"]["pair"] == p]
        assert len(pr) == 2 and {x["gold"] for x in pr} == {"yes", "no"} and pr[0]["meta"]["n_args"] == pr[1]["meta"]["n_args"]
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "items.jsonl"), "w", encoding="utf-8") as f:
        for it in items:
            f.write(dumps(it) + "\n")
    lens = [len(it["state"]) for it in items]
    write_task_files(items, min(lens), max(lens))
    report(items, lens)


def write_task_files(items, lo, hi):
    tj = {"task": TASK, "layer": "D",
          "title": "Generated tool calls: is the proposed call correct for the request under the schema?",
          "decision": "whether a proposed tool call is valid under the tool's JSON schema and carries every value that the user request fixes (yes) or breaks the schema or the request (no)",
          "source": {"name": f"generator build/gen_{TASK}.py", "url": "", "files": [], "split": "generated, random.Random(20261007)",
                     "version": "benchmark v0, 7 October 2026"},
          "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
          "labels": "programmatic", "item_source": "generated", "metric": "accuracy", "chance": 0.5, "rows": len(items),
          "groups": None, "question_type": "choice", "options": 2,
          "notes": ("300 matched pairs: a correct call (yes) and the same item with exactly one planted deviation (no); the pair id is meta.pair. "
                    "Deviation kinds (60 each): missing (required parameter dropped, an unnamed optional one added), enum (value one step outside the enum or the "
                    "inclusive range; in half of the cases the request itself asks for it), type (string for integer, number or boolean), value (near-miss "
                    "contradiction of the request, still valid under the schema), extra (argument that the schema does not define, an unnamed optional one dropped). "
                    "Dial meta.params = number of properties of the schema (4, 6, 8; 200 rows each). 8 invented tools; names, titles and identifiers from syllable "
                    f"generators. State length {lo} to {hi} characters. Truth by truth(spec); independently recomputed by check(item) from the state text alone; "
                    "positives and negatives have the same number of arguments in every pair. The judging conventions are part of every state.")}
    with open(os.path.join(OUT, "task.json"), "w", encoding="utf-8") as f:
        json.dump(tj, f, indent=1, ensure_ascii=False)


def audit_lines():
    import audit as audit_mod
    audit_mod.HERE = ROOT
    r = audit_mod.audit(TASK)
    head = f"{'layer':5s} {'task':28s} {'rows':>5s} {'chance':>6s} {'major.':>6s} {'first':>6s} {'length':>6s}  rule"
    ln = f"{r['length']:6.3f}" if r["length"] is not None else f"{'':6s}"
    line = (f"{r['layer']:5s} {TASK:28s} {r['rows']:5d} {r['chance']:6.3f} {r['majority']:6.3f} {r['first']:6.3f} {ln}  "
            f"{r['length_rule']}{'   *' if r['flag'] else ''}")
    return head, line, r


def example_text(it):
    q = it["questions"]["q"]
    opts = "\n".join(f"  {k}: {v}" for k, v in q["criteria"].items())
    return f"STATE:\n{it['state']}\n\nQUESTION: {q['instructions']}\nOPTIONS:\n{opts}\nGOLD: {it['gold']}"


def report(items, lens):
    head, line, r = audit_lines()
    import validate as validate_mod
    validate_mod.HERE = ROOT
    tj, errs = validate_mod.check(TASK)
    status = "OK" if not errs else "ERRORS " + "; ".join(errs[:3])
    cnt_dev = collections.Counter((it["meta"]["params"], it["meta"]["deviation"]) for it in items if it["gold"] == "no")
    ex = []
    for lv in LEVELS:
        cand = [it for it in items if it["meta"]["params"] == lv and it["gold"] == "no" and it["meta"]["deviation"] == {4: "missing", 6: "enum", 8: "value"}[lv]]
        ex.append(cand[0])
    lines = [f"# {TASK}", "", "Generated tool calls: is the proposed call correct for the request under the tool's schema?", "",
             "- Decision: whether a proposed tool call is valid under the tool's JSON schema and carries every value that the user request fixes (yes) or breaks the schema or the request (no).",
             f"- Item source: generated by `build/gen_{TASK}.py` (`random.Random(20261007)`, standard library only, no input file); labels programmatic; licence: generated by the benchmark's script (no third-party text); items included.",
             f"- Rows: {len(items)} (300 yes, 300 no); metric: accuracy (chance 0.5). Rebuild: `python3 build/gen_{TASK}.py`.", "",
             "## What is generated", "",
             "Every item is a tool schema in JSON (4, 6 or 8 properties with type, enum or inclusive range, `required`, `additionalProperties: false`), a user request of one or two sentences that fixes values "
             "(ISO dates, amounts with a currency code, identifiers, counts, enum words, quoted names, yes/no wishes) and a proposed call in JSON. The judging conventions (what *correct* means) are a fixed block at the start of every state. "
             "The 300 positives are correct calls; each has a twin that differs by exactly one planted deviation. Eight invented tools (hotel room, courier pickup, invoice payment, support ticket, vehicle rental, parts order, meeting room, report export) "
             "with 10 parameters each (an amount and its currency are two of the schema's properties); every request clause has four phrasings, every tool four openers, and a second sentence without values is added to about 40% of the requests. "
             "Both rows of a pair are scored as separate items; a bootstrap that resamples by `meta.pair` accounts for their correlation.", "",
             "## Dial", "", "`meta.params` = number of properties in the schema: 4, 6, 8 (200 rows each, 100 yes and 100 no). More properties mean a longer schema, more values in the request and more arguments in the call.", "",
             "## Deviation kinds (`meta.deviation`, number of no-items per dial level)", "",
             "| kind | what is wrong | params 4 | params 6 | params 8 | total |", "|---|---|---|---|---|---|"]
    what = {"missing": "a required parameter is missing (an unnamed optional one is added, so the number of arguments is unchanged)",
            "enum": "a value is outside the enum or one step beyond the inclusive range (half of the cases: the request asks for that value and the call copies it)",
            "type": "a string is passed where the schema says integer, number or boolean",
            "value": "a value contradicts the request by a near miss and is still valid under the schema",
            "extra": "an argument that the schema does not define (an unnamed optional one is dropped)"}
    for k in KINDS:
        lines.append(f"| {k} | {what[k]} | " + " | ".join(str(cnt_dev[(lv, k)]) for lv in LEVELS) + f" | {sum(cnt_dev[(lv, k)] for lv in LEVELS)} |")
    lines += ["", f"State length: {min(lens)} to {max(lens)} characters (median {sorted(lens)[len(lens) // 2]}).", "",
              "## Checks run by the script", "",
              "- `truth(spec)` on the structured specification (`meta.spec`) and `check(item)` on the state text alone agree on all 600 items; every negative has exactly one violation, of the planted kind.",
              "- Exact balance: 300 yes / 300 no; 100 yes and 100 no per dial level; 20 deviations per kind and level. Pairs have the same number of arguments.",
              "- Vocabulary test: no word (and no token) of frequency >= 20 is more than twice as frequent in one class as in the other.", "",
              "## Audit (`python3 audit.py " + TASK + "`)", "", "```", head, line, "```", "",
              f"`python3 validate.py {TASK}`: {status}.", "", "## Examples (one per dial level)", ""]
    for lv, it in zip(LEVELS, ex):
        lines += [f"### params = {lv} ({it['id']}, deviation {it['meta']['deviation']})", "", "```", example_text(it), "```", ""]
    lines += ["## Relation to the authors' training data", "",
              "The items are disjoint from any training generator of the authors by construction: this is a new generator, written for this benchmark "
              "(its own templates and its own invented vocabulary), and every entity is invented."]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"validate: {status}")
    print(head)
    print(line)
    print("classes:", dict(collections.Counter(it["gold"] for it in items)))
    print("per dial level:", dict(collections.Counter(it["meta"]["params"] for it in items)))
    print("per deviation:", dict(collections.Counter(it["meta"]["deviation"] for it in items)))
    print("per level and deviation (no-items):", dict(sorted(cnt_dev.items(), key=lambda x: (x[0][0], str(x[0][1])))))
    print(f"state length: {min(lens)} to {max(lens)} characters")
    print("example (hardest level):")
    print(example_text(ex[-1]))


# ================================================================================================================
# DIFFICULTY v2: nested objects and arrays, rules across parameters, values given indirectly, look-alike identifiers
# ================================================================================================================
LEVELS2 = [6, 9, 12]                                 # dial `params`: top-level properties of the schema
KINDS2 = ["missing", "enum", "type", "value", "extra", "rule"]
KIND_QUOTA2 = {6: [17, 17, 17, 17, 16, 16], 9: [16, 16, 17, 17, 17, 17], 12: [17, 17, 16, 16, 17, 17]}   # no-items per level
N_RULES2 = {6: 1, 9: 2, 12: 3}                       # cross-field rules in the tool description
N_ELEMS2 = {6: (2, 4), 9: (3, 6), 12: (5, 8)}        # entries of the array in the call

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
NUMW = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]
ORDINALS = ["first", "second", "third", "fourth"]
D_LO, D_HI = datetime.date(2026, 2, 10), datetime.date(2027, 5, 20)

NUM_RX = r"(?:\d+|" + "|".join(NUMW) + ")"
DATE_RX = (r"(?:\d{4}-\d{2}-\d{2}|the last day of (?:" + "|".join(MONTHS) + r") \d{4}|the date " + NUM_RX +
           r" days? (?:after|before) \d{4}-\d{2}-\d{2}|the (?:first|second|third|fourth|last) (?:" + "|".join(WEEKDAYS) +
           ") of (?:" + "|".join(MONTHS) + r") \d{4})")
ID_RX = r"[A-Z]{2,3}-\d+"
ASIDE_TEXT = ["(not {x})", "(not to be confused with {x})", "(careful: not {x})", "(and not {x})"]
ASIDE_RX = r"(?: \((?:not|not to be confused with|careful: not|and not) " + ID_RX + r"\))?"


def numword(n):
    return NUMW[n] if 0 <= n <= 12 else str(n)


def num_value(w):
    return int(w) if w.isdigit() else NUMW.index(w)


def month_end(d):
    return datetime.date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def eval_date(s):
    """the date that a date expression of the request denotes"""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return datetime.date.fromisoformat(s)
    m = re.fullmatch(r"the last day of (\w+) (\d{4})", s)
    if m:
        return month_end(datetime.date(int(m.group(2)), MONTHS.index(m.group(1)) + 1, 1))
    m = re.fullmatch(r"the date (\w+) days? (after|before) (\d{4}-\d{2}-\d{2})", s)
    if m:
        n = num_value(m.group(1))
        return datetime.date.fromisoformat(m.group(3)) + datetime.timedelta(days=n if m.group(2) == "after" else -n)
    m = re.fullmatch(r"the (\w+) (\w+) of (\w+) (\d{4})", s)
    first = datetime.date(int(m.group(4)), MONTHS.index(m.group(3)) + 1, 1)
    wd = WEEKDAYS.index(m.group(2))
    if m.group(1) == "last":
        d = month_end(first)
        while d.weekday() != wd:
            d -= datetime.timedelta(days=1)
        return d
    d = first
    while d.weekday() != wd:
        d += datetime.timedelta(days=1)
    return d + datetime.timedelta(days=7 * ORDINALS.index(m.group(1)))


def pick_form(rng, d):
    """how the request will denote the date d: literally, as a calendar rule or as a number of days from another date"""
    if d == month_end(d) and rng.random() < 0.7:
        return {"form": "last"}
    r = rng.random()
    if r < 0.30:
        return {"form": "iso"}
    if r < 0.55:
        return {"form": "after", "n": rng.randint(1, 40)}
    if r < 0.70:
        return {"form": "before", "n": rng.randint(1, 40)}
    return {"form": "weekday"}


def render_date(d, f):
    k = f["form"]
    if k == "iso":
        return d.isoformat()
    if k == "last":
        return f"the last day of {MONTHS[d.month - 1]} {d.year}"
    if k in ("after", "before"):
        n = f["n"]
        anchor = d - datetime.timedelta(days=n) if k == "after" else d + datetime.timedelta(days=n)
        return f"the date {numword(n)} day{'' if n == 1 else 's'} {k} {anchor.isoformat()}"
    ordinal = "last" if month_end(d).day - d.day < 7 else ORDINALS[(d.day - 1) // 7]
    return f"the {ordinal} {WEEKDAYS[d.weekday()]} of {MONTHS[d.month - 1]} {d.year}"


def gen_target(rng):
    """a date in the working range; one in five is the last day of a month"""
    d = D_LO + datetime.timedelta(days=rng.randrange(0, (D_HI - D_LO).days))
    return month_end(d) if rng.random() < 0.2 else d


# ----------------------------------------------------------------------------------------------------------------
# leaf values (a parameter, or a field of an object or of an array entry)
# ----------------------------------------------------------------------------------------------------------------
def CODE(name, desc, clauses):
    return dict(kind="code", name=name, desc=desc, clauses=clauses, req=False, free=False)


def F_id(name, prefix, digits, desc):
    return dict(kind="id", name=name, prefix=prefix, digits=digits, desc=desc)


def F_int(name, lo, hi, desc, words=False):
    return dict(kind="int", name=name, lo=lo, hi=hi, desc=desc, words=words)


def F_amount(name, lo, hi, desc):
    return dict(kind="amount", name=name, lo=lo, hi=hi, desc=desc)


def F_enum(name, values, wrong, desc):
    return dict(kind="enum", name=name, values=values, wrong=wrong, desc=desc)


def F_flag(name, desc):
    return dict(kind="flag", name=name, desc=desc)


def F_date(name, desc):
    return dict(kind="date", name=name, desc=desc)


def F_text(name, gen, desc):
    return dict(kind="text", name=name, gen=gen, desc=desc)


def leaf_schema(f):
    k, d = f["kind"], f["desc"]
    if k == "date":
        return {"type": "string", "format": "date", "description": d}
    if k in ("int", "amount"):
        return {"type": "integer" if k == "int" else "number", "minimum": f["lo"], "maximum": f["hi"], "description": d}
    if k == "enum":
        return {"type": "string", "enum": f["values"], "description": d}
    if k == "flag":
        return {"type": "boolean", "description": d}
    return {"type": "string", "description": d}


def gen_code(rng):
    return "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(3)) + "%02d" % rng.randrange(10, 99)


def gen_leaf(rng, f, edge=None):
    k = f["kind"]
    if k == "id":
        return gen_id(rng, f)
    if k == "date":
        return gen_target(rng).isoformat()
    if k == "int":
        return f["hi"] if edge == "hi" else (f["lo"] if edge == "lo" else rng.randint(f["lo"], f["hi"]))
    if k == "amount":
        return float(gen_amount(rng, f, edge))
    if k == "enum":
        return rng.choice(f["values"])
    if k == "flag":
        return rng.random() < 0.5
    if k == "code":
        return gen_code(rng)
    return person(rng) if f["gen"] == "person" else title(rng)


def swap_adjacent(rng, s, only_digits=False):
    """s with two neighbouring different characters exchanged (a transposition); None when there are none"""
    pos = [i for i in range(len(s) - 1) if s[i] != s[i + 1] and (not only_digits or (s[i].isdigit() and s[i + 1].isdigit()))
           and not (i == 0 and s[i + 1] == "0" and only_digits)]
    if not pos:
        return None
    i = rng.choice(pos)
    return s[:i] + s[i + 1] + s[i] + s[i + 2:]


def lookalike(rng, v):
    """an identifier that differs from v by one transposed pair of digits"""
    pre, dig = v.rsplit("-", 1)
    t = swap_adjacent(rng, dig, only_digits=True)
    return f"{pre}-{t}" if t else near_id(rng, v)


def near_amount2(rng, f, a):
    s = "%.2f" % a
    cands = [round(a + 0.01, 2), round(a - 0.01, 2)] * 2 + [round(a + 0.1, 2), round(a - 1, 2)]
    t = swap_adjacent(rng, s.replace(".", ""), only_digits=True)
    if t:
        cands += [round(float(t[:-2] + "." + t[-2:]), 2)] * 3
    cands = [c for c in cands if c != a and f["lo"] <= c <= f["hi"]]
    return rng.choice(cands)


def near_date2(rng, v):
    d = datetime.date.fromisoformat(v)
    cands = [d + datetime.timedelta(days=1), d - datetime.timedelta(days=1)] * 4 + [d + datetime.timedelta(days=2), d - datetime.timedelta(days=7)]
    if d.day <= 12 and d.day != d.month:
        cands.append(datetime.date(d.year, d.day, d.month))
    return rng.choice(cands).isoformat()


def near_leaf(rng, f, v):
    """a value that differs a little from v and is still valid under the schema"""
    k = f["kind"]
    if k == "id":
        return lookalike(rng, v) if rng.random() < 0.6 else near_id(rng, v)
    if k == "date":
        return near_date2(rng, v)
    if k == "int":
        return rng.choice([c for c in (v - 1, v + 1) if f["lo"] <= c <= f["hi"]])
    if k == "amount":
        return near_amount2(rng, f, v)
    if k == "enum":
        return rng.choice([w for w in f["values"] if w != v])
    if k == "flag":
        return not v
    if k == "code":
        return swap_adjacent(rng, v) or v[::-1]
    if k in ("email", "phone"):
        return v.replace(v[0], "z" if v[0] != "z" else "y", 1)
    return near_text(rng, v)


def slot_regex(name, f):
    """regular expression of a slot of a request template: a group named `name` that holds the value of the field f"""
    k = f["kind"]
    if k == "id":
        return "(?P<%s>%s)%s" % (name, ID_RX, ASIDE_RX)
    rx = {"date": DATE_RX, "int": NUM_RX if f.get("words") else r"\d+", "amount": r"\d+\.\d{2}", "text": r'[^"]+',
          "code": r"[A-Z]{3}\d{2}", "email": r"[a-z]+\.[a-z]+@[a-z]+\.example", "phone": r"555-\d{4}",
          "enum": "|".join(re.escape((f.get("names") or {}).get(w, w)) for w in sorted(f.get("values", []) + f.get("wrong", []), key=len, reverse=True))}[k]
    return "(?P<%s>%s)" % (name, rx)


def parse_leaf(f, s):
    k = f["kind"]
    if k == "date":
        return eval_date(s).isoformat()
    if k == "int":
        return num_value(s)
    if k == "amount":
        return float(s)
    if k == "enum" and f.get("names"):
        return next(c for c, w in f["names"].items() if w == s)           # the request says "Dutch", the call carries "nl"
    return s


def compile_tmpl2(tmpl, slots):
    """slots: {placeholder: regular expression}; {s} (plural) and {a} (article) are built in"""
    out = []
    for part in re.split(r"(\{[a-z_]+\})", tmpl):
        if len(part) > 2 and part[0] == "{" and part[-1] == "}":
            nm = part[1:-1]
            out.append("s?" if nm == "s" else ("an?" if nm == "a" else slots[nm]))
        else:
            out.append(re.escape(part))
    return re.compile(r"(?<![A-Za-z0-9\-])" + "".join(out) + r"(?![A-Za-z0-9\-])")


# ----------------------------------------------------------------------------------------------------------------
# rules that the tool description states about several parameters
# ----------------------------------------------------------------------------------------------------------------
RULE2_TEXT = {
    "date_order": ["`{b}` may not be before `{a}`.", "`{a}` has to be the same day as `{b}` or earlier.",
                   "`{b}` must be on or after `{a}`.", "The date in `{b}` cannot come before the date in `{a}`."],
    "date_strict": ["`{b}` must be after `{a}`.", "`{a}` has to be earlier than `{b}`.",
                    "`{b}` must come at least one day after `{a}`.", "The date in `{b}` has to be later than the date in `{a}`."],
    "only_when": ["`{x}` is only allowed when `{y}` is '{v}'.", "Give `{x}` only if `{y}` is '{v}'.",
                  "`{x}` may be used only when `{y}` equals '{v}'.", "When `{y}` is not '{v}', `{x}` must be left out."],
    "one_of": ["Exactly one of `{p}` and `{q}` must be given.", "Give either `{p}` or `{q}`, but not both and not neither.",
               "`{p}` and `{q}` are alternatives: exactly one of them is required.",
               "One, and only one, of `{p}` and `{q}` has to be present."],
    "sum": ["`{t}` must equal the sum, over all entries of `{a}`, of {expr}.",
            "The value of `{t}` is the total of {expr} over all entries of `{a}`; it has to match exactly.",
            "Adding up {expr} over every entry of `{a}` must give `{t}`.",
            "`{t}` is computed from `{a}`: the sum of {expr} for all entries."],
    "count": ["`{n}` must equal the number of entries in `{a}`.", "The number of entries of `{a}` has to be `{n}`.",
              "`{n}` counts the entries of `{a}`.", "`{a}` must have exactly `{n}` entries."],
    "within": ["Every `{f}` in `{a}` must lie between `{lo}` and `{hi}`, both included.",
               "No entry of `{a}` may have `{f}` before `{lo}` or after `{hi}`.",
               "For all entries of `{a}`, `{f}` is on or after `{lo}` and on or before `{hi}`.",
               "The `{f}` of each entry in `{a}` falls within `{lo}` to `{hi}` (ends included)."],
    "elem_order": ["In every entry of `{a}`, `{hi}` must be greater than `{lo}`.", "For each entry of `{a}`, `{lo}` has to be less than `{hi}`.",
                   "`{hi}` must exceed `{lo}` in all entries of `{a}`.", "No entry of `{a}` may have `{hi}` less than or equal to `{lo}`."]}
RULE2_SLOT = {"v": "(?P<v>[^']+)", "expr": r"(?P<expr>`\w+` times `\w+`|`\w+` minus `\w+`|`\w+`)"}
SUM_EXPR = {"product": "`{f1}` times `{f2}`", "diff": "`{f1}` minus `{f2}`", "field": "`{f1}`"}


def rule2_regex(tmpl):
    out = []
    for part in re.split(r"(\{[a-z]+\})", tmpl):
        if len(part) > 2 and part[0] == "{" and part[-1] == "}":
            nm = part[1:-1]
            out.append(RULE2_SLOT.get(nm) or "(?P<%s>[\\w.]+)" % nm)
        else:
            out.append(re.escape(part))
    return re.compile("".join(out))


RULE2_RX = [(fam, i, rule2_regex(t)) for fam, ts in RULE2_TEXT.items() for i, t in enumerate(ts)]


def rule2_sentence(r):
    k = r["kind"]
    fam = "date_strict" if (k == "date_order" and r.get("strict")) else k
    t = RULE2_TEXT[fam][r["variant"]]
    if k == "date_order":
        return t.format(a=r["a"], b=r["b"])
    if k == "only_when":
        return t.format(x=r["x"], y=r["y"], v=r["v"])
    if k == "one_of":
        return t.format(p=r["p"], q=r["q"])
    if k == "sum":
        return t.replace("{expr}", SUM_EXPR[r["expr"]]).format(t=r["t"], a=r["a"], f1=r.get("f1"), f2=r.get("f2"))
    if k == "count":
        return t.format(n=r["n"], a=r["a"])
    if k == "within":
        return t.format(f=r["f"], a=r["a"], lo=r["lo"], hi=r["hi"])
    return t.format(a=r["a"], hi=r["hi"], lo=r["lo"])                     # elem_order


def parse_rules2(desc):
    """the rules stated in a tool description, in the order of the text"""
    found = []
    for fam, i, rx in RULE2_RX:
        for m in rx.finditer(desc):
            found.append((m.start(), m.end(), fam, i, m.groupdict()))
    found.sort()
    out, end = [], -1
    for s, e, fam, i, g in found:
        assert s >= end, ("rule sentences overlap", desc[s:e])
        end = e
        if fam in ("date_order", "date_strict"):
            out.append({"kind": "date_order", "strict": fam == "date_strict", "a": g["a"], "b": g["b"]})
        elif fam == "sum":
            parts = re.findall(r"`(\w+)`", g["expr"])
            kind = {1: "field", 2: "product" if " times " in g["expr"] else "diff"}[len(parts)]
            out.append({"kind": "sum", "t": g["t"], "a": g["a"], "expr": kind, "f1": parts[0], "f2": parts[1] if len(parts) > 1 else None})
        else:
            out.append(dict(g, kind=fam))
    return out


def get_path(args, path):
    cur = args
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def cents(x):
    return int(round(float(x) * 100))


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def entries(args, a):
    v = args.get(a)
    return v if isinstance(v, list) and all(isinstance(e, dict) for e in v) else None


def term_cents(rule, e):
    """what one array entry adds to a sum rule, in hundredths; None when the entry lacks a number"""
    v1, v2 = e.get(rule["f1"]), e.get(rule.get("f2") or "")
    if not is_num(v1) or (rule["expr"] != "field" and not is_num(v2)):
        return None
    if rule["expr"] == "field":
        return cents(v1)
    return v1 * cents(v2) if rule["expr"] == "product" else (v1 - v2) * 100


def sum_cents(rule, ents):
    terms = [term_cents(rule, e) for e in ents]
    return None if any(t is None for t in terms) else sum(terms)


def rule_holds(rule, args):
    """True when the call keeps the rule; a rule about something the call does not give is not broken"""
    k = rule["kind"]
    if k == "date_order":
        (ha, a), (hb, b) = get_path(args, rule["a"]), get_path(args, rule["b"])
        if not (ha and hb and isinstance(a, str) and isinstance(b, str)):
            return True
        return a < b if rule["strict"] else a <= b
    if k == "only_when":
        hx, _ = get_path(args, rule["x"])
        if not hx:
            return True
        hy, y = get_path(args, rule["y"])
        return hy and y == rule["v"]
    if k == "one_of":
        if not isinstance(args.get(rule["p"].split(".")[0]), dict):
            return True
        return get_path(args, rule["p"])[0] != get_path(args, rule["q"])[0]
    if k == "sum":
        ents, (ht, t) = entries(args, rule["a"]), get_path(args, rule["t"])
        if ents is None or not (ht and is_num(t)):
            return True
        s = sum_cents(rule, ents)
        return s is None or cents(t) == s
    if k == "count":
        (hn, n), arr = get_path(args, rule["n"]), args.get(rule["a"])
        return not (hn and isinstance(n, int) and isinstance(arr, list)) or n == len(arr)
    if k == "within":
        ents, (hl, lo), (hh, hi) = entries(args, rule["a"]), get_path(args, rule["lo"]), get_path(args, rule["hi"])
        if ents is None or not (hl and hh and isinstance(lo, str) and isinstance(hi, str)):
            return True
        return all(not isinstance(e.get(rule["f"]), str) or lo <= e[rule["f"]] <= hi for e in ents)
    ents = entries(args, rule["a"])                                          # elem_order
    return ents is None or all(not (isinstance(e.get(rule["hi"]), int) and isinstance(e.get(rule["lo"]), int)) or e[rule["hi"]] > e[rule["lo"]] for e in ents)


# ----------------------------------------------------------------------------------------------------------------
# the v2 tools: top-level scalars (as in v1), one nested object (name, e-mail, phone), one array of objects, one computed
# parameter and the rules that link them
# ----------------------------------------------------------------------------------------------------------------
LIB2 = {}
EMAIL_PART = [" at {email}", " (e-mail {email})", " with e-mail {email}", " reachable at {email}"]
PHONE_PART = [" on {phone}", " (phone {phone})", " with phone {phone}", " reachable on {phone}"]


def generic_units():
    return [
        ID("reference", "RF", 5, "Reference of the requester.",
           ["with reference {v}", "under reference {v}", "referenced as {v}", "quoting reference {v}"]),
        ID("cost_centre", "CC", 3, "Cost centre to charge.",
           ["charged to cost centre {v}", "booked on cost centre {v}", "against cost centre {v}", "assigned to cost centre {v}"]),
        TEXT("approver", "person", "Person who approved the request.",
             ['approved by "{v}"', 'with approval from "{v}"', 'signed off by "{v}"', 'authorised by "{v}"']),
        ENUM("region", ["north", "south", "east", "west", "central"], ["coastal", "inland", "remote"], "Sales region.",
             ["for the {v} region", "in region {v}", "handled by the {v} office", "listed under the {v} region"], free=True),
        FLAG("urgent", "Whether the request is urgent.", ["marked urgent", "flagged as urgent", "treated as urgent", "as an urgent matter"],
             ["not urgent", "with no urgency", "as a routine matter", "without any rush"]),
        FLAG("notify", "Whether the requester is notified.",
             ["with a notification to the requester", "keeping the requester informed", "telling the requester", "letting the requester know"],
             ["without notifying the requester", "with no notification to the requester", "keeping the requester out of it",
              "with the requester not told"]),
        TEXT("memo", "title", "Short memo for the records.",
             ['with the memo "{v}"', 'noting "{v}"', 'adding the remark "{v}"', 'with the comment "{v}"']),
        ENUM("language", ["en", "de", "fr", "nl"], ["es", "it", "pl"], "Language of the confirmation, as a two-letter ISO 639-1 code.",
             ["confirmed in {v}", "with the confirmation in {v}", "answered in {v}", "replying in {v}"], free=True,
             names={"en": "English", "de": "German", "fr": "French", "nl": "Dutch", "es": "Spanish", "it": "Italian", "pl": "Polish"})]


def contact_object(name, desc, base):
    return dict(kind="object", name=name, desc=desc, base=base, req=False, free=False,
                fields=[F_text("name", "person", "Full name."), dict(kind="email", name="email", desc="E-mail address."),
                        dict(kind="phone", name="phone", desc="Phone number.")], required=["name"])


def lines_unit(name, desc, fields, required, optional, elem, lead, currency=None, plural=None, pair=None):
    return dict(kind="lines", name=name, desc=desc, fields=fields, required=required, optional=optional, elem=elem, lead=lead,
                currency=currency, plural=plural, pair=pair, req=True, free=False)


def computed_unit(name, ctype, desc):
    return dict(kind="computed", name=name, ctype=ctype, desc=desc, req=True, free=False)


def tool2(name, summary, openers, scalars, obj, lines, computed, rules):
    units = scalars + generic_units() + [obj, lines, computed]
    LIB2[name] = dict(tool=name, summary=summary, openers=openers, units=units, rules=rules)


CUR_ENUM = ["EUR", "USD", "GBP"]
tool2("create_order", "Create a customer order with one or more line items.",
      ["Please create an order", "I would like to place an order", "Can you enter an order for me", "Set up an order for us"],
      [ID("customer_id", "CU", 4, "Customer who orders.",
          ["for customer {v}", "on behalf of customer {v}", "placed by customer {v}", "billed to customer {v}"]),
       ENUM("channel", ["web", "partner", "store", "agent"], ["kiosk", "mail", "fax"], "Sales channel of the order.",
            ["through the {v} channel", "via the {v} channel", "booked on the {v} channel", "coming from the {v} channel"], free=True),
       CODE("discount_code", "Discount code of the customer.",
            ["using discount code {v}", "with discount code {v}", "applying the code {v}", "quoting discount code {v}"]),
       DATE("order_date", "Day on which the order is entered.", ["dated {v}", "entered on {v}", "with order date {v}", "placed on {v}"]),
       DATE("delivery_date", "Day on which the goods should arrive.",
            ["for delivery on {v}", "to be delivered on {v}", "arriving on {v}", "with delivery on {v}"]),
       ENUM("shipping", ["standard", "express", "pickup"], ["drone", "freight", "courier"], "Shipping method.",
            ["with {v} shipping", "shipped as {v}", "using {v} shipping", "on {v} shipping terms"], free=True),
       FLAG("gift", "Whether the order is gift wrapped.", ["wrapped as a gift", "with gift wrapping", "packed as a present", "gift wrapping included"],
            ["without gift wrapping", "left unwrapped", "with no gift wrapping", "as an ordinary parcel"])],
      contact_object("contact", "Person to contact about the order.",
                     ['contact person "{name}"', 'with "{name}" as the contact', 'ask for "{name}"', 'contact name "{name}"']),
      lines_unit("items", "Order lines.",
                 [F_id("sku", "KX", 4, "Catalogue number of the article."), F_int("quantity", 1, 20, "Number of units.", words=True),
                  F_amount("unit_price", 1, 500, "Price of one unit."), F_flag("boxed", "Whether this line is packed in a box of its own.")],
                 ["sku", "quantity", "unit_price"], ["boxed"],
                 ["{quantity} of SKU {sku} at {unit_price} {currency} each", "{quantity} units of {sku} priced at {unit_price} {currency} apiece",
                  "{quantity} pieces of {sku} at {unit_price} {currency} per piece",
                  "{sku} in a quantity of {quantity} at {unit_price} {currency} each"],
                 ["The order lines are: {els}.", "The order should contain {els}.", "Lines: {els}.", "The goods are {els}."],
                 currency=CUR_ENUM),
      computed_unit("total", "number", "Total of all order lines in the currency of the order."),
      [("date_order", "order_date", "delivery_date"), ("only_when", "discount_code", "channel", "partner"),
       ("one_of", "contact.email", "contact.phone"), ("sum", "total", "items", "product", "quantity", "unit_price")])

tool2("schedule_shifts", "Schedule staff shifts for a team over a period.",
      ["Please schedule some shifts", "I need a rota entered", "Can you plan shifts for a crew", "Roster the following shifts"],
      [ID("team_id", "TM", 3, "Team that works the shifts.",
          ["for team {v}", "covering team {v}", "on behalf of team {v}", "assigned to team {v}"]),
       DATE("period_start", "First day of the period.",
            ["starting on {v}", "beginning on {v}", "with the period opening on {v}", "running from {v}"]),
       DATE("period_end", "Last day of the period.", ["ending on {v}", "until {v}", "with the period closing on {v}", "through {v}"]),
       ENUM("site", ["north", "south", "harbor", "campus"], ["airport", "depot", "annex"], "Site where the team works.",
            ["at the {v} site", "on the {v} site", "based at the {v} site", "for the {v} site"], free=True),
       INT("min_staff", 1, 6, "Minimum number of staff members per shift.",
           ["with at least {v} staff member{s} per shift", "needing {v} staff member{s} per shift",
            "requiring {v} staff member{s} on each shift", "staffed by {v} staff member{s} per shift"], free=True),
       FLAG("overtime_ok", "Whether overtime is allowed.", ["overtime allowed", "with overtime permitted", "allowing overtime", "overtime is fine"],
            ["no overtime", "with overtime forbidden", "disallowing overtime", "overtime not permitted"])],
      contact_object("supervisor", "Supervisor of the rota.",
                     ['supervisor "{name}"', 'supervised by "{name}"', 'with "{name}" in charge', 'overseen by "{name}"']),
      lines_unit("shifts", "Shifts of the rota.",
                 [F_id("employee_id", "EM", 4, "Employee who works the shift."), F_date("day", "Day of the shift."),
                  F_int("start_hour", 0, 23, "Hour at which the shift starts."), F_int("end_hour", 1, 24, "Hour at which the shift ends."),
                  F_enum("role", ["cashier", "driver", "cook", "guard"], ["manager", "trainee", "cleaner"], "Role during the shift.")],
                 ["employee_id", "day", "start_hour", "end_hour"], ["role"],
                 ["{employee_id} on {day} from {start_hour}:00 to {end_hour}:00",
                  "employee {employee_id} working {start_hour}:00 to {end_hour}:00 on {day}",
                  "a shift for {employee_id} on {day}, {start_hour}:00 until {end_hour}:00",
                  "{employee_id} covering {day} between {start_hour}:00 and {end_hour}:00"],
                 ["The shifts are: {els}.", "Please schedule {els}.", "Shifts: {els}.", "The rota consists of {els}."],
                 pair=("start_hour", "end_hour")),
      computed_unit("total_hours", "integer", "Total number of hours of all shifts."),
      [("date_order", "period_start", "period_end"), ("within", "shifts", "day", "period_start", "period_end"),
       ("elem_order", "shifts", "end_hour", "start_hour"), ("sum", "total_hours", "shifts", "diff", "end_hour", "start_hour"),
       ("one_of", "supervisor.email", "supervisor.phone")])

tool2("book_trip", "Book a trip for a group of passengers.",
      ["Please book a trip", "I need a journey booked", "Can you arrange travel for a group", "Set up a trip for us"],
      [ID("booking_ref", "BK", 5, "Booking the trip belongs to.",
          ["under booking {v}", "for the booking {v}", "against booking {v}", "tied to booking {v}"]),
       DATE("depart_on", "Day of departure.", ["departing on {v}", "leaving on {v}", "with departure on {v}", "setting off on {v}"]),
       DATE("return_on", "Day of return.", ["returning on {v}", "coming back on {v}", "with the return on {v}", "arriving home on {v}"]),
       ENUM("cabin", ["economy", "premium", "business"], ["first", "basic", "shuttle"], "Cabin class.",
            ["in {v} class", "travelling {v} class", "booked in the {v} cabin", "in the {v} cabin"], free=True),
       CODE("upgrade_code", "Code for a cabin upgrade.",
            ["using upgrade code {v}", "with upgrade code {v}", "applying code {v}", "quoting upgrade code {v}"]),
       FLAG("insurance", "Whether travel insurance is added.",
            ["with travel insurance", "insured for the trip", "including insurance", "covered by insurance"],
            ["without insurance", "uninsured", "with no travel insurance", "not insured"]),
       MONEY("budget", "budget_currency", 50, 20000, CUR_ENUM, "Highest total price accepted.", "Currency of budget.",
             ["with a budget of {amount} {cur}", "for no more than {amount} {cur} in total", "up to {amount} {cur}",
              "with a ceiling of {amount} {cur}"])],
      contact_object("traveller_contact", "Lead traveller of the group.",
                     ['main traveller "{name}"', 'booked for "{name}"', 'with "{name}" as lead traveller', 'lead traveller "{name}"']),
      lines_unit("passengers", "Passengers of the trip.",
                 [F_text("name", "person", "Full name of the passenger."), F_int("age", 0, 110, "Age in years."),
                  F_enum("seat", ["window", "aisle", "any"], ["middle", "exit", "front"], "Seat preference.")],
                 ["name", "age"], ["seat"],
                 ['"{name}", aged {age}', 'the passenger "{name}" ({age} years old)', '"{name}" who is {age}', '{age}-year-old "{name}"'],
                 ["The passengers are: {els}.", "Travelling: {els}.", "The group consists of {els}.", "Passengers: {els}."]),
      computed_unit("party_size", "integer", "Number of passengers."),
      [("date_order", "depart_on", "return_on"), ("only_when", "upgrade_code", "cabin", "premium"),
       ("count", "party_size", "passengers"), ("one_of", "traveller_contact.email", "traveller_contact.phone")])

tool2("file_claim", "File an insurance claim with a list of cost items.",
      ["Please file a claim", "I need a claim entered", "Can you register an insurance claim", "Open a claim for us"],
      [ID("claim_ref", "CL", 5, "Reference of the claim.",
          ["for claim {v}", "under claim number {v}", "registered as claim {v}", "referring to claim {v}"]),
       ID("policy_id", "PL", 4, "Insurance policy of the claimant.",
          ["on policy {v}", "under policy {v}", "against policy {v}", "covered by policy {v}"]),
       DATE("incident_date", "Day on which the damage occurred.",
            ["for an incident on {v}", "occurring on {v}", "that happened on {v}", "relating to {v}"]),
       DATE("filed_date", "Day on which the claim is filed.", ["filed on {v}", "submitted on {v}", "lodged on {v}", "reported on {v}"]),
       ENUM("claim_type", ["fire", "water", "theft", "storm"], ["flood", "vandalism", "subsidence"], "Kind of damage.",
            ["classified as {v} damage", "of the type {v}", "under the heading {v}", "for {v} damage"], free=True),
       CODE("waiver_code", "Code that waives the excess.",
            ["with waiver code {v}", "quoting waiver code {v}", "using the waiver {v}", "applying waiver code {v}"]),
       TEXT("adjuster", "person", "Adjuster who handles the claim.",
            ['assigned to adjuster "{v}"', 'handled by adjuster "{v}"', 'with adjuster "{v}"', 'under adjuster "{v}"'])],
      contact_object("claimant", "Person who files the claim.",
                     ['claimant "{name}"', 'submitted by "{name}"', 'on behalf of "{name}"', 'with "{name}" as claimant']),
      lines_unit("expenses", "Cost items of the claim.",
                 [F_id("item_ref", "EX", 4, "Reference of the cost item."),
                  F_enum("kind", ["travel", "repair", "medical", "other"], ["legal", "rental", "storage"], "Kind of cost."),
                  F_amount("amount", 1, 2000, "Amount of the cost item."), F_flag("receipt", "Whether a receipt is attached.")],
                 ["item_ref", "kind", "amount"], ["receipt"],
                 ["{kind} expense {item_ref} of {amount} {currency}", "an item {item_ref} ({kind}) costing {amount} {currency}",
                  "{amount} {currency} for {kind} item {item_ref}", "the {kind} bill {item_ref} for {amount} {currency}"],
                 ["The expenses are: {els}.", "Charges: {els}.", "The claim covers {els}.", "Expenses: {els}."],
                 currency=CUR_ENUM),
      computed_unit("claimed_total", "number", "Total of all cost items in the given currency."),
      [("date_order", "incident_date", "filed_date"), ("only_when", "waiver_code", "claim_type", "storm"),
       ("sum", "claimed_total", "expenses", "field", "amount", None), ("one_of", "claimant.email", "claimant.phone")])

tool2("plan_delivery", "Plan the stops of a delivery route.",
      ["Please plan a delivery", "I need a round entered", "Can you set up a delivery run", "Organise a delivery for us"],
      [ID("route_id", "RT", 4, "Route that serves the stops.",
          ["on route {v}", "for route {v}", "along route {v}", "assigned to route {v}"]),
       DATE("ship_date", "Day on which the goods leave the depot.",
            ["shipping on {v}", "leaving the depot on {v}", "dispatched on {v}", "with dispatch on {v}"]),
       DATE("deliver_by", "Latest day of delivery.",
            ["delivered by {v}", "to arrive by {v}", "with a delivery deadline of {v}", "due at the last drop-off by {v}"]),
       ENUM("vehicle", ["van", "truck", "bike"], ["boat", "plane", "tram"], "Type of vehicle.",
            ["using a {v}", "by {v}", "on a {v}", "with a {v}"], free=True),
       ENUM("zone", ["domestic", "export"], ["transit", "local", "bonded"], "Customs zone of the delivery.",
            ["in the {v} zone", "for the {v} zone", "as {v} freight", "within the {v} zone"], free=True),
       CODE("customs_code", "Customs declaration code.",
            ["declared with customs code {v}", "with customs code {v}", "quoting code {v} for customs", "using customs code {v}"]),
       FLAG("fragile", "Whether the goods are fragile.", ["marked as fragile", "handled as fragile goods", "flagged fragile", "labelled fragile"],
            ["not fragile", "as ordinary goods", "with no fragile goods", "with nothing fragile inside"])],
      contact_object("driver", "Driver of the route.",
                     ['driver "{name}"', 'driven by "{name}"', 'with "{name}" at the wheel', 'assigned to "{name}"']),
      lines_unit("stops", "Stops of the route.",
                 [F_id("stop_id", "ST", 3, "Identifier of the stop."), F_int("parcels", 1, 40, "Number of parcels for the stop.", words=True),
                  F_int("window_start", 0, 23, "Hour at which delivery may start."), F_int("window_end", 1, 24, "Hour by which delivery must be done."),
                  F_flag("signature", "Whether a signature is required.")],
                 ["stop_id", "parcels", "window_start", "window_end"], ["signature"],
                 ["{parcels} parcel{s} to stop {stop_id} between {window_start}:00 and {window_end}:00",
                  "stop {stop_id} receiving {parcels} parcel{s} within the {window_start}:00 to {window_end}:00 window",
                  "{parcels} parcel{s} for {stop_id}, to be delivered from {window_start}:00 until {window_end}:00",
                  "{stop_id} ({parcels} parcel{s}, window {window_start}:00 to {window_end}:00)"],
                 ["The stops are: {els}.", "Round: {els}.", "Drop off {els}.", "The delivery plan has {els}."], plural="parcels",
                 pair=("window_start", "window_end")),
      computed_unit("load_total", "integer", "Total number of parcels of all stops."),
      [("date_order", "ship_date", "deliver_by"), ("only_when", "customs_code", "zone", "export"),
       ("elem_order", "stops", "window_end", "window_start"), ("sum", "load_total", "stops", "field", "parcels", None),
       ("one_of", "driver.email", "driver.phone")])
TOOLS2 = list(LIB2)

# ----------------------------------------------------------------------------------------------------------------
# gen_v4: no word of the request may equal a parameter name of the schema without referring to that parameter, and the filler
# sentences come from a larger pool.  The same function judges the library (every template of every tool against every name the
# tool can have) and every item (the pieces of its request against the names of its own schema).
# ----------------------------------------------------------------------------------------------------------------
ADDONS2 = ["Thanks.", "Thanks in advance.", "Many thanks.", "Much appreciated.", "That would be a great help.",
           "I am grateful for the help.", "Good to have this sorted.", "Hope this is clear.",
           "This is for the autumn planning round.", "This is needed for the spring planning round.",
           "It is part of the yearly planning.", "It is needed for the yearly meeting.",
           "I will look at the outcome later.", "I will go through the output later.",
           "The manager already knows about it.", "My colleagues are aware of this.",
           "This was agreed in the last meeting.", "It follows what we discussed earlier.",
           "Nothing else is needed from my side.", "This is a one-off.", "Sorry for the short notice.",
           "Apologies for the late request.", "I appreciate the quick help.", "Please keep this between us.",
           "This should not take long.", "I will explain the background later.", "A colleague asked me to do this.",
           "I have been meaning to get this done.", "It has been on my list for a while.", "This is the last thing on my list.",
           "I am writing this between meetings.", "Things are calm on my side at the moment.",
           "We have been waiting for this for some time.", "This comes up every season.", "The same thing came up last season.",
           "I hope the system is behaving.", "Have a good one.", "This will make things easier for everyone.",
           "I am glad we can do this.", "We do this a few times a year.", "My manager asked me to take care of it.",
           "I am doing this for the first time.", "Things have been busy this month.", "It is a quiet week for us."]
STOP_PARTS = {"id", "ref", "by", "on", "of", "ok", "min", "max"}           # parts of a name that are function words, not name words
_NW = {}


def forms(w):
    out = {w, w + "s"}
    if w.endswith("ies"):
        out.add(w[:-3] + "y")
    if w.endswith("y"):
        out.add(w[:-1] + "ies")
    if w.endswith("es"):
        out.add(w[:-2])
    if w.endswith("s"):
        out.add(w[:-1])
    return out


def name_words(leaf):
    """the words that stand for a parameter name: the whole name (singular / plural) and every part split at the underscores"""
    if leaf not in _NW:
        ws = set(forms(leaf.replace("_", "")))
        for p in leaf.split("_"):
            if p not in STOP_PARTS and len(p) >= 3:
                ws |= forms(p)
        _NW[leaf] = frozenset(ws)
    return _NW[leaf]


def schema_leaves(schema):
    """names of all properties of a schema at every level (arguments, nested object, entries of the array)"""
    out = set()

    def walk(node):
        if node.get("type") == "object":
            for k, v in node["properties"].items():
                out.add(k)
                walk(v)
        elif node.get("type") == "array":
            walk(node["items"])
    walk(schema["parameters"])
    return out


def pool_leaves(dom):
    """every name that a schema of this tool can contain"""
    out = {"currency"}
    for u in dom["units"]:
        out.add(u["name"])
        if u["kind"] == "money":
            out.add(u["cur_name"])
        elif u["kind"] in ("object", "lines"):
            out |= {f["name"] for f in u["fields"]}
    return out


def piece_hits(text, owners, names, theme):
    """[(word, names)] of the words of one piece of the request that equal a parameter name without being the piece's own clause:
    owners = names of the parameters that the piece sets (its words are that parameter's own), theme = words of the tool's name"""
    t = re.sub(DATE_RX, " ", re.sub(r"\{[a-z_]+\}", " ", text))                    # date expressions say "day" and "date"
    own = set()
    for o in owners:
        own |= name_words(o)
    out = []
    for w in re.findall(r"[a-z]+", t.lower()):
        if w in theme or w in own:
            continue
        hit = sorted(n for n in names if w in name_words(n))
        if hit:
            out.append((w, hit))
    return out


def theme_words(tool):
    out = set()
    for p in tool.split("_"):
        out |= forms(p)
    return out


def request_pieces(spec):
    """[(text, names of the parameters the piece sets, source)]: the opener, one clause per named scalar / flag / amount / object, the lead-in
    of the array, one text per array entry and the filler sentence; together they are the request"""
    dom, phr, named = LIB2[spec["tool"]], spec["phrasing"], spec["named"]
    by = {u["name"]: u for u in dom["units"]}
    out = [(dom["openers"][phr["opener"]], set(), "opener")]
    for n in phr["order"]:
        u, i, k = by[n], phr["variants"][n], by[n]["kind"]
        if k == "flag":
            c, own = (u["yes"] if named[n] else u["no"])[i], {n}
        elif k == "money":
            c, own = u["clauses"][i].replace("{amount}", "%.2f" % named[n]).replace("{cur}", named[u["cur_name"]]), {n, u["cur_name"]}
        elif k == "object":
            c = object_clause(u, named[n], i)
            own = {n, "name"} | ({"email"} if "email" in named[n] else set()) | ({"phone"} if "phone" in named[n] else set())
        else:
            c, own = fill2(u["clauses"][i], u, named[n], phr, n), {n}
        out.append((c, own, "clause " + n))
    lines_u = next(u for u in dom["units"] if u["kind"] == "lines")
    pre, post = lines_u["lead"][phr["lead"]].split("{els}")
    out.append((pre + post, {lines_u["name"]}, "lead"))
    for i, ent in enumerate(named[lines_u["name"]]):
        out.append((elem_text(lines_u, ent, i, phr, named.get("currency")),
                    {lines_u["name"]} | set(lines_u["required"]) | {"currency"}, "entry"))
    if phr["addon"] is not None:
        out.append((ADDONS2[phr["addon"]], set(), "filler"))
    return out


def name_collisions(spec):
    """[(word, names, source, text)] of the words of the request that equal a parameter name of the schema without referring to it"""
    names, theme = schema_leaves(spec["schema"]), theme_words(spec["tool"])
    return [(w, hit, src, text) for text, owners, src in request_pieces(spec) for w, hit in piece_hits(text, owners, names, theme)]


def library_collisions():
    """the same test on the whole library: every phrasing of every tool against every name that tool can have (a clean library cannot
    produce a collision from its templates; invented names and e-mail domains avoid the name words through FORBID)"""
    bad = []
    for tool, dom in LIB2.items():
        names, theme, pieces = pool_leaves(dom), theme_words(tool), []
        pieces += [(o, set(), "opener") for o in dom["openers"]]
        for u in dom["units"]:
            n, k = u["name"], u["kind"]
            if k == "flag":
                pieces += [(t, {n}, "clause " + n) for t in u["yes"] + u["no"]]
            elif k == "money":
                pieces += [(t, {n, u["cur_name"]}, "clause " + n) for t in u["clauses"]]
            elif k == "object":
                for i, b in enumerate(u["base"]):
                    pieces += [(b, {n, "name"}, "clause " + n), (b + EMAIL_PART[i], {n, "name", "email"}, "clause " + n),
                               (b + PHONE_PART[i], {n, "name", "phone"}, "clause " + n)]
            elif k == "lines":
                pieces += [(t, {n} | set(u["required"]) | {"currency"}, "entry " + n) for t in u["elem"]]
                pieces += [(t.replace("{els}", " "), {n}, "lead " + n) for t in u["lead"]]
                for f in u["fields"]:
                    if f["kind"] == "enum":
                        pieces += [(w, {n, f["name"]}, "value " + f["name"]) for w in f["values"] + f["wrong"]]
            elif k != "computed":
                pieces += [(t, {n}, "clause " + n) for t in u["clauses"]]
                if k == "enum":
                    pieces += [((u.get("names") or {}).get(w, w), {n}, "value " + n) for w in u["values"] + u["wrong"]]
        pieces += [(a, set(), "filler") for a in ADDONS2]
        for text, owners, src in pieces:
            bad += [(tool, src, w, hit, text) for w, hit in piece_hits(text, owners, names, theme)]
    return bad


def all_name_words():
    return frozenset(w for dom in LIB2.values() for leaf in pool_leaves(dom) for w in name_words(leaf))


def n_props2(u):
    k = u["kind"]
    return 2 if k == "money" or (k == "lines" and u["currency"]) else 1


def make_rule(rng, cand):
    k = cand[0]
    r = {"kind": k, "variant": rng.randrange(4)}
    if k == "date_order":
        r.update(a=cand[1], b=cand[2], strict=rng.random() < 0.4)
    elif k == "only_when":
        r.update(x=cand[1], y=cand[2], v=cand[3])
    elif k == "one_of":
        r.update(p=cand[1], q=cand[2])
    elif k == "sum":
        r.update(t=cand[1], a=cand[2], expr=cand[3], f1=cand[4], f2=cand[5])
    elif k == "count":
        r.update(n=cand[1], a=cand[2])
    elif k == "within":
        r.update(a=cand[1], f=cand[2], lo=cand[3], hi=cand[4])
    else:
        r.update(a=cand[1], hi=cand[2], lo=cand[3])
    return r


def rule_units(r):
    """names of the top-level units that a rule talks about"""
    k = r["kind"]
    names = {"date_order": [r.get("a"), r.get("b")], "only_when": [r.get("x"), r.get("y")], "one_of": [r.get("p", "").split(".")[0]],
             "sum": [r.get("t"), r.get("a")], "count": [r.get("n"), r.get("a")], "within": [r.get("a"), r.get("lo"), r.get("hi")],
             "elem_order": [r.get("a")]}[k]
    return {n for n in names if n}


def pick_units2(rng, dom, P, force=None):
    """-> (units in schema order, rules): the array is always there, then the units that the rules need, the object from 9
    properties on, then scalars until the schema has exactly P top-level properties"""
    pool = dom["units"]
    by = {u["name"]: u for u in pool}
    lines_u = next(u for u in pool if u["kind"] == "lines")
    obj_u = next(u for u in pool if u["kind"] == "object")
    scalars = [u for u in pool if u["kind"] not in ("lines", "object", "computed")]
    for _ in range(300):
        cands = rng.sample(dom["rules"], min(N_RULES2[P], len(dom["rules"])))
        if force and not any(c[0] == force for c in cands):                 # the family of rule that a rule deviation will break
            cands[0] = rng.choice([c for c in dom["rules"] if c[0] == force])
        rules = [make_rule(rng, c) for c in dict.fromkeys(cands)]
        need = {lines_u["name"]}
        for r in rules:
            need |= rule_units(r)
        if P >= 9 and rng.random() < 0.8:
            need.add(obj_u["name"])
        total = sum(n_props2(by[n]) for n in need)
        if total > P:
            continue
        chosen = set(need)
        rest = [u for u in scalars if u["name"] not in chosen]
        rng.shuffle(rest)
        for u in rest:
            if total + n_props2(u) <= P:
                chosen.add(u["name"])
                total += n_props2(u)
            if total == P:
                break
        if total == P:
            return [u for u in pool if u["name"] in chosen], rules
    raise RuntimeError("no unit selection")


def build_schema2(dom, units, rules, roles, maxitems):
    props, required = {}, []
    for u in units:
        k, req = u["kind"], roles[u["name"]] == "req"
        if k == "money":
            props[u["name"]] = leaf_schema(dict(u, kind="amount"))
            props[u["cur_name"]] = {"type": "string", "enum": u["curs"], "description": u["cur_desc"]}
            required += [u["name"], u["cur_name"]] if req else []
            continue
        if k == "object":
            props[u["name"]] = {"type": "object", "description": u["desc"], "required": u["required"], "additionalProperties": False,
                                "properties": {f["name"]: leaf_schema(f) for f in u["fields"]}}
        elif k == "lines":
            props[u["name"]] = {"type": "array", "description": u["desc"], "minItems": 1, "maxItems": maxitems,
                                "items": {"type": "object", "required": u["required"], "additionalProperties": False,
                                          "properties": {f["name"]: leaf_schema(f) for f in u["fields"]}}}
            if u["currency"]:
                props["currency"] = {"type": "string", "enum": u["currency"], "description": "Currency of all prices and amounts of the entries."}
                required += ["currency"] if req else []
        elif k == "computed":
            props[u["name"]] = {"type": u["ctype"], "minimum": 0, "description": u["desc"]}
        else:
            props[u["name"]] = leaf_schema(u)
        required += [u["name"]] if req else []
    props_order = list(props)
    desc = dom["summary"] + "".join(" " + rule2_sentence(r) for r in rules)
    return {"name": dom["tool"], "description": desc,
            "parameters": {"type": "object", "properties": props, "required": [p for p in props_order if p in required],
                           "additionalProperties": False}}


def fmt_json(node, ind=0):
    """schema text: a dict that holds other dicts is spread over lines, a dict of plain values stays on one line"""
    if not (isinstance(node, dict) and any(isinstance(v, dict) for v in node.values())):
        return [json.dumps(node)]
    pad = " " * ind
    lines, keys = ["{"], list(node)
    for i, k in enumerate(keys):
        sub = fmt_json(node[k], ind + 2)
        sub[0] = f"{pad}  {json.dumps(k)}: {sub[0]}"
        if i < len(keys) - 1:
            sub[-1] += ","
        lines += sub
    lines.append(pad + "}")
    return lines


def involved(rules):
    out = set()
    for r in rules:
        out |= rule_units(r)
    return out


def gen_scalar2(rng, u):
    k = u["kind"]
    if k == "date":
        return gen_target(rng).isoformat()
    if k == "code":
        return gen_code(rng)
    return gen_value(rng, u)                                    # id, int, enum, flag, text; an amount returns (amount, currency)


def make_email(rng, name):
    first, last = name.lower().split(" ")
    return f"{first}.{last}@{word(rng, 2, 2)}.example"


def make_phone(rng):
    return "555-%d" % rng.randrange(1000, 9999)


def computed_value(rule, ents, ctype):
    if rule["kind"] == "count":
        return len(ents)
    c = sum_cents(rule, ents)
    return c // 100 if ctype == "integer" else round(c / 100, 2)


def gen_entries(rng, lines_u, e, rules, vals):
    """e entries of the array: the required fields, a few optional ones; hours run forward, days lie inside the period of a `within` rule"""
    within = next((r for r in rules if r["kind"] == "within"), None)
    used = {f["name"]: set() for f in lines_u["fields"] if f["kind"] == "id"}
    pair = lines_u.get("pair")
    ents = []
    for _ in range(e):
        ent = {}
        for f in lines_u["fields"]:
            n = f["name"]
            if n not in lines_u["required"]:
                continue
            v = gen_leaf(rng, f)
            while f["kind"] == "id" and v in used[n]:
                v = gen_leaf(rng, f)
            if f["kind"] == "id":
                used[n].add(v)
            ent[n] = v
        if pair:
            s = rng.choice([0, rng.randint(0, 22)]) if rng.random() < 0.2 else rng.randint(0, 22)
            ent[pair[0]] = s
            ent[pair[1]] = 24 if rng.random() < 0.2 else rng.randint(s + 1, 24)
        if within:
            lo, hi = datetime.date.fromisoformat(vals[within["lo"]]), datetime.date.fromisoformat(vals[within["hi"]])
            ent[within["f"]] = (rng.choice([lo, hi]) if rng.random() < 0.25 else lo + datetime.timedelta(days=rng.randint(0, (hi - lo).days))).isoformat()
        for f in lines_u["fields"]:
            if f["name"] not in lines_u["required"] and rng.random() < 0.3:
                ent[f["name"]] = gen_leaf(rng, f)
        ents.append({f["name"]: ent[f["name"]] for f in lines_u["fields"] if f["name"] in ent})
    return ents


def make_base2(rng, dom, P, force=None):
    """a correct call with its request: the valid base of a pair (`force`: a family of rule that the rules must include)"""
    units, rules = pick_units2(rng, dom, P, force)
    by = {u["name"]: u for u in units}
    lines_u = next(u for u in units if u["kind"] == "lines")
    obj_u = next((u for u in units if u["kind"] == "object"), None)
    rk = {r["kind"] for r in rules}
    inv = involved(rules)
    only = next((r for r in rules if r["kind"] == "only_when"), None)
    x_present = rng.random() < 0.5 and force != "only_when"            # a call that breaks `only_when` starts without the code
    roles = {}
    for u in units:
        n, k = u["name"], u["kind"]
        if k in ("lines", "computed"):
            roles[n] = "req"
        elif k == "object":
            roles[n] = "req" if "one_of" in rk else rng.choice(["req", "named"])
        elif only and n == only["x"]:
            roles[n] = "named" if x_present else "unused"
        elif only and n == only["y"]:
            roles[n] = rng.choice(["req", "named"])
        elif n in inv:
            roles[n] = "req"
        else:
            r = rng.random()
            if k == "code":
                roles[n] = "named" if r < 0.3 else "unused"
            elif u["req"]:
                p_req = 0.75 if k in ("id", "date") else 0.45                  # identifiers and dates are usually required
                roles[n] = "req" if r < p_req else ("named" if r < p_req + 0.25 else ("free" if u["free"] and r < p_req + 0.42 else "unused"))
            else:
                roles[n] = "named" if r < 0.45 else ("free" if r < 0.75 else "unused")
    vals = {u["name"]: gen_scalar2(rng, u) for u in units if u["kind"] not in ("lines", "object", "computed") and roles[u["name"]] != "unused"}
    for r in rules:
        if r["kind"] == "date_order":
            gap0 = 1 if r["strict"] else 0
            a, b = datetime.date.fromisoformat(vals[r["a"]]), datetime.date.fromisoformat(vals[r["b"]])
            if (b - a).days < gap0 or rng.random() < 0.3:
                gap = gap0 if rng.random() < 0.6 else rng.randint(gap0, 40)
                vals[r["b"]] = (a + datetime.timedelta(days=gap)).isoformat()
        elif r["kind"] == "only_when":
            if x_present:
                vals[r["y"]] = r["v"]
            else:
                while vals[r["y"]] == r["v"]:
                    vals[r["y"]] = gen_scalar2(rng, by[r["y"]])
    for r in rules:
        if r["kind"] == "within":
            lo, hi = datetime.date.fromisoformat(vals[r["lo"]]), datetime.date.fromisoformat(vals[r["hi"]])
            if (hi - lo).days < 3:
                vals[r["hi"]] = (lo + datetime.timedelta(days=rng.randint(3, 25))).isoformat()
    obj_val = None
    if obj_u is not None:
        name = person(rng)
        form = rng.choice(["email", "phone"]) if "one_of" in rk else rng.choice(["name", "email", "phone"])
        obj_val = {"name": name}
        if form == "email":
            obj_val["email"] = make_email(rng, name)
        elif form == "phone":
            obj_val["phone"] = make_phone(rng)
    e = rng.randint(*N_ELEMS2[P])
    maxitems = min(8, e + rng.choice([0, 1, 1, 2]))
    ents = gen_entries(rng, lines_u, e, rules, vals)
    cur = rng.choice(lines_u["currency"]) if lines_u["currency"] else None
    schema = build_schema2(dom, units, rules, roles, maxitems)
    props = schema["parameters"]["properties"]
    cv, nv = {}, {}
    for u in units:
        n, k, r = u["name"], u["kind"], roles[u["name"]]
        if k == "lines":
            cv[n], nv[n] = ents, [{f: ent[f] for f in lines_u["required"]} for ent in ents]
            if cur:
                cv["currency"], nv["currency"] = cur, cur
        elif k == "object":
            cv[n] = obj_val
            if r in ("req", "named"):
                nv[n] = dict(obj_val)
        elif k == "computed":
            rule = next(x for x in rules if x.get("t") == n or x.get("n") == n)
            cv[n] = computed_value(rule, ents, u["ctype"])
        elif r != "unused":
            if k == "money":
                cv[n], cv[u["cur_name"]] = vals[n]
                if r in ("req", "named"):
                    nv[n], nv[u["cur_name"]] = vals[n]
            else:
                cv[n] = vals[n]
                if r in ("req", "named"):
                    nv[n] = vals[n]
    call = {p: cv[p] for p in props if p in cv}
    named = {p: nv[p] for p in props if p in nv}
    # phrasing of the request
    mentioned = [u["name"] for u in units if u["kind"] not in ("lines", "computed") and roles[u["name"]] in ("req", "named")]
    rng.shuffle(mentioned)
    ids = [n for n in mentioned if by[n]["kind"] == "id"]
    if ids and rng.random() < 0.8:
        mentioned.remove(ids[0])
        mentioned.insert(0, ids[0])
    phr = {"opener": rng.randrange(4), "order": mentioned, "variants": {n: rng.randrange(4) for n in mentioned},
           "addon": rng.randrange(len(ADDONS2)) if rng.random() < 0.4 else None, "lead": rng.randrange(4), "date_forms": {}, "asides": {},
           "elem": [{"variant": rng.randrange(4), "words": rng.random() < 0.5} for _ in ents]}
    for n in mentioned:
        if by[n]["kind"] == "date":
            phr["date_forms"][n] = pick_form(rng, datetime.date.fromisoformat(named[n]))
        elif by[n]["kind"] == "id" and rng.random() < 0.35:
            phr["asides"][n] = [lookalike(rng, named[n]), rng.randrange(4)]
    for i, ent in enumerate(ents):
        for f in lines_u["fields"]:
            if f["name"] in lines_u["required"]:
                path = f"{lines_u['name']}[{i}].{f['name']}"
                if f["kind"] == "date":
                    phr["date_forms"][path] = pick_form(rng, datetime.date.fromisoformat(ent[f["name"]]))
                elif f["kind"] == "id" and rng.random() < 0.3:
                    phr["asides"][path] = [lookalike(rng, ent[f["name"]]), rng.randrange(4)]
    return {"tool": dom["tool"], "params": P, "schema": schema, "rules": rules, "roles": roles, "named": named, "call": call,
            "phrasing": phr, "deviation": None}


# ----------------------------------------------------------------------------------------------------------------
# the request text and its parse
# ----------------------------------------------------------------------------------------------------------------
CONVENTIONS2 = (
    "You are given the schema of a tool, a user request, and the call that an agent proposes for that request.\n"
    "How a call is judged:\n"
    "- Every object (the arguments, a nested object, each entry of an array) must give all parameters listed under its \"required\" and may "
    "not contain a name that is not under its \"properties\".\n"
    "- Every value must have its declared type and, where the schema says so, be one of the \"enum\" values, lie between \"minimum\" and "
    "\"maximum\" (both included), or (for an array) hold between \"minItems\" and \"maxItems\" entries (both included); a \"date\" is "
    "written YYYY-MM-DD.\n"
    "- Every rule in the tool description must hold for the call.\n"
    "- The request fixes the value of every parameter that it names, also when it gives the value indirectly (a date as a calendar rule or "
    "as a number of days from another date, a count as a word); an amount is a number and a currency code, and a price \"each\" is the price "
    "of one unit. An identifier in brackets after another one and marked \"not\" is a look-alike that must not be used. The call must pass "
    "exactly the values that the request fixes, and the entries of an array in the order of the request.\n"
    "- A parameter that the request does not name may be left out or set to any value the schema allows.")


def slot_text(f, v, phr, path, words=False):
    k = f["kind"]
    if k == "id":
        a = phr["asides"].get(path)
        return v + (" " + ASIDE_TEXT[a[1]].format(x=a[0]) if a else "")
    if k == "date":
        return render_date(datetime.date.fromisoformat(v), phr["date_forms"].get(path, {"form": "iso"}))
    if k == "int":
        return numword(v) if (f.get("words") and words and 0 <= v <= 12) else str(v)
    if k == "amount":
        return "%.2f" % v
    if k == "enum" and f.get("names"):
        return f["names"][v]
    return str(v)


def fill2(tmpl, u, v, phr, path):
    text = slot_text(u, v, phr, path)
    plural = "" if (not isinstance(v, int) or isinstance(v, bool) or v == 1) else "s"
    return tmpl.replace("{v}", text).replace("{s}", plural).replace("{a}", "an" if text[:1] in "aeiou" else "a")


def elem_text(lines_u, ent, idx, phr, cur):
    t = lines_u["elem"][phr["elem"][idx]["variant"]]
    fields = {f["name"]: f for f in lines_u["fields"]}

    def rep(m):
        nm = m.group(1)
        if nm == "currency":
            return cur
        if nm == "s":
            return "" if ent[lines_u["plural"]] == 1 else "s"
        return slot_text(fields[nm], ent[nm], phr, f"{lines_u['name']}[{idx}].{nm}", phr["elem"][idx]["words"])
    return re.sub(r"\{([a-z_]+)\}", rep, t)


def object_clause(u, v, i):
    s = u["base"][i].format(name=v["name"])
    if "email" in v:
        s += EMAIL_PART[i].format(email=v["email"])
    elif "phone" in v:
        s += PHONE_PART[i].format(phone=v["phone"])
    return s


def render_request2(spec):
    dom, phr, named = LIB2[spec["tool"]], spec["phrasing"], spec["named"]
    by = {u["name"]: u for u in dom["units"]}
    clauses = []
    for n in phr["order"]:
        u, i, k = by[n], phr["variants"][n], by[n]["kind"]
        if k == "flag":
            clauses.append((u["yes"] if named[n] else u["no"])[i])
        elif k == "money":
            clauses.append(u["clauses"][i].replace("{amount}", "%.2f" % named[n]).replace("{cur}", named[u["cur_name"]]))
        elif k == "object":
            clauses.append(object_clause(u, named[n], i))
        else:
            clauses.append(fill2(u["clauses"][i], u, named[n], phr, n))
    opener = dom["openers"][phr["opener"]]
    end = "?" if opener.startswith("Can you") else "."
    if not clauses:
        s1 = opener + end
    else:
        body = clauses[0] if len(clauses) == 1 else ", ".join(clauses[:-1]) + " and " + clauses[-1]
        s1 = opener + (" " if clauses[0].split()[0] in PREPOSITIONS else ", ") + body + end
    lines_u = next(u for u in dom["units"] if u["kind"] == "lines")
    cur = named.get("currency")
    els = "; ".join(elem_text(lines_u, ent, i, phr, cur) for i, ent in enumerate(named[lines_u["name"]]))
    s2 = lines_u["lead"][phr["lead"]].replace("{els}", els)
    return " ".join([s1, s2] + ([ADDONS2[phr["addon"]]] if phr["addon"] is not None else []))


_RX2 = {}


def request_patterns(tool):
    """compiled patterns of the clause templates of a tool: scalars, the object (three forms), the array entries"""
    if tool in _RX2:
        return _RX2[tool]
    R = {"scalars": {}, "object": None, "lines": None}
    for u in LIB2[tool]["units"]:
        k, n = u["kind"], u["name"]
        if k == "computed":
            continue
        if k == "flag":
            R["scalars"][n] = (u, [(compile_tmpl2(t, {}), True) for t in u["yes"]] + [(compile_tmpl2(t, {}), False) for t in u["no"]])
        elif k == "money":
            slots = {"amount": "(?P<amount>\\d+\\.\\d{2})", "cur": "(?P<cur>[A-Z]{3})"}
            R["scalars"][n] = (u, [(compile_tmpl2(t, slots), None) for t in u["clauses"]])
        elif k == "object":
            name_rx = {"name": '(?P<name>[^"]+)'}
            forms = []
            for form, part, slot in (("email", EMAIL_PART, slot_regex("email", u["fields"][1])), ("phone", PHONE_PART, slot_regex("phone", u["fields"][2])), ("name", None, None)):
                rxs = []
                for i, b in enumerate(u["base"]):
                    t = b + (part[i] if part else "")
                    rxs.append(compile_tmpl2(t, dict(name_rx, **({form: slot} if slot else {}))))
                forms.append((form, rxs))
            R["object"] = (u, forms)
        elif k == "lines":
            slots = {f["name"]: slot_regex(f["name"], f) for f in u["fields"] if f["kind"] != "flag"}
            slots["currency"] = "(?P<currency>[A-Z]{3})"
            R["lines"] = (u, [compile_tmpl2(t, slots) for t in u["elem"]])
        else:
            R["scalars"][n] = (u, [(compile_tmpl2(t, {"v": slot_regex("v", u)}), None) for t in u["clauses"]])
    _RX2[tool] = R
    return R


def parse_request2(tool, text):
    """the values that the request text fixes, as a nested dict; array entries in the order of the text"""
    R, named = request_patterns(tool), {}
    for n, (u, pats) in R["scalars"].items():
        hits = []
        for rx, flag in pats:
            m = rx.search(text)
            if m:
                k = u["kind"]
                if k == "flag":
                    hits.append({n: flag})
                elif k == "money":
                    hits.append({n: float(m.group("amount")), u["cur_name"]: m.group("cur")})
                else:
                    hits.append({n: parse_leaf(u, m.group("v"))})
        if hits:
            assert all(h == hits[0] for h in hits), ("ambiguous request", n, hits)
            named.update(hits[0])
    if R["object"]:
        u, forms = R["object"]
        for form, rxs in forms:
            ms = [rx.search(text) for rx in rxs]
            ms = [m for m in ms if m]
            if ms:
                m = ms[0]
                named[u["name"]] = {"name": m.group("name")}
                if form != "name":
                    named[u["name"]][form] = m.group(form)
                break
    if R["lines"]:
        u, rxs = R["lines"]
        found = sorted(((m.start(), m.end(), m) for rx in rxs for m in rx.finditer(text)), key=lambda t: t[0])
        ents, curs, last = [], set(), -1
        fields = {f["name"]: f for f in u["fields"]}
        for s, e, m in found:
            assert s >= last, ("array entries overlap", text[s:e])
            last = e
            ents.append({f: parse_leaf(fields[f], m.group(f)) for f in u["required"]})
            if "currency" in m.groupdict():
                curs.add(m.group("currency"))
        if ents:
            named[u["name"]] = ents
        if curs:
            assert len(curs) == 1, curs
            named["currency"] = curs.pop()
    return named


# ----------------------------------------------------------------------------------------------------------------
# validation: the text-based checker (violations2 / check2) and the specification-based truth2
# ----------------------------------------------------------------------------------------------------------------
def join_path(path, k):
    return k if not path else f"{path}.{k}"


def validate_node(node, v, path, out):
    t = node["type"]
    if t == "object":
        if not isinstance(v, dict):
            out.append(("type", path))
            return
        for r in node.get("required", []):
            if r not in v:
                out.append(("missing", join_path(path, r)))
        for k, x in v.items():
            if k not in node["properties"]:
                out.append(("extra", join_path(path, k)))
            else:
                validate_node(node["properties"][k], x, join_path(path, k), out)
    elif t == "array":
        if not isinstance(v, list):
            out.append(("type", path))
            return
        if not node["minItems"] <= len(v) <= node["maxItems"]:
            out.append(("enum", path))
        for i, x in enumerate(v):
            validate_node(node["items"], x, f"{path}[{i}]", out)
    else:
        if not type_ok(v, t):
            out.append(("type", path))
            return
        if "enum" in node and v not in node["enum"]:
            out.append(("enum", path))
        if ("minimum" in node and v < node["minimum"]) or ("maximum" in node and v > node["maximum"]):
            out.append(("enum", path))
        if node.get("format") == "date":
            try:
                datetime.date.fromisoformat(v)
            except ValueError:
                out.append(("format", path))


def same_value(a, b):
    return abs(a - b) < 1e-9 if isinstance(a, float) or isinstance(b, float) else a == b


def compare_named(node, named, args, path, out):
    """values that the request fixes and the call does not carry unchanged (a wrong type or a missing required field is not repeated here)"""
    for k, nv in named.items():
        sub = node["properties"].get(k)
        if sub is None:
            continue
        if k not in args:
            if k not in node.get("required", []):
                out.append(("value", join_path(path, k)))
            continue
        av = args[k]
        if sub["type"] == "object":
            if isinstance(av, dict):
                compare_named(sub, nv, av, join_path(path, k), out)
        elif sub["type"] == "array":
            if isinstance(av, list):
                if len(av) != len(nv):
                    out.append(("value", join_path(path, k)))
                else:
                    for i, (ne, ae) in enumerate(zip(nv, av)):
                        if isinstance(ae, dict):
                            compare_named(sub["items"], ne, ae, f"{join_path(path, k)}[{i}]", out)
        elif type_ok(av, sub["type"]) and not same_value(av, nv):
            out.append(("value", join_path(path, k)))


def violations2(state):
    """(kind, path) of everything wrong with the call, found by reading the text of the state"""
    m = re.search(r"Tool schema:\n(.*)\n\nUser request:\n(.*)\n\nProposed call:\n(.*)\Z", state, re.S)
    schema, request, call = json.loads(m.group(1)), m.group(2), json.loads(m.group(3))
    params, args, out = schema["parameters"], call["arguments"], []
    if call["name"] != schema["name"]:
        out.append(("name", call["name"]))
    validate_node(params, args, "", out)
    for r in parse_rules2(schema["description"]):
        if not rule_holds(r, args):
            out.append(("rule", r["kind"]))
    compare_named(params, parse_request2(schema["name"], request), args, "", out)
    return out


def check2(item):
    return "no" if violations2(item["state"]) else "yes"


def node_ok(node, v):
    """independent of validate_node: True when the value fits the schema node (types, required, enum, ranges, array sizes)"""
    t = node["type"]
    if t == "object":
        return (isinstance(v, dict) and all(r in v for r in node.get("required", []))
                and all(k in node["properties"] and node_ok(node["properties"][k], x) for k, x in v.items()))
    if t == "array":
        return isinstance(v, list) and node["minItems"] <= len(v) <= node["maxItems"] and all(node_ok(node["items"], x) for x in v)
    if t == "string" and not isinstance(v, str) or t == "boolean" and not isinstance(v, bool):
        return False
    if t in ("integer", "number") and (isinstance(v, bool) or not isinstance(v, int if t == "integer" else (int, float))):
        return False
    if "enum" in node and v not in node["enum"]:
        return False
    if ("minimum" in node and v < node["minimum"]) or ("maximum" in node and v > node["maximum"]):
        return False
    if node.get("format") == "date":
        try:
            datetime.date.fromisoformat(v)
        except ValueError:
            return False
    return True


def named_ok(named, call):
    """every value that the request fixes is in the call, unchanged (arrays: same length, entry by entry)"""
    if isinstance(named, dict):
        return isinstance(call, dict) and all(k in call and named_ok(x, call[k]) for k, x in named.items())
    if isinstance(named, list):
        return isinstance(call, list) and len(named) == len(call) and all(named_ok(x, y) for x, y in zip(named, call))
    if isinstance(named, bool) or isinstance(call, bool):
        return type(named) is type(call) and named == call
    return same_value(named, call)


def truth2(spec):
    """gold answer from the structured specification"""
    ok = (node_ok(spec["schema"]["parameters"], spec["call"]) and all(rule_holds(r, spec["call"]) for r in spec["rules"])
          and named_ok(spec["named"], spec["call"]))
    return "yes" if ok else "no"


def render_state2(spec):
    call = {"name": spec["tool"], "arguments": spec["call"]}
    return (CONVENTIONS2 + "\n\nTool schema:\n" + "\n".join(fmt_json(spec["schema"])) + "\n\nUser request:\n" + render_request2(spec) +
            "\n\nProposed call:\n" + json.dumps(call, indent=2))


# ----------------------------------------------------------------------------------------------------------------
# planting one deviation: every candidate edit is applied to a copy of the base and judged by the text-based checker; only an edit
# that leaves exactly one violation, of the intended kind, is kept
# ----------------------------------------------------------------------------------------------------------------
def refresh(s, skip=None):
    """recompute the computed parameters (sums, counts) from the entries of the call, except for the rule with index `skip`"""
    call, props = s["call"], s["schema"]["parameters"]["properties"]
    for i, r in enumerate(s["rules"]):
        if i == skip or r["kind"] not in ("sum", "count"):
            continue
        if r["kind"] == "sum":
            ents = entries(call, r["a"])
            c = sum_cents(r, ents) if ents is not None else None
            if c is not None and r["t"] in call:
                call[r["t"]] = c // 100 if props[r["t"]]["type"] == "integer" else round(c / 100, 2)
        elif isinstance(call.get(r["a"]), list) and r["n"] in call:
            call[r["n"]] = len(call[r["a"]])


def reorder(s, rng):
    """top-level keys in the order of the schema; a name the schema does not know goes to a random place"""
    order, call = list(s["schema"]["parameters"]["properties"]), s["call"]
    keys = [k for k in order if k in call]
    for k in [k for k in call if k not in order]:
        keys.insert(rng.randrange(len(keys) + 1), k)
    s["call"] = {k: call[k] for k in keys}


def stringify(v):
    return ("true" if v else "false") if isinstance(v, bool) else str(v)


def leaf_def(by, lines_u, n):
    """the leaf definition behind a top-level name (an amount and its currency are two leaves)"""
    if n == "currency":
        return F_enum("currency", lines_u["currency"], ["CHF", "SEK", "JPY"], "")
    if n in by:
        return by[n]
    for u in by.values():
        if u["kind"] == "money" and u["cur_name"] == n:
            return F_enum(n, u["curs"], ["CHF", "SEK", "JPY"], "")
    return None


def pick_pad(s, rng):
    """an optional parameter that the call does not give: it takes the place of a parameter that a deviation removes"""
    by = {u["name"]: u for u in LIB2[s["tool"]]["units"]}
    c = [by[n] for n, r in s["roles"].items() if r == "unused" and by[n]["free"] and by[n]["kind"] in ("enum", "flag", "int")]
    return rng.choice(c) if c else None


def candidates(s, kind):
    dom = LIB2[s["tool"]]
    by = {u["name"]: u for u in dom["units"]}
    lines_u = next(u for u in dom["units"] if u["kind"] == "lines")
    obj_u = next(u for u in dom["units"] if u["kind"] == "object")
    L, O = lines_u["name"], obj_u["name"]
    call, named, roles = s["call"], s["named"], s["roles"]
    props = s["schema"]["parameters"]["properties"]
    maxitems = props[L]["maxItems"]
    fields = {f["name"]: f for f in lines_u["fields"]}
    n_ent = len(call[L])
    out = []

    def req_fields(i):
        return [f for f in lines_u["required"] if f in call[L][i]]

    if kind == "missing":
        for n in s["schema"]["parameters"]["required"]:
            if n in (L, O) or (n in by and by[n]["kind"] == "computed"):
                continue

            def fn(b, d, rng, n=n):
                pad = pick_pad(d, rng)
                if pad is None:
                    return None
                del d["call"][n]
                d["call"][pad["name"]] = gen_scalar2(rng, pad)
                return {"where": "top", "padded": pad["name"]}
            out.append(("top", n, fn))
        for i in range(n_ent):
            for f in req_fields(i):
                def fn(b, d, rng, i=i, f=f):
                    del d["call"][L][i][f]
                    return {"where": "element"}
                out.append(("element", f"{L}[{i}].{f}", fn))
        if O in call:
            def fn(b, d, rng):
                del d["call"][O]["name"]
                return {"where": "object"}
            out.append(("object", O, fn))

    elif kind == "extra":
        def free_swap(d, rng):
            free = [n for n in d["call"] if roles.get(n) == "free"]
            if not free:
                return False
            del d["call"][rng.choice(free)]
            return True

        def fn(b, d, rng):
            if not free_swap(d, rng):
                return None
            nm, gen = rng.choice([e for e in EXTRAS if e[0] not in props])
            d["call"][nm] = gen(rng)
            return {"where": "top", "name": nm}
        out.append(("top", "undefined name", fn))

        def fn(b, d, rng):                                          # a field of the entries given at the top level
            keys = [f for f in fields if f not in props and f in d["call"][L][0]]
            if not keys or not free_swap(d, rng):
                return None
            key = rng.choice(keys)
            d["call"][key] = d["call"][L][0][key]
            return {"where": "top", "name": key, "wrong_level": True}
        out.append(("top", "entry field at top level", fn))
        for i in range(n_ent):
            def fn(b, d, rng, i=i):
                tops = [k for k, v in d["call"].items() if k not in fields and not isinstance(v, (dict, list))]
                if tops and rng.random() < 0.55:
                    k = rng.choice(tops)                              # a top-level field given inside an entry
                    d["call"][L][i][k] = d["call"][k]
                    return {"where": "element", "name": k, "wrong_level": True}
                nm, gen = rng.choice([e for e in EXTRAS if e[0] not in fields])
                d["call"][L][i][nm] = gen(rng)
                return {"where": "element", "name": nm}
            out.append(("element", f"{L}[{i}]", fn))
        if O in call:
            def fn(b, d, rng):
                tops = [k for k, v in d["call"].items() if k not in props[O]["properties"] and not isinstance(v, (dict, list)) and k != O]
                if tops and rng.random() < 0.5:
                    k = rng.choice(tops)
                    d["call"][O][k] = d["call"][k]
                    return {"where": "object", "name": k, "wrong_level": True}
                nm, gen = rng.choice([e for e in EXTRAS if e[0] not in props[O]["properties"]])
                d["call"][O][nm] = gen(rng)
                return {"where": "object", "name": nm}
            out.append(("object", O, fn))

    elif kind == "enum":
        for n, v in call.items():
            f = leaf_def(by, lines_u, n)
            if f is None or n in (L, O) or f["kind"] not in ("int", "enum", "money"):
                continue
            if f["kind"] == "money":
                f = dict(f, kind="amount")

            def fn(b, d, rng, n=n, f=f):
                is_named = n in named
                if f["kind"] == "enum":
                    bad = rng.choice(f["wrong"])
                    d["call"][n] = bad
                    if is_named:
                        d["named"][n] = bad
                    return {"where": "top", "limit": "enum", "variant": "request" if is_named else "call_only"}
                edge = "hi" if f["lo"] < 1 else rng.choice(["hi", "lo"])
                base_v = float(f[edge]) if f["kind"] == "amount" else f[edge]
                step = 0.01 if f["kind"] == "amount" else 1
                bad = round(base_v + step, 2) if edge == "hi" else round(base_v - step, 2)
                bad = bad if f["kind"] == "amount" else int(bad)
                for x, val in ((b, base_v), (d, bad)):
                    x["call"][n] = val
                    if is_named:
                        x["named"][n] = val
                return {"where": "top", "limit": "range", "variant": "request" if is_named else "call_only"}
            out.append(("top", n, fn))
        for i in range(n_ent):
            for f in lines_u["fields"]:
                n = f["name"]
                if f["kind"] in ("int", "amount") and n in call[L][i]:
                    def fn(b, d, rng, i=i, f=f):
                        edge = "hi" if f["lo"] < 1 else rng.choice(["hi", "lo"])
                        base_v = float(f[edge]) if f["kind"] == "amount" else f[edge]
                        step = 0.01 if f["kind"] == "amount" else 1
                        bad = round(base_v + step, 2) if edge == "hi" else round(base_v - step, 2)
                        bad = bad if f["kind"] == "amount" else int(bad)
                        for x, val in ((b, base_v), (d, bad)):
                            x["call"][L][i][f["name"]] = val
                            x["named"][L][i][f["name"]] = val
                        return {"where": "element", "limit": "range", "variant": "request"}
                    out.append(("element", f"{L}[{i}].{n}", fn))
                elif f["kind"] == "enum" and n in call[L][i]:
                    def fn(b, d, rng, i=i, f=f):
                        d["call"][L][i][f["name"]] = rng.choice(f["wrong"])
                        return {"where": "element", "limit": "enum", "variant": "call_only"}
                    out.append(("element", f"{L}[{i}].{n}", fn))
        if n_ent == maxitems:
            def fn(b, d, rng):
                for _ in range(30):
                    new = gen_entries(rng, lines_u, 1, d["rules"], d["call"])[0]
                    if all(new[f] not in [e[f] for e in d["call"][L]] for f in lines_u["required"] if fields[f]["kind"] == "id"):
                        break
                d["call"][L].append(new)
                d["named"][L].append({f: new[f] for f in lines_u["required"]})
                d["phrasing"]["elem"].append({"variant": rng.randrange(4), "words": rng.random() < 0.5})
                return {"where": "array", "limit": "size", "variant": "request"}
            out.append(("array", L, fn))

    elif kind == "type":
        for n, v in call.items():
            if props[n]["type"] in ("integer", "number", "boolean"):
                def fn(b, d, rng, n=n):
                    d["call"][n] = stringify(d["call"][n])
                    return {"where": "top"}
                out.append(("top", n, fn))
        for i in range(n_ent):
            for n, v in call[L][i].items():
                if fields[n]["kind"] in ("int", "amount", "flag"):
                    def fn(b, d, rng, i=i, n=n):
                        d["call"][L][i][n] = stringify(d["call"][L][i][n])
                        return {"where": "element"}
                    out.append(("element", f"{L}[{i}].{n}", fn))

        def fn(b, d, rng):                                          # the array given as one object
            d["call"][L] = d["call"][L][0]
            return {"where": "array"}
        out.append(("array", L, fn))
        if O in call:
            def fn(b, d, rng):
                d["call"][O] = d["call"][O]["name"]
                return {"where": "object"}
            out.append(("object", O, fn))

    elif kind == "value":
        for n, nv in named.items():
            f = leaf_def(by, lines_u, n)
            if f is None or n in (L, O):
                continue
            if f["kind"] == "money":
                f = dict(f, kind="amount")

            def fn(b, d, rng, n=n, f=f):
                old = d["named"][n]
                a = d["phrasing"]["asides"].get(n)
                d["call"][n] = a[0] if (a and rng.random() < 0.85) else near_leaf(rng, f, old)
                return {"where": "top", "lookalike": bool(a and d["call"][n] == a[0])}
            out.append(("top", n, fn))
        for i in range(n_ent):
            for n in lines_u["required"]:
                def fn(b, d, rng, i=i, n=n):
                    old, f = d["named"][L][i][n], fields[n]
                    a = d["phrasing"]["asides"].get(f"{L}[{i}].{n}")
                    d["call"][L][i][n] = a[0] if (a and rng.random() < 0.85) else near_leaf(rng, f, old)
                    return {"where": "element", "lookalike": bool(a and d["call"][L][i][n] == a[0])}
                out.append(("element", f"{L}[{i}].{n}", fn))
        if O in named:
            for n in named[O]:
                def fn(b, d, rng, n=n):
                    f = obj_u["fields"][[x["name"] for x in obj_u["fields"]].index(n)]
                    d["call"][O][n] = near_contact(rng, f, d["named"][O][n])
                    return {"where": "object"}
                out.append(("object", f"{O}.{n}", fn))

    else:                                                           # rule
        for idx, r in enumerate(s["rules"]):
            k = r["kind"]
            if k == "date_order":
                def fn(b, d, rng, r=r):
                    a = datetime.date.fromisoformat(d["named"][r["a"]])
                    new = (a if r["strict"] else a - datetime.timedelta(days=1)).isoformat()
                    d["call"][r["b"]] = new
                    d["named"][r["b"]] = new
                    d["phrasing"]["date_forms"][r["b"]] = {"form": "iso"}
                    return {"where": "top", "rule": "date_order", "variant": "request"}
                out.append(("top", "date_order", fn))
            elif k == "only_when":
                def fn(b, d, rng, r=r):
                    if r["x"] in d["call"] or d["call"].get(r["y"]) == r["v"]:
                        return None
                    free = [n for n in d["call"] if roles.get(n) == "free"]
                    if not free:
                        return None
                    del d["call"][rng.choice(free)]
                    d["call"][r["x"]] = gen_code(rng)
                    return {"where": "top", "rule": "only_when", "variant": "call_only"}
                out.append(("top", "only_when", fn))
            elif k == "one_of":
                def fn(b, d, rng, r=r):
                    oname = r["p"].split(".")[0]
                    missing = [x.split(".")[1] for x in (r["p"], r["q"]) if x.split(".")[1] not in d["call"][oname]]
                    if len(missing) != 1:
                        return None
                    d["call"][oname][missing[0]] = make_email(rng, d["call"][oname]["name"]) if missing[0] == "email" else make_phone(rng)
                    return {"where": "object", "rule": "one_of", "variant": "call_only"}
                out.append(("object", "one_of", fn))
            elif k in ("sum", "count"):
                def fn(b, d, rng, r=r, idx=idx):
                    t = r["t"] if r["kind"] == "sum" else r["n"]
                    v, delta = d["call"][t], rng.choice([-1, 1])
                    new = round(v + 0.01 * delta, 2) if isinstance(v, float) else v + delta       # the smallest step
                    d["call"][t] = new if new >= 0 else v + abs(delta) * (0.01 if isinstance(v, float) else 1)
                    return {"where": "top", "rule": r["kind"], "variant": "call_only", "skip_rule": idx}
                out.append(("top", k, fn))
            elif k == "within":
                for i in range(n_ent):
                    def fn(b, d, rng, r=r, i=i):
                        lo, hi = d["call"][r["lo"]], d["call"][r["hi"]]
                        new = (datetime.date.fromisoformat(hi) + datetime.timedelta(days=1)).isoformat() if rng.random() < 0.6 else (
                            datetime.date.fromisoformat(lo) - datetime.timedelta(days=1)).isoformat()
                        d["call"][L][i][r["f"]] = new
                        d["named"][L][i][r["f"]] = new
                        d["phrasing"]["date_forms"][f"{L}[{i}].{r['f']}"] = {"form": "iso"}
                        return {"where": "element", "rule": "within", "variant": "request"}
                    out.append(("element", f"within[{i}]", fn))
            else:                                                   # elem_order
                for i in range(n_ent):
                    def fn(b, d, rng, r=r, i=i):
                        d["call"][L][i][r["hi"]] = d["call"][L][i][r["lo"]]
                        d["named"][L][i][r["hi"]] = d["call"][L][i][r["lo"]]
                        return {"where": "element", "rule": "elem_order", "variant": "request"}
                    out.append(("element", f"elem_order[{i}]", fn))
    return out


def near_contact(rng, f, v):
    """a name, e-mail address or phone number that differs a little from v"""
    if f["kind"] == "text":
        return near_text(rng, v)
    if f["kind"] == "phone":
        return swap_adjacent(rng, v, only_digits=True) or v[:-1] + str((int(v[-1]) + 1) % 10)
    local, host = v.split("@")
    first, last = local.split(".")
    return (swap_adjacent(rng, first) or first[::-1]) + "." + last + "@" + host


WHERE_WEIGHT = {"top": 1.0, "element": 2.2, "object": 0.7, "array": 0.5}     # most deviations hide inside an array entry


def plant2(rng, base, kind, tries=60, family=None):
    """-> (base, deviated copy) with exactly one violation of `kind` in the copy, or None; family: the rule that a rule deviation breaks"""
    groups = collections.defaultdict(list)
    for c in candidates(base, kind):
        if kind == "rule" and family and c[1].split("[")[0] != family:
            continue
        groups[c[1].split("[")[0] if kind == "rule" else c[0]].append(c)          # a rule deviation: pick the rule first
    keys = sorted(groups)
    for _ in range(tries):
        if not keys:
            return None
        key = rng.choice(keys) if kind == "rule" else rng.choices(keys, weights=[WHERE_WEIGHT[w] for w in keys])[0]
        c = rng.choice(groups[key])
        b, d = copy.deepcopy(base), copy.deepcopy(base)
        detail = c[2](b, d, rng)
        if detail is None:
            continue
        refresh(b)
        refresh(d, detail.get("skip_rule"))
        reorder(b, rng)
        reorder(d, rng)
        if len(b["call"]) != len(d["call"]):
            continue
        if violations2(render_state2(b)):
            continue
        v = violations2(render_state2(d))
        if len(v) == 1 and v[0][0] == kind:
            d["deviation"] = dict(detail, kind=kind, path=v[0][1], label=c[1])
            return b, d
    return None


# ----------------------------------------------------------------------------------------------------------------
# v2: self-test, main, task files, README
# ----------------------------------------------------------------------------------------------------------------
def self_test2(rng):
    """every phrasing of the openers, clauses, entries and lead-ins is parsed back to the values it was made from"""
    for tool in TOOLS2:
        for variant in range(4):
            for P in LEVELS2:
                spec = make_base2(rng, LIB2[tool], P)
                phr = spec["phrasing"]
                phr["opener"], phr["lead"] = variant, variant
                phr["variants"] = {n: variant for n in phr["variants"]}
                for e in phr["elem"]:
                    e["variant"] = variant
                assert parse_request2(tool, render_request2(spec)) == spec["named"], (tool, variant, P)
                assert not violations2(render_state2(spec)) and truth2(spec) == "yes", (tool, variant, P)
    for _ in range(2000):
        d = gen_target(rng)
        assert eval_date(render_date(d, pick_form(rng, d))) == d


LEVEL_OF = {6: 1, 9: 2, 12: 3}                      # meta.level for the dial `params` (6 / 9 / 12 top-level properties)


def main_v2():
    global FORBID
    FORBID = all_name_words()                           # no invented name, title or e-mail domain equals a parameter-name word
    lib_bad = library_collisions()
    assert not lib_bad, lib_bad[:3]                     # no template, filler or enum word of any tool equals a parameter name of that tool
    master = random.Random(SEED)
    self_test2(sub("self-test"))
    cells, used = [], collections.Counter()
    for level in LEVELS2:
        kinds = [k for k, q in zip(KINDS2, KIND_QUOTA2[level]) for _ in range(q)]
        tools = [TOOLS2[i % len(TOOLS2)] for i in range(len(kinds))]
        master.shuffle(tools)
        for k, t in zip(kinds, tools):
            fam = None
            if k == "rule":                                         # the rule family of a rule deviation: the least used one the tool has
                fam = min(sorted({c[0] for c in LIB2[t]["rules"]}), key=lambda f: used[f])
                used[fam] += 1
            cells.append((level, k, t, fam))
    seeds = [master.getrandbits(64) for _ in cells]
    rows = []
    for pair_no, ((level, kind, tool, fam), seed) in enumerate(zip(cells, seeds), 1):
        rng = random.Random(seed)
        got = None
        for attempt in range(600):
            dom = LIB2[tool] if attempt < 200 else LIB2[rng.choice([t for t in TOOLS2 if not fam or any(c[0] == fam for c in LIB2[t]["rules"])])]
            base = make_base2(rng, dom, level, fam)
            got = plant2(rng, base, kind, family=fam)
            if got and any(name_collisions(sp) for sp in got):          # a name or value that equals a parameter-name word: draw again
                got = None
            if got:
                break
        assert got, (level, kind, tool)
        for spec, gold in zip(got, ("yes", "no")):
            assert truth2(spec) == gold, (pair_no, kind, gold)
            rows.append({"pair": pair_no, "level": level, "gold": gold, "spec": spec, "state": render_state2(spec)})
    sub("shuffle").shuffle(rows)
    items = []
    for i, r in enumerate(rows, 1):
        spec, state = r["spec"], r["state"]
        dv = spec["deviation"]
        lines_name = next(u["name"] for u in LIB2[spec["tool"]]["units"] if u["kind"] == "lines")
        n_ind = sum(1 for p, f in spec["phrasing"]["date_forms"].items() if f["form"] != "iso" and (
            p in spec["named"] or (p.startswith(lines_name + "[") and int(p[len(lines_name) + 1:].split("]")[0]) < len(spec["named"][lines_name]))))
        item = {"id": f"{TASK}:{i:05d}", "state": state, "questions": {"q": copy.deepcopy(QUESTION)}, "gold": r["gold"], "soft": None,
                "group": f"{TASK}:g{r['pair']:04d}",
                "meta": {"source_id": f"{i:05d}", "pair": f"{r['pair']:05d}", "tool": spec["tool"], "level": LEVEL_OF[r["level"]], "params": r["level"],
                         "rules": [x["kind"] for x in spec["rules"]],
                         "deviation": dv["kind"] if dv else None, "deviation_path": dv["path"] if dv else None,
                         "deviation_where": dv["where"] if dv else None,
                         "deviation_detail": ({k: v for k, v in dv.items() if k in ("limit", "variant", "rule", "padded", "name", "wrong_level", "lookalike")}
                                              if dv else None),
                         "n_args": len(spec["call"]), "n_entries": len(spec["call"][lines_name]) if isinstance(spec["call"][lines_name], list) else 1,
                         "n_required": len(spec["schema"]["parameters"]["required"]), "n_indirect_dates": n_ind, "spec": spec}}
        viol = violations2(state)
        assert check2(item) == item["gold"] == truth2(spec), (item["id"], viol)
        if item["gold"] == "yes":
            assert viol == [], (item["id"], viol)
        else:
            assert len(viol) == 1 and viol[0][0] == dv["kind"] and viol[0][1] == dv["path"], (item["id"], viol, dv)
        items.append(item)
    gold = [it["gold"] for it in items]
    assert collections.Counter(gold) == {"yes": 300, "no": 300}
    assert collections.Counter(it["meta"]["level"] for it in items) == {1: 200, 2: 200, 3: 200}
    for it in items:                                    # gen_v4: no word of the request equals a parameter name without referring to it
        request = re.search(r"User request:\n(.*)\n\nProposed call:", it["state"], re.S).group(1)
        assert all(text in request for text, _, src in request_pieces(it["meta"]["spec"]) if src != "lead"), it["id"]
        assert not name_collisions(it["meta"]["spec"]), (it["id"], name_collisions(it["meta"]["spec"])[:2])
    for lv in LEVELS2:
        assert collections.Counter(it["gold"] for it in items if it["meta"]["params"] == lv) == {"yes": 100, "no": 100}
        for k, q in zip(KINDS2, KIND_QUOTA2[lv]):
            assert sum(1 for it in items if it["meta"]["params"] == lv and it["meta"]["deviation"] == k) == q
    assert all(sum(1 for it in items if it["meta"]["deviation"] == k) == 50 for k in KINDS2)
    worst = {}
    for pat, name in ((r"[a-z]+", "words"), (r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", "all tokens")):
        bad, tested, w = vocab_test([it["state"] for it in items], gold, pattern=pat)
        worst[name] = w
        print(f"vocabulary test ({name}): {tested} tokens with frequency >= 20, worst rate ratio {w:.2f}, offenders {bad[:10]}")
        assert not bad
    for p in sorted({it["meta"]["pair"] for it in items}):
        pr = [it for it in items if it["meta"]["pair"] == p]
        assert len(pr) == 2 and {x["gold"] for x in pr} == {"yes", "no"} and pr[0]["meta"]["n_args"] == pr[1]["meta"]["n_args"]
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "items.jsonl"), "w", encoding="utf-8") as f:
        for it in items:
            f.write(dumps(it) + "\n")
    lens = [len(it["state"]) for it in items]
    write_task_files_v2(items, min(lens), max(lens))
    report_v2(items, lens, worst)


def write_task_files_v2(items, lo, hi):
    tj = {"task": TASK, "layer": "D",
          "title": "Generated tool calls: is the proposed call correct for the request under the schema? (difficulty v2)",
          "decision": "whether a proposed tool call is valid under the tool's JSON schema, keeps the rules of its description and carries every value that the user request fixes, directly or indirectly (yes), or breaks the schema, a rule or the request (no)",
          "source": {"name": f"generator build/gen_{TASK}.py", "url": "", "files": [], "split": "generated, random.Random(20261007), difficulty v2",
                     "version": "gen_v4, 2026-10-08: no word of the request equals a parameter name without referring to it (checked per item), "
                                                 "filler sentences from a pool of 44, languages named in the request (Dutch) while the call carries the code (nl), meta.level 1/2/3"},
          "licence": "generated by the benchmark's script (no third-party text)", "redistribution": "items included",
          "labels": "programmatic", "item_source": "generated", "metric": "accuracy", "chance": 0.5, "rows": len(items),
          "groups": len({it["group"] for it in items}), "question_type": "choice", "options": 2,
          "notes": ("gen_v4 (2026-10-08): the request never uses a word that equals a parameter name (or one part of it) of the schema unless the phrase sets that parameter (a cost item "
                    "is no longer a receipt next to the flag `receipt`), the filler sentences come from a pool of 44 instead of 8 and are neutral, a language is named in the request "
                    "(Dutch) while the call carries its code (nl), and meta.level = 1, 2, 3 for params 6, 9, 12. "
                    "Difficulty v2 (the first version, flat schemas with params 4/6/8, is regenerated with DIFFICULTY = \"v1\" at the top of the script). "
                    "300 matched pairs: a correct call (yes) and the same item with exactly one planted deviation (no); the pair id is meta.pair. "
                    "Schemas have 6, 9 or 12 top-level properties (meta.params; 200 rows each) with a nested object (name, e-mail, phone), an array of objects with its own "
                    "required fields and ranges, one computed parameter (a total, a count) and 1, 2 or 3 rules in the tool description (a date may not precede another, a parameter "
                    "is only allowed for a value of another, exactly one of two contact fields, a total equals a sum over the array, a count equals the number of entries, "
                    "every entry's day lies in the period, an hour window runs forward). The request fixes dates indirectly (last day of a month, nth weekday of a month, n days "
                    "after or before a date), line items as quantities at a price each, and names look-alike identifiers (one transposed pair of digits) that must not be used. "
                    "Deviation kinds (50 each; 16 or 17 per level): missing (a required field missing at the top level, in one array entry or in the object), enum (one step "
                    "outside an enum, a range or the size of the array; the request itself asks for it, or the call sets an unnamed field), type (a string for a number or a "
                    "boolean, an object for an array, a string for an object), value (a near miss: one day off, a transposed pair of digits, the look-alike identifier, a price "
                    "one hundredth off, a name with a letter changed), extra (an undefined field at the top level, in an entry or in the object, or a field of another level "
                    "put at the wrong level), rule (one of the rules of the description is broken: a date one day early, a total or count off by the smallest step, an extra "
                    "contact field, a code without its condition, a day outside the period, an hour window that does not run forward). Computed parameters are recomputed "
                    "from the call's own entries except in the item that breaks their rule, so exactly one thing is wrong. "
                    f"State length {lo} to {hi} characters. Truth by truth2(spec); independently recomputed by check2(item) from the state text alone (schema JSON, rules "
                    "parsed from the description, request parsed with the clause patterns of the tool); the top-level argument counts of the two members of a pair are equal.")}
    with open(os.path.join(OUT, "task.json"), "w", encoding="utf-8") as f:
        json.dump(tj, f, indent=1, ensure_ascii=False)


def report_v2(items, lens, worst):
    head, line, r = audit_lines()
    import validate as validate_mod
    validate_mod.HERE = ROOT
    tj, errs = validate_mod.check(TASK)
    status = "OK" if not errs else "ERRORS " + "; ".join(errs[:3])
    neg = [it for it in items if it["gold"] == "no"]
    cnt = collections.Counter((it["meta"]["params"], it["meta"]["deviation"]) for it in neg)
    where = collections.Counter((it["meta"]["deviation"], it["meta"]["deviation_where"]) for it in neg)
    rulef = collections.Counter(it["meta"]["deviation_detail"].get("rule") for it in neg if it["meta"]["deviation"] == "rule")
    by_level = {lv: [len(it["state"]) for it in items if it["meta"]["params"] == lv] for lv in LEVELS2}
    hard = LEVELS2[-1]
    ex = []
    for want in (lambda m: m["deviation"] == "value" and m["deviation_where"] == "element",
                 lambda m: m["deviation"] == "rule" and m["deviation_detail"].get("rule") == "sum",
                 lambda m: m["deviation"] == "missing" and m["deviation_where"] == "element"):
        ex.append(next(it for it in neg if it["meta"]["params"] == hard and want(it["meta"])))
    what = {"missing": "a required field is missing: at the top level (an unnamed optional one is added), in one array entry, or in the nested object",
            "enum": "one step outside an enum, a range or the size of the array (the request asks for it, or the call sets an unnamed field)",
            "type": "a string for a number or a boolean, an object where the schema says array, a string where it says object",
            "value": "a near miss that contradicts the request: one day off, a transposed pair of digits (often the look-alike named in the request), a price one hundredth off",
            "extra": "an undefined field at the top level, in an array entry or in the object, or a field of another level at the wrong level",
            "rule": "one rule of the tool description is broken: date order, total or count off by the smallest step, a second contact field, a code without its condition, a day outside the period, an hour window that does not run forward"}
    lines = [f"# {TASK}", "", "Generated tool calls (difficulty v2): is the proposed call correct for the request under the tool's schema?", "",
             "- Decision: whether a proposed tool call is valid under the tool's JSON schema, keeps the rules of its description and carries every value that the user request fixes, directly or indirectly (yes), or breaks the schema, a rule or the request (no).",
             f"- Item source: generated by `build/gen_{TASK}.py` (`random.Random(20261007)`, standard library only, no input file); labels programmatic; licence: generated by the benchmark's script (no third-party text); items included.",
             f"- Rows: {len(items)} (300 yes, 300 no); metric: accuracy (chance 0.5). Rebuild: `python3 build/gen_{TASK}.py`; the first version (flat schemas, params 4/6/8) is `DIFFICULTY = \"v1\"` at the top of the script.", "",
             "## What is generated", "",
             "Every item is a tool schema in JSON, a user request and a proposed call in JSON, under a fixed block of judging conventions. The schema has 6, 9 or 12 top-level properties: scalars (identifiers, dates, counts, enum words, yes/no flags, names, codes, amounts with a currency), "
             "a nested object (name, e-mail, phone), an array of objects with its own required fields, ranges and size limits (order lines, shifts, passengers, cost items, delivery stops), and one computed parameter (a total, a count). "
             "The tool description states 1, 2 or 3 rules across parameters: a date may not precede another; a code is only allowed for one value of another parameter; exactly one of the two contact fields is given; a total equals a sum over the array "
             "(quantity times price, a field, hours); a count equals the number of entries; every entry's day lies in the period; every hour window runs forward. "
             "The request fixes values indirectly as well as directly: dates as the last day of a month, the n-th weekday of a month or a number of days from another date; line items as a quantity at a price each (so the total must be computed); "
             "and look-alike identifiers: after an identifier a bracket names another one, with one transposed pair of digits, that must not be used. "
             "Five invented tools (order, rota, trip, claim, delivery run) with 15 to 19 properties in the pool each. The words of the request never equal a parameter name of the schema unless they set that parameter (a cost item is a bill, not a receipt, next to the flag `receipt`); "
             "filler sentences come from a pool of 44; a language is named (\"Dutch\") while the call carries its code. The 300 positives are correct calls that exercise the same structures (arrays of 2 to 8 entries, boundary values, indirect dates, look-alikes, rules at their limits); "
             "each has a twin with exactly one planted deviation. Both rows of a pair are scored as separate items; a bootstrap that resamples by `meta.pair` accounts for their correlation.", "",
             "## Dial", "", f"`meta.level` = 1, 2, 3 for `meta.params` = number of top-level properties 6, 9, 12 (200 rows each, 100 yes and 100 no). More properties bring more rules (1, 2, 3), a nested object from 9 on, and longer arrays (2-3, 3-5, 4-7 entries). "
             f"State length: {min(by_level[6])}-{max(by_level[6])}, {min(by_level[9])}-{max(by_level[9])} and {min(by_level[12])}-{max(by_level[12])} characters.", "",
             "## Deviation kinds (`meta.deviation`, number of no-items per dial level)", "", "| kind | what is wrong | level 1 (params 6) | level 2 (params 9) | level 3 (params 12) | total |", "|---|---|---|---|---|---|"]
    for k in KINDS2:
        lines.append(f"| {k} | {what[k]} | " + " | ".join(str(cnt[(lv, k)]) for lv in LEVELS2) + f" | {sum(cnt[(lv, k)] for lv in LEVELS2)} |")
    lines += ["", "Where the deviation sits (`meta.deviation_where`): " + ", ".join(f"{w} {sum(v for (k, ww), v in where.items() if ww == w)}" for w in ("top", "element", "object", "array")) + ". "
              "Rule deviations by rule: " + ", ".join(f"{k} {v}" for k, v in sorted(rulef.items())) + ".", "",
              f"Indirect dates per request: mean {sum(it['meta']['n_indirect_dates'] for it in items) / len(items):.1f}. Vocabulary test worst rate ratio: {worst['words']:.2f} (words), {worst['all tokens']:.2f} (all tokens).", "",
              "## Checks run by the script", "",
              "- `truth2(spec)` on the structured specification (`meta.spec`) and `check2(item)` on the state text alone agree on all 600 items; every negative has exactly one violation, of the planted kind, at the recorded path; the correct member of every pair has none.",
              "- Exact balance: 300 yes / 300 no; 100 + 100 per dial level; 16 or 17 deviations per kind and level (50 per kind). The two members of a pair have the same number of top-level arguments.",
              "- Vocabulary test: no word (and no token) of frequency >= 20 is more than twice as frequent in one class as in the other.",
              "- Name collisions (gen_v4): no word of the request equals a parameter name of the schema (the whole name in singular or plural, or one part of it split at the underscores) unless the phrase sets that parameter; "
              "the words of the tool's own name (create_order: create, order) and date expressions (\"the last day of ...\") are exempt. The test runs on the whole library (every phrasing, filler sentence and enum word of every tool against every name the tool can have) "
              "and on the request of every item and of both members of every pair; invented names, titles and e-mail domains are drawn so that they do not equal such a word.",
              "- Languages (gen_v4): the request names the language (\"replying in Dutch\"), the call carries the code (`nl`); the schema says that the value is a two-letter ISO 639-1 code, and `parse_request2` maps the name back to the code.", "",
              "## Audit (`python3 audit.py " + TASK + "`)", "", "```", head, line, "```", "", f"`python3 validate.py {TASK}`: {status}.", "",
              "## Examples (three of the hardest level, params = 12)", ""]
    for it in ex:
        lines += [f"### {it['id']} (deviation {it['meta']['deviation']}, path {it['meta']['deviation_path']})", "", "```", example_text(it), "```", ""]
    lines += ["## Relation to the authors' training data", "",
              "The items are disjoint from any training generator of the authors by construction: this is a new generator, written for this benchmark "
              "(its own templates and its own invented vocabulary), and every entity is invented."]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"validate: {status}")
    print(head)
    print(line)
    print("classes:", dict(collections.Counter(it["gold"] for it in items)))
    print("per dial level:", dict(sorted(collections.Counter(it["meta"]["params"] for it in items).items())))
    print("per deviation:", dict(sorted(collections.Counter(str(it["meta"]["deviation"]) for it in items).items())))
    print("per level and deviation (no-items):", dict(sorted(cnt.items())))
    print("where:", dict(sorted(where.items())), "| rule deviations:", dict(rulef))
    print("state length per level:", {lv: (min(v), int(sum(v) / len(v)), max(v)) for lv, v in by_level.items()}, "overall", min(lens), "to", max(lens))
    print("example (hardest level):")
    print(example_text(ex[0]))


def main():
    return main_v2() if DIFFICULTY == "v2" else main_v1()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("v1", "v2"):
        DIFFICULTY = sys.argv[1]                      # optional: python3 generators/toolcall_valid.py v1
    main()
