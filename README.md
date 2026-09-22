# DealerOS Reconciliation

Finds where System A and System B disagree about the same events, and shows the
disagreements one tenant (org) at a time, without ever mixing tenants in a single
response.

## How to run it

Requires Python 3.11+ and Node 18+.

**Backend**

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
python manage.py migrate
python manage.py import_data
python manage.py test
python manage.py runserver
```

`import_data` wipes and reloads all three tables from `backend/data/*.csv` every time
it runs, so it's safe to re-run from a clean clone. It prints how many rows it imported
per file and any parsing warnings (there's only one: `REC-1050`'s blank actor id gets
logged, not dropped).

**Frontend** (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Open the printed local URL (typically `http://localhost:5173`). The dev server proxies
`/api/*` to Django on `127.0.0.1:8000`, so no CORS setup is needed - just make sure the
backend is running first.

## What I built

- A Django + SQLite backend that imports `locations.csv`, `system_a.csv` and
  `system_b.csv` into three tables, keeping both parsed/typed fields and the untouched
  original row for every record (see `DECISIONS.md` #2).
- A comparison service (`backend/reconcile/services/compare.py`) that matches each
  System A record to its System B entry(ies) and flags five kinds of disagreement:
  missing in B, orphan in B (a phantom `record_ref`), duplicate in B, value mismatch,
  and location mismatch (the tenant-boundary case).
- Two API endpoints: `GET /api/orgs/` for the tenant picker, `GET
  /api/disagreements/?org=ORG-A` for one tenant's disagreements. `org` is required -
  there is no endpoint that returns more than one tenant's data.
- A single-page React frontend: an org selector, a reason filter, a sortable value
  column, and a plain HTML table. No styling effort, on purpose.
- 24 tests: one per disagreement type (each using the actual dirty row from the CSVs,
  not an invented fixture), a non-error case, three importer tests, and unit tests for
  the normalization helpers.

Running the importer against the real data gives **120 System A rows, 121 System B
rows** (the brief says "120 on each side" - the file itself has one extra row baked in,
see `DECISIONS.md`), and the comparison logic finds **11 real disagreements**: 2 missing
in B, 1 orphan in B, 2 duplicates in B, 5 value mismatches, 1 location mismatch. Three of
those value mismatches (`REC-1003`, `REC-1027`, `REC-1088`) weren't part of my original
read-through of the data - the comparison logic surfaced them on its own: System B
recorded the `base_value` instead of the `total_value` for those three.

## What I deliberately did not build

- **Auth** - skipped entirely, as instructed. Tenant isolation is enforced at the API
  query layer instead (every call requires `org`; see `DECISIONS.md` #5), not at a login
  screen.
- **Styling** - a plain HTML table, no CSS framework. The brief says this is correct.
- **Pagination / search** - not needed at 120-240 rows.
- **Date mismatch as a tracked disagreement type** - `REC-1009` has a real 2-day gap
  between System A's `event_date` and System B's `recorded_on` that today's build
  doesn't flag. It wasn't in the brief's minimum list, and I ran out of scope budget
  before it felt worth adding. Would be the first thing I'd build with a second day.
- **A smarter rule for the REC-1055 "split that sums correctly" case** - see
  `DECISIONS.md` #4. Flagged the same as a plain duplicate rather than guessing intent.
- **An admin UI or CSV re-upload flow** - the importer is a management command, run
  once per fresh clone, exactly matching the brief's scope.

## How I worked with the agent

I used Claude Code for essentially the whole build, but not as a single "generate the
app" prompt - it went through a planning pass first (with an explicit plan file) before
any code was written, specifically so I could catch a wrong architectural assumption
before it got baked into the schema (see question (a) below).

Before planning started, I had the agent verify every claim about the dataset directly
against the CSV bytes with `grep`, rather than trust a single read-through - the "few
dozen disagreements" framing in the brief turned out to actually be 11 once the
comparison logic ran for real, and I wanted the plan built on confirmed facts (exact
row counts, exact record ids for each dirty-data pattern) rather than assumptions. That
verification step is also what caught that System B has 121 rows, not 120 as the brief
states.

During implementation, the agent committed after each logical piece (models, importer,
normalization helpers, comparison logic, tests, API, frontend, this README, DECISIONS)
rather than all at once, and ran the actual test suite and a live end-to-end check
(both dev servers running, real HTTP requests through the Vite proxy) after each stage
instead of assuming the code worked from reading it. I reviewed the generated code
directly rather than just trusting it built and tests passed - by this point I can read
Django/DRF/React well enough to know what a given diff is doing.

### a. Name one thing the AI agent got wrong. How did you notice?

While drafting the plan, the AI agent made a mistake by saying that System A was the
source of truth for tenant-scoping a disagreeing record. However, the brief clearly
stated that neither System A nor System B was authoritative.

I noticed this by manually reviewing the whole plan again and comparing it with the
brief. I then explained the issue to Claude and asked for more clarity.

After discussing it, we corrected the reasoning. System A is used only to identify the
record and handle access control, not because System A's data is considered more
trustworthy. Both System A and System B values are still shown when there is a
mismatch. See `DECISIONS.md` #3.

### b. Which part of your submission are you least confident about, and why?

The `REC-1055` case (`DECISIONS.md` #4): System B has two entries for it whose values
sum exactly to System A's total. My comparison logic flags it as `DUPLICATE_IN_B`, the
same as `REC-1042`'s plain identical-value duplicate - but REC-1055 might genuinely be a
legitimate multi-part entry, not an error at all. I didn't have enough business context
in 120 rows to tell the difference confidently, and I'd rather flag it honestly than
build a heuristic I can't justify.

### c. If you had a second day, what would you fix first?

Two things, in order: add date-mismatch as its own tracked disagreement type (REC-1009
already proves it's a real pattern in this data, not a hypothetical), and build an
actual rule for the REC-1055 ambiguity instead of leaving it flagged identically to a
true duplicate - probably a sum-tolerance check that changes the *label*, not the
detection, so a reviewer sees "possible split entry" rather than a plain "duplicate."
