# Decisions

Short log of the calls that actually mattered, in roughly the order I made them.

## 1. SQLite, not Postgres

**Decision:** SQLite for the database.
**Rejected:** PostgreSQL.
**Why:** the brief explicitly deprioritizes scale/performance ("each file has a hundred and twenty rows") and weights "does it run from a clean clone" at 30% — the single highest criterion. Postgres would mean the reviewer needs a running Postgres instance or a docker-compose just to run `migrate`, for zero benefit at this data size. Django's ORM stores `DecimalField` as an exact string through both backends, so there's no precision trade-off either.

## 2. Keep both typed fields and the raw CSV row

**Decision:** every imported row stores parsed/typed columns (Decimal, Date, etc.) *and* a `raw_row` JSON field with the untouched original CSV row.
**Rejected:** store only the parsed values.
**Why:** if a value fails to parse it becomes `NULL`, and without the original text there'd be no way to show *why* — the row would just look silently broken. The brief explicitly says nothing should be silently dropped; keeping the raw text is what makes that true even for garbage input.

## 3. System A's location anchors tenant-scoping — but is not "the truth"

**Decision:** when a disagreement needs to be filed under one tenant's screen, we use System A's `location_id` to decide which org it belongs to.
**Rejected:** trusting System B's location, or showing the row under both orgs.
**Why:** the brief says "neither is authoritative" about values, and I mean that literally — `VALUE_MISMATCH` rows always show both figures, no winner declared. But *tenant scoping* is a different question: something has to decide which screen a row appears on, or it either leaks to both tenants or neither. System B's own schema defines `record_ref` as pointing back at System A's id space, so A owns record identity. I anchor on that identity, not on A's numbers being more correct — REC-1077's `LOCATION_MISMATCH` row explicitly states B's conflicting location in its detail text rather than hiding it.

## 4. Duplicate-in-B is flagged uniformly, not smartly

**Decision:** any record_ref with 2+ B entries is flagged `DUPLICATE_IN_B`, full stop.
**Rejected:** detecting that `REC-1055`'s two entries (71950.93 + 107926.39) sum exactly to A's total and treating that differently from `REC-1042`'s true identical-value duplicate.
**Why:** I don't have enough business context to know if a "split entry that sums correctly" is an intentional multi-part transaction or a coincidence. Guessing intent from 120 rows felt riskier than flagging both cases the same way and letting a human decide — this is the one I'm least confident about (see README).

## 5. No auth, but every API call is org-scoped by a required parameter

**Decision:** `/api/disagreements/` requires `?org=`, and there is no "all tenants" endpoint.
**Rejected:** a single endpoint returning everything, filtered client-side.
**Why:** the brief says to skip auth entirely, but also says a row must never leak across tenants. Skipping login doesn't mean skipping the boundary — so I moved the boundary into the query layer instead: the server physically cannot return more than one tenant's rows in a single response, regardless of what the frontend does with them.

## 6. Orphan-in-B rows are scoped by System B's own location

**Decision:** a `record_ref` that matches no real A record (e.g. `REC-1999`) is filed under the org implied by *that entry's own* `location_id`.
**Rejected:** dropping orphan rows from every org view, since there's no A record to anchor identity to.
**Why:** decision #3 anchors tenant identity on A precisely *because* A owns the record — but an orphan has no A-side record at all, so there's nothing to anchor to. B's location is the only signal available, and showing the row (rather than hiding it) matches "find the disagreements," not "hide the ones we're unsure about."

## 7. Blank/unparseable B values are folded into VALUE_MISMATCH, not a 6th reason code

**Decision:** a blank or garbled `value` field in System B is reported as a `VALUE_MISMATCH` (with `b_value: "blank"` or `"unparseable: ..."`), not a separate reason category.
**Rejected:** a dedicated `UNPARSEABLE_VALUE` reason.
**Why:** it keeps the reason-filter dropdown to 5 options instead of 6, and functionally it *is* a mismatch — A has a value, B doesn't have a usable one. The detail text still says exactly what went wrong.

## 8. Record state (e.g. VOIDED) is not part of the comparison

**Decision:** only `total_value` and `location_id` are compared between A and B; `state` is imported and stored but never checked.
**Rejected:** flagging a `VOIDED` record that still has a matching B entry as a disagreement.
**Why:** `REC-1019` is VOIDED in A but has a value-agreeing B entry — the brief's own framing ("the non-error is correctly identified as a non-error") reads as a direct hint that this shouldn't be flagged. Extending state-aware comparison felt like scope creep the brief didn't ask for.
