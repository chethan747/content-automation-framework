# Content Automation Framework

A workflow engine for automating repetitive content operations: reusable
steps chained into named workflows, with status tracking, an approval gate
that blocks publishing, and a servlet-style HTTP layer. Jobs and step
results are persisted in SQLite.

## What it does

- **Reusable steps:** validate content, transform/normalise it (trim,
  collapse whitespace, build a slug), pass an approval gate, publish.
- **Named workflows:** `standard-publish` (validate → transform → approval
  → publish) and `quick-publish` (validate → transform → publish, no
  approval gate).
- **Status tracking:** `pending` → `running` → `awaiting_approval` /
  `approved` → `published`, or `failed`. An unapproved job pauses at the
  approval gate — it does not fail, and approving it resumes from the
  gate without re-running earlier steps.
- **HTTP layer:** a servlet-style API built on Python's `http.server`.
- **Job store:** SQLite (`caf_jobs.db` by default), so jobs survive restarts.

## How to run

Requires Python 3.10+ and nothing else (standard library only).

```bash
# Demo: a sample publishing workflow, end to end
python3 -m caf.cli --db /tmp/caf_demo.db

# HTTP server (default http://127.0.0.1:8000)
python3 -m caf.server --port 8000 --db caf_jobs.db

# Tests
python3 -m unittest discover -s tests -v
```

## HTTP API

```bash
# List workflows
curl http://127.0.0.1:8000/workflows

# Run a workflow (returns 201 with the job)
curl -X POST http://127.0.0.1:8000/workflows/run \
  -H 'Content-Type: application/json' \
  -d '{"workflow": "standard-publish",
       "content": {"title": "Launch", "body": "Our guide is live."}}'

# List jobs / get one job
curl http://127.0.0.1:8000/jobs
curl http://127.0.0.1:8000/jobs/1

# Approve a paused job and resume it to published
curl -X POST http://127.0.0.1:8000/jobs/1/approve
```

## Architecture

```
caf/
  steps.py    -- ValidateStep, TransformStep, ApprovalGateStep, PublishStep
  engine.py   -- Workflow definitions, job lifecycle, step chaining, resume
  store.py    -- SQLite job + step-result persistence
  server.py   -- http.server handlers (the servlet-style layer)
  cli.py      -- demo CLI: create -> run -> gate -> approve -> publish
tests/
  test_engine.py  -- chaining, approval gate, failure handling, normalisation
  test_store.py   -- persistence across Store instances
  test_server.py  -- HTTP endpoints against a real local server
```

## Honest mapping to the portfolio description

The portfolio describes "a framework built on AEM workflows and servlets
to automate repetitive content operations". This repository is a
**standalone Python implementation of those workflow/servlet concepts**:
a step-chaining engine, an approval gate, and an HTTP endpoint layer
modelled on the servlet idea. It is written in pure Python so it runs
anywhere with no build tooling.

It does **not** run inside Adobe AEM, it does not use AEM, OSGi, or Java,
and it is **not** claimed as a client production system. No portfolio
metrics are reproduced here — there are no efficiency or time-saving
claims, only the behaviour demonstrated by the code and tests.
