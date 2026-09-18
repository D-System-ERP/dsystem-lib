# dsystem-lib

Shared library for every dsystem-v2 Python service — local folder `D-System/lib/`, package `dsystem` (`pip install -e ../lib`). Fork of TheCargo `thecargo-lib`,
package name `dsystem`, exchange `dsystem.events`.

| Module | What it gives a service |
|---|---|
| `dsystem.models.base` | `Base`, `BaseModel`, `SoftDeleteModel`, `ReferenceModel` + column guards (string length, tz-aware datetimes) |
| `dsystem.models.{lookup,bank_account,user_replica,partner_replica,legal_entity_replica,file}` | shared table shapes and replicas |
| `dsystem.repositories.base` | `TenantRepository(db, org_id)` — every query scoped to the organization |
| `dsystem.dependencies.auth` | `get_current_user`, `get_org_id`, `Requires(resource, action)`, `Scope`, `TokenPayload`, `get_current_admin` |
| `dsystem.dependencies.{service_auth,guards,repo,upload,timezone}` | `verify_service_auth`, `or_404`, `check_version`, `make_get_repo`, uploads, timezones |
| `dsystem.permissions`, `dsystem.role_templates` | canonical resources/actions/stages and default roles |
| `dsystem.events.{outbox,consumer,envelope,schemas,user_sync,partner_sync,legal_entity_sync,replica_sync}` | transactional outbox + relay, DLQ consumer, envelope `{v, event_id, organization_id, occurred_at, actor_id, data}`, Pydantic payload contracts, replica consumers |
| `dsystem.cache` | `cache_aside`, `cache_set`, `claim_once` (event dedupe) |
| `dsystem.middleware` | `AuditMiddleware`, `IdempotencyMiddleware`, `CancelOnDisconnectMiddleware`, `RateLimitMiddleware` |
| `dsystem.audit` | `Auditable` mixin → `audit.*` events |
| `dsystem.money`, `dsystem.uom`, `dsystem.sequences`, `dsystem.schemas.values` | Decimal money, uom conversion, `next_code`, value objects |
| `dsystem.health` | `/health/live`, `/health/ready` router |
| `dsystem.exceptions`, `dsystem.handlers`, `dsystem.i18n`, `dsystem.observability` | error envelope, i18n, Sentry/request id |
| `dsystem.clients` | `ServiceClient`, `AuthServiceClient`, `SocketClient` |
| `dsystem.storage`, `dsystem.public_storage` | S3-compatible object storage (MinIO) |

```bash
make install   # venv + editable install
make lint      # ruff check/format
make test      # pytest (no external services needed)
```

Service specs that consume this library: `D-System-ERP/dsystem-docs` (`services/*.md`, §A.15).
