"""Default role blueprints seeded into every new organization.

Keys are ``"<resource>.<action>"`` and values the scope; anything absent is no
access. ``Admin`` is the organization's own administrator role (see
``ORG_ADMIN_ROLE_NAME``) — not the platform ``is_superuser`` flag.
"""

from typing import Final

from dsystem.permissions import ACTIONS, RESOURCES, actions_for


def _full(*resources: str, scope: str = "all") -> dict[str, str]:
    return {f"{r}.{a}": scope for r in resources for a in actions_for(r)}


def _view(*resources: str, scope: str = "all") -> dict[str, str]:
    return {f"{r}.view": scope for r in resources}


ADMIN: Final[dict[str, str]] = {f"{r}.{a}": "all" for r in RESOURCES for a in actions_for(r)}

SALES: Final[dict[str, str]] = {
    **_full("partner", "bank_account", "opportunity", "activity", "task", scope="own"),
    **_view("partner", "opportunity", "activity", "board", "task", "notification", "contract"),
    **{"partner.create": "all", "opportunity.create": "all", "activity.create": "all", "task.create": "all"},
    **{f"sale.{a}": "own" for a in ("view", "create", "update")},
    **_view("product", "packaging", "warehouse", "stock", "uom", "price_list", "payment"),
    "dashboard.view": "own",
    "report.view": "own",
    "lookup.view": "all",
    "legal_entity.view": "all",
    "user.view": "all",
    "team.view": "all",
}

PURCHASE: Final[dict[str, str]] = {
    **_full("partner", "bank_account", "activity", "task", scope="own"),
    **_view("partner", "activity", "board", "task", "notification", "contract"),
    **{"partner.create": "all", "activity.create": "all", "task.create": "all"},
    **{f"purchase.{a}": "own" for a in ("view", "create", "update")},
    **_view("product", "packaging", "warehouse", "stock", "uom", "price_list", "payment"),
    "product.create": "all",
    "product.update": "all",
    "dashboard.view": "own",
    "report.view": "own",
    "lookup.view": "all",
    "legal_entity.view": "all",
    "user.view": "all",
    "team.view": "all",
}

WAREHOUSE: Final[dict[str, str]] = {
    **_full("product", "packaging", "warehouse", "stock", "uom", "transfer", "write_off"),
    **_view("partner", "sale", "purchase", "manufacture", "bom", "price_list", "notification", "task"),
    "sale.update": "all",
    "purchase.update": "all",
    "task.create": "all",
    "task.update": "own",
    "dashboard.view": "all",
    "report.view": "all",
    "lookup.view": "all",
    "legal_entity.view": "all",
    "user.view": "all",
    "team.view": "all",
}

ACCOUNTANT: Final[dict[str, str]] = {
    **_full("payment", "contract", "manual_entry", "currency", "bank_account"),
    **_view(
        "partner", "sale", "purchase", "manufacture", "product", "warehouse", "stock", "price_list", "notification"
    ),
    **_full("payslip", "employee_debt"),
    "employee.view": "all",
    "partner.update": "all",
    "legal_entity.view": "all",
    "legal_entity.update": "all",
    "dashboard.view": "all",
    "report.view": "all",
    "audit.view": "all",
    "lookup.view": "all",
    "lookup.create": "all",
    "lookup.update": "all",
    "user.view": "all",
    "team.view": "all",
}

PRODUCTION: Final[dict[str, str]] = {
    **_full("manufacture", "bom"),
    **_view("product", "packaging", "warehouse", "stock", "uom", "transfer", "notification", "task"),
    "transfer.create": "all",
    "transfer.update": "own",
    "task.create": "all",
    "task.update": "own",
    "dashboard.view": "all",
    "report.view": "own",
    "lookup.view": "all",
    "legal_entity.view": "all",
    "user.view": "all",
    "team.view": "all",
}

LOADER: Final[dict[str, str]] = {
    **_view("sale", "purchase", "transfer", "product", "warehouse", "stock", "notification", "task"),
    "sale.update": "all",
    "purchase.update": "all",
    "transfer.update": "all",
    "task.update": "own",
}

TEMPLATES: Final[dict[str, dict[str, str]]] = {
    "Admin": ADMIN,
    "Sales": SALES,
    "Purchase": PURCHASE,
    "Warehouse": WAREHOUSE,
    "Accountant": ACCOUNTANT,
    "Production": PRODUCTION,
    "Loader": LOADER,
}


def expand_template(template: dict[str, str]) -> dict[str, dict[str, str | None]]:
    nested: dict[str, dict[str, str | None]] = {r: {a: None for a in ACTIONS} for r in RESOURCES}
    for key, scope in template.items():
        resource, action = key.split(".", 1)
        if resource in nested and action in nested[resource]:
            nested[resource][action] = scope
    return nested
