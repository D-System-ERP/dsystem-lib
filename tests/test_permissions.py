from dsystem.permissions import (
    ACTIONS,
    RESOURCE_SET,
    STAGES_BY_KIND,
    actions_for,
    build_permission_groups,
    is_known,
    ui_resource_keys,
)
from dsystem.role_templates import ROLE_KINDS, TEMPLATES, expand_template, template_grants


def test_ui_groups_cover_every_resource_exactly():
    assert ui_resource_keys() == RESOURCE_SET


def test_templates_only_reference_known_permissions():
    for name, template in TEMPLATES.items():
        for key in template:
            resource, action = key.split(".", 1)
            assert is_known(resource, action), f"{name}: {key}"


def test_admin_template_grants_everything():
    nested = expand_template(TEMPLATES["Admin"])
    for resource, actions in nested.items():
        for action in actions_for(resource):
            assert actions[action] == "all", (resource, action)


def test_matrix_carries_stage_filters_for_documents():
    groups = build_permission_groups({("sale", "view"): "own"}, {"sale": ["offer", "order"]})
    sale = next(r for g in groups for r in g["resources"] if r["key"] == "sale")
    assert sale["actions"]["view"] == "own"
    assert sale["stages"] == ["offer", "order"]
    assert sale["available_stages"] == list(STAGES_BY_KIND["sale"])
    dashboard = next(r for g in groups for r in g["resources"] if r["key"] == "dashboard")
    assert list(dashboard["actions"]) == ["view"]
    assert "stages" not in dashboard
    assert set(ACTIONS) == {"view", "create", "update", "delete"}


def test_only_who_buys_and_keeps_the_books_sees_cost():
    seeing = {name for name, template in TEMPLATES.items() if template.get("cost.view")}
    assert seeing == {"Admin", "Purchase", "Accountant"}
    assert actions_for("cost") == ("view",)


def test_a_template_that_makes_tasks_sees_their_boards():
    for name, template in TEMPLATES.items():
        if template.get("task.create"):
            assert template.get("board.view"), name


def test_every_template_names_people():
    for name, template in TEMPLATES.items():
        assert template.get("user.view") == "all", name


def test_template_stages_are_the_resources_own():
    for name, template in TEMPLATES.items():
        for (resource, action), (_, stages) in template_grants(template).items():
            if stages is not None:
                assert set(stages) <= set(STAGES_BY_KIND[resource]), f"{name}: {resource}.{action}"


def test_a_buyer_invoices_receipts_and_sells_nothing():
    grants = template_grants(TEMPLATES["Purchase"])
    for action in ("view", "create", "update", "delete"):
        assert grants[("sale", action)] == ("own", ("invoice",))


def test_each_static_kind_runs_its_own_flow_whole():
    for name, resource in (("Sales", "sale"), ("Purchase", "purchase"), ("Production", "manufacture")):
        grants = template_grants(TEMPLATES[name])
        for action in ("view", "create", "update", "delete"):
            assert grants[(resource, action)] == ("all", None), f"{name}: {resource}.{action}"


def test_production_writes_off_its_scrap():
    production = TEMPLATES["Production"]
    assert production["write_off.create"] == "all"
    assert production["write_off.view"] == "own"


def test_sales_reads_no_payments():
    assert not any(key.startswith("payment.") for key in TEMPLATES["Sales"])


def test_only_the_warehouse_and_the_books_see_inventory_counts():
    seeing = {name for name, template in TEMPLATES.items() if template.get("inventory_count.view")}
    assert seeing == {"Admin", "Warehouse", "Accountant"}


def test_hr_keeps_the_people_and_their_users():
    hr = TEMPLATES["HR"]
    for resource in ("employee", "payslip", "employee_debt", "user"):
        for action in actions_for(resource):
            assert hr[f"{resource}.{action}"] == "all", (resource, action)
    assert hr["role.view"] == "all"
    assert "role.create" not in hr


def test_a_seller_sends_requests_and_sees_only_their_own():
    grants = template_grants(TEMPLATES["Sales"])
    for resource in ("manufacture", "purchase"):
        for action in ("view", "create"):
            assert grants[(resource, action)] == ("own", ("request",)), (resource, action)
        assert (resource, "update") not in grants


def test_production_and_the_warehouse_ask_the_buyers():
    production = template_grants(TEMPLATES["Production"])
    warehouse = template_grants(TEMPLATES["Warehouse"])
    assert production[("purchase", "create")] == ("all", ("request",))
    assert production[("purchase", "view")] == ("all", ("request",))
    assert warehouse[("purchase", "create")] == ("all", ("request", "receipt"))


def test_the_warehouse_makes_and_confirms_receipts_and_shipments():
    warehouse = template_grants(TEMPLATES["Warehouse"])
    assert warehouse[("sale", "create")] == ("all", ("shipment",))
    assert warehouse[("sale", "update")] == ("all", None)
    assert warehouse[("purchase", "update")] == ("all", None)


def test_the_accountant_makes_invoices():
    accountant = template_grants(TEMPLATES["Accountant"])
    assert accountant[("sale", "create")] == ("all", ("invoice",))
    assert accountant[("sale", "view")] == ("all", None)


def test_kto_keeps_specifications_stock_catalogue_and_projects_only():
    kto = TEMPLATES["KTO"]
    resources = {key.split(".", 1)[0] for key in kto}
    assert resources == {
        "bom",
        "product",
        "project",
        "packaging",
        "uom",
        "stock",
        "notification",
        "lookup",
        "legal_entity",
        "user",
        "team",
    }
    assert kto["project.update"] == "all" and "project.delete" not in kto
    assert not any(key.startswith(("cost.", "price_list.", "sale.", "purchase.")) for key in kto)


def test_every_role_kind_is_cut_from_a_template():
    assert set(ROLE_KINDS.values()) <= set(TEMPLATES)
    assert "Loader" not in ROLE_KINDS.values()


def test_expand_template_keeps_the_scope_of_a_staged_grant():
    assert expand_template(TEMPLATES["Purchase"])["sale"]["view"] == "own"


def test_invoices_and_refunds_have_a_stage_of_their_own():
    assert STAGES_BY_KIND["sale"][-2:] == ("invoice", "refund")
    assert STAGES_BY_KIND["purchase"][-1] == "refund"
