"""Canonical permission vocabulary for every dsystem service.

One source of truth: the auth service seeds the ``permissions`` table from
``RESOURCES`` × ``ACTIONS``, every service checks ``Requires(resource, action)``
against the JWT, and the admin UI renders the matrix from ``GROUPS``. Adding a
resource means appending it here, adding it to a group, and re-running the auth
seed — nothing else.
"""

from typing import Final

ORG_ADMIN_ROLE_NAME: Final[str] = "Admin"

ACTIONS: Final[tuple[str, ...]] = ("view", "create", "update", "delete")

SCOPES: Final[tuple[str, ...]] = ("all", "own", "team")

NO_ACCESS: Final[str] = "none"

# Document stages per stage-filterable resource. A role may restrict a
# permission to a subset of stages (role_permissions.stage_filter); the JWT
# carries it as ``ps`` and ``Scope.check_stage`` enforces it.
STAGES_BY_KIND: Final[dict[str, tuple[str, ...]]] = {
    "sale": ("offer", "order", "sale", "shipment"),
    "purchase": ("request", "order", "purchase", "receipt"),
    "manufacture": ("request", "order", "production"),
}

STAGE_FILTERABLE_RESOURCES: Final[frozenset[str]] = frozenset(STAGES_BY_KIND)

RESOURCES: Final[tuple[str, ...]] = (
    "partner",
    "bank_account",
    "opportunity",
    "activity",
    "notification",
    "board",
    "task",
    "sale",
    "purchase",
    "product",
    "packaging",
    "warehouse",
    "stock",
    "uom",
    "price_list",
    "bom",
    "manufacture",
    "transfer",
    "write_off",
    "payment",
    "contract",
    "manual_entry",
    "currency",
    "employee",
    "payslip",
    "employee_debt",
    "dashboard",
    "report",
    "user",
    "team",
    "role",
    "legal_entity",
    "settings",
    "lookup",
    "audit",
)

RESOURCE_SET: Final[frozenset[str]] = frozenset(RESOURCES)
ACTION_SET: Final[frozenset[str]] = frozenset(ACTIONS)
SCOPE_SET: Final[frozenset[str]] = frozenset(SCOPES)


RESOURCE_ACTIONS: Final[dict[str, tuple[str, ...]]] = {
    "dashboard": ("view",),
    "report": ("view",),
    "audit": ("view",),
    "settings": ("view", "update"),
}


def actions_for(resource: str) -> tuple[str, ...]:
    return RESOURCE_ACTIONS.get(resource, ACTIONS)


def is_known(resource: str, action: str) -> bool:
    return resource in RESOURCE_SET and action in actions_for(resource)


def stages_for(resource: str) -> tuple[str, ...] | None:
    return STAGES_BY_KIND.get(resource)


GROUPS: Final[list[dict]] = [
    {
        "title": "CRM",
        "resources": [
            {"key": "partner", "label": "Partners"},
            {"key": "bank_account", "label": "Bank Accounts"},
            {"key": "opportunity", "label": "Opportunities"},
            {"key": "activity", "label": "Activities"},
            {"key": "notification", "label": "Notifications"},
            {"key": "board", "label": "Boards"},
            {"key": "task", "label": "Tasks"},
        ],
    },
    {
        "title": "SALES",
        "resources": [
            {"key": "sale", "label": "Sales"},
        ],
    },
    {
        "title": "PURCHASE",
        "resources": [
            {"key": "purchase", "label": "Purchases"},
        ],
    },
    {
        "title": "INVENTORY",
        "resources": [
            {"key": "product", "label": "Products"},
            {"key": "packaging", "label": "Packagings"},
            {"key": "warehouse", "label": "Warehouses"},
            {"key": "stock", "label": "Stock"},
            {"key": "uom", "label": "Units of Measure"},
            {"key": "price_list", "label": "Price Lists"},
            {"key": "bom", "label": "Bills of Materials"},
        ],
    },
    {
        "title": "PRODUCTION",
        "resources": [
            {"key": "manufacture", "label": "Manufacturing"},
            {"key": "transfer", "label": "Transfers"},
            {"key": "write_off", "label": "Write-offs"},
        ],
    },
    {
        "title": "FINANCE",
        "resources": [
            {"key": "payment", "label": "Payments"},
            {"key": "contract", "label": "Contracts"},
            {"key": "manual_entry", "label": "Manual Entries"},
            {"key": "currency", "label": "Exchange Rates"},
        ],
    },
    {
        "title": "HR",
        "resources": [
            {"key": "employee", "label": "Employees"},
            {"key": "payslip", "label": "Payslips"},
            {"key": "employee_debt", "label": "Employee Debts"},
        ],
    },
    {
        "title": "ANALYTICS",
        "resources": [
            {"key": "dashboard", "label": "Dashboard"},
            {"key": "report", "label": "Reports"},
        ],
    },
    {
        "title": "SYSTEM",
        "resources": [
            {"key": "user", "label": "Users"},
            {"key": "team", "label": "Teams"},
            {"key": "role", "label": "Roles"},
            {"key": "legal_entity", "label": "Legal Entities"},
            {"key": "settings", "label": "Settings"},
            {"key": "lookup", "label": "Lookups"},
            {"key": "audit", "label": "Audit"},
        ],
    },
]


def ui_resource_keys() -> set[str]:
    keys: set[str] = set()
    for group in GROUPS:
        for resource in group["resources"]:
            keys.add(resource["key"])
            for child in resource.get("children") or []:
                keys.add(child["key"])
    return keys


def _resource_node(node: dict, scopes: dict[tuple[str, str], str], stages: dict | None) -> dict:
    key = node["key"]
    out: dict = {
        "key": key,
        "label": node["label"],
        "actions": {action: scopes.get((key, action), NO_ACCESS) for action in actions_for(key)},
    }
    if key in STAGE_FILTERABLE_RESOURCES:
        out["stages"] = list((stages or {}).get(key) or ()) or None
        out["available_stages"] = list(STAGES_BY_KIND[key])
    children = node.get("children")
    if children:
        out["children"] = [_resource_node(child, scopes, stages) for child in children]
    return out


def build_permission_groups(
    scopes: dict[tuple[str, str], str],
    stages: dict[str, list[str] | None] | None = None,
) -> list[dict]:
    """Arrange flat ``(resource, action) -> scope`` grants as the admin matrix.

    Every resource appears even when not granted so the UI renders the full
    grid from this alone; stage-filterable rows also carry the stage subset.
    """
    return [
        {
            "title": group["title"],
            "resources": [_resource_node(resource, scopes, stages) for resource in group["resources"]],
        }
        for group in GROUPS
    ]


_ui_keys = ui_resource_keys()
_ghost = _ui_keys - RESOURCE_SET
assert not _ghost, f"permissions.GROUPS references non-canonical resources: {sorted(_ghost)}"
_missing = RESOURCE_SET - _ui_keys
assert not _missing, f"permissions.GROUPS missing canonical resources: {sorted(_missing)}"
_bad_ra = {r for r in RESOURCE_ACTIONS if r not in RESOURCE_SET} | {
    a for acts in RESOURCE_ACTIONS.values() for a in acts if a not in ACTION_SET
}
assert not _bad_ra, f"permissions.RESOURCE_ACTIONS has non-canonical entries: {sorted(_bad_ra)}"
_bad_stage = set(STAGES_BY_KIND) - RESOURCE_SET
assert not _bad_stage, f"permissions.STAGES_BY_KIND has non-canonical resources: {sorted(_bad_stage)}"
