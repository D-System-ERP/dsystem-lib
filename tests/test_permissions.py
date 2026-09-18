from dsystem.permissions import (
    ACTIONS,
    RESOURCE_SET,
    STAGES_BY_KIND,
    actions_for,
    build_permission_groups,
    is_known,
    ui_resource_keys,
)
from dsystem.role_templates import TEMPLATES, expand_template


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
