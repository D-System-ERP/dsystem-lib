# dsystem (shared lib) — Claude notes

Installed into every service with `pip install -e ../lib`. A change here lands in all six at once — run the
service suites, not just `lib`'s.

## Layout

`dsystem/` — `models/` (Base, mixins, replica models), `repositories/base.py` (`TenantRepository`,
`_base_query` = org filter + soft delete), `schemas/` (AppSchema, values, file refs), `dependencies/`
(`auth.py` JWT + `Requires` + role-version checks, `service_auth.py`, `guards.py` `or_404`/`check_version`),
`events/` (publisher, consumer with DLQ, outbox relay, envelope, `schemas.py` contract registry,
`replica_sync.py` + partner/legal-entity/user sync), `middleware/` (audit, idempotency, cancel-on-disconnect),
`handlers.py` (error envelope + i18n), `i18n.py`, `observability.py` (Sentry + Prometheus), `storage.py` /
`public_storage.py` (R2), `money.py`, `uom.py`, `sequences.py`, `permissions.py`, `role_templates.py`,
`locale/` (the 31 generic keys every service copies).

## Rules that bite

- This is a **port of TheCargo's `thecargo` lib**: keep its structure and naming, adapt only the domain. The
  15 comments left in `dependencies/auth.py`, `middleware/audit.py`, `models/__init__.py` and `permissions.py`
  are inherited — do not add new ones.
- `events/schemas.py` is the contract registry. A new event needs an entry there *and* a payload builder test
  in the publishing service (`test_event_contracts.py`).
- Middleware answers before the app's exception handlers, so anything that returns a JSON error from a
  middleware translates itself (`_error` in `middleware/idempotency.py` is the pattern).
- `observability.setup_metrics(app)` is installed once per process and is idempotent; the collector names are
  fixed by `infra/monitoring` — changing them breaks the dashboards and alerts.
- The outbox relay reports `dsystem_outbox_pending` every 12 ticks (≈1 min); the backlog alert has no other
  signal.
- Cache writes that touch more than one key go through `cache_set_many` (one pipeline), not a loop.
- `locale/` here is the baseline every service copies; a new generic key must be added to all five locale
  directories, or the services' `test_i18n.py` will not see it.

## Verify

`make lint && make test`, then at minimum `cd ../auth && make test` (JWT, role version, i18n) and
`cd ../operations && make test` (outbox, replicas, money).
