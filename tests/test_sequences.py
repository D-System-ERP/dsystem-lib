from dsystem.sequences import START_NUMBER, TENANT_SCOPE, format_code


def test_format_code_with_and_without_entity_prefix():
    assert format_code("SA", 10001) == "SA10001"
    assert format_code("SA", 10001, "ABC") == "ABC-SA10001"
    assert format_code("P", START_NUMBER + 1, None) == "P10001"


def test_tenant_scope_is_the_nil_uuid():
    assert str(TENANT_SCOPE) == "00000000-0000-0000-0000-000000000000"
