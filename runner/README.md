# Producing answer files

Evaluation only: never copy the items into a training directory and never put them into a prompt for a model you are going to train.

## The answer file

One file per task, `runs/<system>/<task>.jsonl`, one line per item of `tasks/<task>/items.jsonl`:

```json
{"id": "policy_case:00007", "p": {"approve": 0.12, "deny": 0.80, "escalate": 0.08}}
```

- `p` gives a probability for every option key of the item (the keys of `questions.q.criteria`; for a list of level texts the keys are
  `"0"`, `"1"`, ...). The scorer normalises over the item's options, so unnormalised scores are fine; a missing key counts as 0.
- The answer object of a typed-decision request is read as well: `{"id": ..., "answers": {"q": {"type": "choice", "choice": "deny",
  "probabilities": {...}}}}`; for a yes/no question of type `noul`: `{"type": "noul", "noul": 0.93}` (the probability of yes).
- A failed item gets `{"id": ..., "error": "<reason>"}`. An item without a line counts the same: unanswered, wrong, uniform probabilities.
- A run counts for a task only if at least 99% of its items have a line. Write the SHA-256 of every items file you ran on into
  `runs/<system>/_items.json` (`{"<task>": "<sha256>"}`), as the runners here do; the scorer then refuses a run made on other items of a
  core family.
- Give every item one answer from the model's own probabilities. Nothing may be fitted to the benchmark: the scores that depend on how
  sure a system is (automation at 5%, accuracy at 0.90, calibration error) are computed from the probabilities as the system gave them.

## A model with a typed-decision interface

The request is the item's `state` and `questions` (one question per item, key `q`), unchanged. `bench_http.py` posts it to
`<url>/v1/systemone` as `{"model", "state", "questions"}` and stores the `answers` field of the reply:

```bash
python3 runner/bench_http.py --url http://127.0.0.1:9701 --model NAME --out runs/NAME [--bench data] [--tasks a,b] [--workers 32]
python3 runner/bench_http.py --url https://HOST --model NAME --out runs/NAME --api-key-env NAME_OF_THE_VARIABLE
```

It can be restarted: answered items are skipped and items with an error are asked again. `--api-key-env` sends the value of an
environment variable as a Bearer token; the key is never written to a file. A model served by its own code can be put behind a small
server with this interface, or its read-out can write the answer file directly.

## A chat model (verbalised probabilities)

A chat model returns text, so it is asked for one option key and a probability for every option as JSON. This is the prompt of the
paper's chat-model baselines (`runner/chat/common.py`):

```
system:  You answer one typed question about the state you are given. Reply with the key of exactly one option, copied as it is
         written, and a probability for every option, as one JSON object and nothing else: {"choice": "<the key of the option you
         pick>", "probabilities": {"<key>": <probability>, ...}}. "probabilities" has one number between 0 and 1 for every option key,
         the numbers add up to 1, and each number is how likely you think it is that this option is the right one.
user:    STATE
         <the state; a structure is written as indented JSON>

         QUESTION
         <questions.q.instructions>

         OPTIONS (key: meaning)
         <key>: <option text>
         ...

         Reply with the JSON object, in this form:
         {"choice": "<key>", "probabilities": {"<key 1>": <p>, "<key 2>": <p>, ...}}
```

```bash
python3 runner/chat/run_api.py --keyfile KEYFILE --base-url https://HOST/v1 --model MODEL --reasoning off --out raw.jsonl
python3 runner/chat/run_api.py --keyfile KEYFILE --base-url https://HOST/v1 --model MODEL --reasoning high \
    --subsample runner/chat/subsample_1296.json --out raw_think.jsonl
python3 runner/chat/collect.py raw.jsonl MODEL-off                 # runs/MODEL-off/<family>.jsonl and _items.json
python3 runner/chat/collect.py raw_think.jsonl MODEL-think
python3 scoring/score.py MODEL-off=runs/MODEL-off
python3 scoring/score.py MODEL-think=runs/MODEL-think --subsample runner/chat/subsample_1296.json
```

- `run_api.py` asks the 13 core families (or `--tasks`), one request per item, and appends every reply to the raw file as it arrives; a
  restart skips the items that have a reply. The key is read from the file named by `--keyfile` and goes into the request header only.
- `--reasoning off | low | high` sends the request fields that the providers of the paper's baselines use (`"thinking"` and
  `"reasoning_effort"`); another provider may need other fields. With `off` and `low` the requests use temperature 0.
- `collect.py` reads the replies with the rules in `common.parse_reply` (tested in `tests/test_chat_parse.py`): the probabilities are
  normalised over the item's options; a reply that names an option but whose probabilities do not parse puts 1.0 on the option; a reply
  with neither is an error line.
- `subsample_1296.json` is the stratified sample of 1,296 core items (whole contrast groups, about 100 items per family) on which the paper
  compares chat models with and without reasoning.
- The chat models of the paper state a top probability of 0.99 or more in 63% to 93% of their replies, so the paper compares them on
  accuracy and pair accuracy only.

## A language model with next-token probabilities

Use the answer-only form of the prompt: the system message asks for "the key of exactly one option, copied as it is written, and
nothing else", and the user message ends with "Reply with one key." instead of the JSON form. Read the probabilities of the option
keys at the next position, keep those of the keys only and write them as `p`. Say in the name of the system how the keys were read.

## A model that thinks first

Write the probabilities that the model gives after its thought as `p`, the length of the thought as `tokens`, whether the thought ended by
itself as `closed`, and, for a model that thinks only on some items, `thought` (true or false). Keep the one-pass read-out of the same run
as a second system, named `<name>-onepass`, and mark the pair in `systems.json`
(`{"NAME": {"name": "...", "mode": "with reasoning", "reasoning_of": "NAME-onepass", "table": true}}`) so that table T4 compares the two
on the same items.
