---
description: Where the build is, what is running, and what is waiting on me - read out of the repo rather than remembered
argument-hint: "[an engagement id, to narrow it]"
---

Answer four questions, in this order, and read each answer out of the thing that owns it
rather than out of anything you remember.

## 1. Where the build is

```
python tools/gate.py status
```

`BUILD/STATE.md` is the cursor and it wins over anything said in a conversation. If
`status` says a checkpoint is owed, say so - a block of phases that have not been sealed
is phases that each passed alone and have not been checked against each other.

## 2. What this machine can actually do

```
python -m uv run python tools/serve.py --check
```

Report only what is *not* ok, and keep the distinction the check makes: **NOT INSTALLED**
is software a person installs, **NOT WIRED** is a join this build has not made. Do not
flatten them into "some things are missing".

## 3. What is running

```
python -m uv run python tools/watch_run.py --once
```

Once. Not in a loop.

## 4. What is waiting on me

Read `BUILD/OPEN.md`. It has four kinds of item - waiting on my word, decisions that
belong to the practice, things owed on this machine, and evidence only the work machine
can produce. Tell me the ones in the first and third groups, because those are the ones I
can do something about tonight. Do not list the whole file.

Then check the two things that go stale quietly:

```
python -m uv run python tools/interview.py status
```

If the identifier register is empty or its acknowledgement has expired, say so first -
`interview.py scan` is what keeps client data inside `knowledge/`, and an empty register
means it has been checking nothing.

## What not to do

- Do not run the test suite. It takes minutes and `gate status` already says what passed.
- Do not run `gate render`, `gate amend` or `gate seal`. Those write.
- Do not summarise the backlog. It is 87 items and I did not ask.
- If something disagrees with something else, say so and name both sources. A
  disagreement between the code and the blueprint is a finding in this project, not a
  thing to pick a winner from.

$ARGUMENTS
