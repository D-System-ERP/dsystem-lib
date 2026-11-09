"""Default role blueprints seeded into every new organization.

Keys are ``"<resource>.<action>"`` and values the scope — or the scope and the
document stages it is limited to (``role_permissions.stage_filter``); anything
absent is no access. ``Admin`` is the organization's own administrator role (see
``ORG_ADMIN_ROLE_NAME``) — not the platform ``is_superuser`` flag.
"""

from typing import Final

from dsystem.permissions import ACTIONS, RESOURCES, actions_for

Grant = str | tuple[str, tuple[str, ...]]


def _full(*resources: str, scope: str = "all") -> dict[str, str]:
    return {f"{r}.{a}": scope for r in resources for a in actions_for(r)}


def _view(*resources: str, scope: str = "all") -> dict[str, str]:
    return {f"{r}.view": scope for r in resources}


def _staged(scope: str, stages: tuple[str, ...], *keys: str) -> dict[str, Grant]:
    return {key: (scope, stages) for key in keys}


ADMIN: Final[dict[str, str]] = {f"{r}.{a}": "all" for r in RESOURCES for a in actions_for(r)}

SALES: Final[dict[str, str]] = {
    **_full("partner", "bank_account", "opportunity", "project", "activity", "task", scope="own"),
    **_view("partner", "opportunity", "activity", "board", "task", "notification", "contract"),
    **{
        "partner.create": "all",
        "opportunity.create": "all",
        "project.create": "all",
        "activity.create": "all",
        "task.create": "all",
    },
    # A seller runs the whole sale flow, a colleague's draft too (2026-11-05, the owner: «sales flow dagi hamma narsani
    # to'liq control»).
    **_full("sale"),
    # A seller asks production and the buyers for what a sale lacks, and sees only the requests they sent (2026-11-04,
    # the owner).
    **_staged("own", ("request",), "manufacture.view", "manufacture.create", "purchase.view", "purchase.create"),
    **_view("product", "packaging", "warehouse", "stock", "cost_adjustment", "uom", "price_list"),
    "currency.view": "all",
    "dashboard.view": "own",
    "report.view": "own",
    "lookup.view": "all",
    "legal_entity.view": "own",
    "user.view": "all",
    "team.view": "all",
}

PURCHASE: Final[dict[str, Grant]] = {
    "project.view": "own",
    **_full("partner", "bank_account", "activity", "task", scope="own"),
    **_view("partner", "activity", "board", "task", "notification", "contract"),
    **{"partner.create": "all", "activity.create": "all", "task.create": "all"},
    # A buyer runs the whole purchase flow (2026-11-05, the owner).
    **_full("purchase"),
    # A receipt's invoice is a `sale` document at the `invoice` stage (operations `RESOURCE_BY_KIND`): the buyer
    # makes it, reads it under Purchase's «Исходящие платежи» and deletes a draft of theirs.
    **_staged("own", ("invoice",), "sale.view", "sale.create", "sale.update", "sale.delete"),
    **_view("product", "packaging", "warehouse", "stock", "cost_adjustment", "uom", "price_list", "payment"),
    # A buyer brings a product the catalogue lacks as an alternative to a specification's material (2026-11-09, the
    # owner: «buyerga + button ham qoshamiz yangi tovarni qoshib ketaolishi uchun»).
    "product.create": "all",
    "cost.view": "all",
    "dashboard.view": "own",
    "report.view": "own",
    "lookup.view": "all",
    "legal_entity.view": "own",
    "user.view": "all",
    "team.view": "all",
}

WAREHOUSE: Final[dict[str, Grant]] = {
    "project.view": "own",
    **_full("warehouse", "stock", "cost_adjustment", "inventory_count", "transfer", "write_off"),
    **_view(
        "partner",
        "sale",
        "purchase",
        "manufacture",
        "product",
        "packaging",
        "uom",
        "bom",
        "price_list",
        "notification",
        "board",
        "task",
    ),
    "sale.update": "all",
    "purchase.update": "all",
    # The warehouse makes and confirms the receipts and shipments, and asks for what is short (2026-11-04, the owner).
    **_staged("all", ("shipment",), "sale.create"),
    **_staged("all", ("request", "receipt"), "purchase.create"),
    "task.create": "all",
    "task.update": "own",
    "dashboard.view": "all",
    "report.view": "all",
    "lookup.view": "all",
    "legal_entity.view": "own",
    "user.view": "all",
    "team.view": "all",
}

ACCOUNTANT: Final[dict[str, Grant]] = {
    "project.view": "own",
    **_full("payment", "contract", "manual_entry", "currency", "bank_account"),
    **_view(
        "partner",
        "sale",
        "purchase",
        "manufacture",
        "product",
        "warehouse",
        "stock",
        "cost_adjustment",
        "inventory_count",
        "price_list",
        "notification",
    ),
    # Everything of the money, the invoices too (2026-11-04, the owner): an invoice is a `sale` at the `invoice` stage.
    **_staged("all", ("invoice",), "sale.create", "sale.update"),
    "employee.view": "all",
    "cost.view": "all",
    "partner.update": "all",
    "legal_entity.view": "own",
    "legal_entity.update": "own",
    "dashboard.view": "all",
    "report.view": "all",
    "audit.view": "all",
    "lookup.view": "all",
    "user.view": "all",
    "team.view": "all",
}

PRODUCTION: Final[dict[str, Grant]] = {
    "project.view": "own",
    **_full("manufacture", "bom"),
    **_view(
        "product",
        "packaging",
        "warehouse",
        "stock",
        "cost_adjustment",
        "uom",
        "transfer",
        "notification",
        "board",
        "task",
    ),
    "transfer.create": "all",
    "transfer.update": "own",
    # Scrap is written off from its production (`write_off:create`) and read in «Отчёт по браку» (`write_off:view`).
    "write_off.create": "all",
    "write_off.view": "own",
    # The raw materials a production lacks go to the buyers as a purchase request (2026-11-04, the owner).
    **_staged("all", ("request",), "purchase.view", "purchase.create"),
    **_staged("own", ("request",), "purchase.update"),
    "task.create": "all",
    "task.update": "own",
    "dashboard.view": "all",
    "report.view": "own",
    "lookup.view": "all",
    "legal_entity.view": "own",
    "user.view": "all",
    "team.view": "all",
}

LOADER: Final[dict[str, str]] = {
    "project.view": "own",
    **_view("sale", "purchase", "transfer", "product", "warehouse", "stock", "cost_adjustment", "notification", "task"),
    "sale.update": "all",
    "purchase.update": "all",
    "transfer.update": "all",
    "task.update": "own",
    "user.view": "all",
    "team.view": "all",
}

# The people: employees, their payslips and debts, and the users they sign in as (2026-11-04, the owner).
HR: Final[dict[str, str]] = {
    **_full("employee", "payslip", "employee_debt", "user"),
    **_view("team", "role", "notification", "board", "task"),
    "task.create": "all",
    "task.update": "own",
    "dashboard.view": "own",
    "report.view": "own",
    "lookup.view": "all",
    "legal_entity.view": "own",
}

# The design office («КТО», 2026-11-04, the owner): only the specifications, the stock levels, the catalogue and the
# projects — our product for each tender row, a new product or raw material, its specification and materials.
KTO: Final[dict[str, str]] = {
    **_full("bom"),
    **{f"product.{a}": "all" for a in ("view", "create", "update")},
    **{f"project.{a}": "all" for a in ("view", "update")},
    **_view("packaging", "uom", "stock", "notification"),
    # The project's KTO picks one of the alternatives a buyer offers for a material, inside the purchase document
    # (2026-11-09, the owner): `own` reaches the documents that ask them (operations `attrs.reviewer_ids`).
    **_staged("own", ("request", "order", "purchase"), "purchase.view"),
    "lookup.view": "all",
    "legal_entity.view": "own",
    "user.view": "all",
    "team.view": "all",
}

TEMPLATES: Final[dict[str, dict[str, Grant]]] = {
    "Admin": ADMIN,
    "Sales": SALES,
    "Purchase": PURCHASE,
    "Warehouse": WAREHOUSE,
    "Accountant": ACCOUNTANT,
    "Production": PRODUCTION,
    "Loader": LOADER,
    "HR": HR,
    "KTO": KTO,
}

# A static role's kind and the template its grants are cut from (2026-11-04, the owner: a role is one of these, or
# its own — a role with no kind keeps the grants it is given).
ROLE_KINDS: Final[dict[str, str]] = {
    "admin": "Admin",
    "sale": "Sales",
    "purchase": "Purchase",
    "manufacture": "Production",
    "warehouse": "Warehouse",
    "accountant": "Accountant",
    "hr": "HR",
    "kto": "KTO",
}


def template_grants(template: dict[str, Grant]) -> dict[tuple[str, str], tuple[str, tuple[str, ...] | None]]:
    """Every grant of a template as ``{(resource, action): (scope, stages)}`` — ``stages`` None for every stage."""
    grants: dict[tuple[str, str], tuple[str, tuple[str, ...] | None]] = {}
    for key, grant in template.items():
        resource, action = key.split(".", 1)
        grants[(resource, action)] = (grant, None) if isinstance(grant, str) else grant
    return grants


def expand_template(template: dict[str, Grant]) -> dict[str, dict[str, str | None]]:
    nested: dict[str, dict[str, str | None]] = {r: {a: None for a in ACTIONS} for r in RESOURCES}
    for (resource, action), (scope, _) in template_grants(template).items():
        if resource in nested and action in nested[resource]:
            nested[resource][action] = scope
    return nested
