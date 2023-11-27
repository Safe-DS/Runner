from safeds_runner.server.pipeline_manager import _get_placeholder_type


def test_type_boolean():
    assert _get_placeholder_type(True) == "Boolean"
    assert _get_placeholder_type(False) == "Boolean"


def test_type_float():
    assert _get_placeholder_type(1.23) == "Float"
    assert _get_placeholder_type(4.156e5) == "Float"
    assert _get_placeholder_type(-1.23e5) == "Float"


def test_type_int():
    assert _get_placeholder_type(1) == "Int"
    assert _get_placeholder_type(-2) == "Int"
    assert _get_placeholder_type(0) == "Int"


def test_type_string():
    assert _get_placeholder_type("abc") == "String"
    assert _get_placeholder_type("18") == "String"
    assert _get_placeholder_type("96.51615") == "String"
    assert _get_placeholder_type("True") == "String"
    assert _get_placeholder_type("False") == "String"
    assert _get_placeholder_type("1.3e5") == "String"


def test_type_other():
    assert _get_placeholder_type(object()) == "object"
    assert _get_placeholder_type(None) == "Null"
    assert _get_placeholder_type(lambda x: x + 1) == "Callable"
