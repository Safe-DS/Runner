import sys
from typing import Any, Type

import pytest
import base64
import pickle
from safeds.data.image.containers import Image
from safeds.data.tabular.containers import Table

from safeds_runner.server._memoization_utils import _is_not_primitive, _is_deterministically_hashable, _has_explicit_identity, _set_new_explicit_identity, _set_new_explicit_identity_deterministic_hash, _shared_memory_serialize_and_assign, _has_explicit_identity_memory, _make_hashable, ExplicitIdentityWrapperLazy, ExplicitIdentityWrapper, _get_size_of_value, _wrap_value_to_shared_memory, _unwrap_value_from_shared_memory


@pytest.mark.parametrize(
    argnames="value,primitive",
    argvalues=[
        (0, True),
        (1.0, True),
        (True, True),
        (None, True),
        ("ab", True),
        (object(), False),
    ],
    ids=[
        "value_int", "value_float", "value_boolean", "value_none", "value_string", "value_object"
    ],
)
def test_is_not_primitive(value: Any, primitive: bool) -> None:
    assert _is_not_primitive(value) != primitive


@pytest.mark.parametrize(
    argnames="value,deterministically_hashable",
    argvalues=[
        (0, False),
        (1.0, False),
        (True, False),
        (None, False),
        ("ab", False),
        (object(), False),
        (Table(), True),
        (Image.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC",
            ),
        ), True)
    ],
    ids=[
        "value_int", "value_float", "value_boolean", "value_none", "value_string", "value_object", "value_table", "value_image"
    ],
)
def test_is_deterministically_hashable(value: Any, deterministically_hashable: bool) -> None:
    assert _is_deterministically_hashable(value) == deterministically_hashable


@pytest.mark.parametrize(
    argnames="value",
    argvalues=[
        Table(),
        Image.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC",
            ),
        )
    ],
    ids=[
        "value_table_plain", "value_image_plain"
    ],
)
def test_has_explicit_identity(value: Any) -> None:
    assert not _has_explicit_identity(value)
    _set_new_explicit_identity(value)
    assert _has_explicit_identity(value)


@pytest.mark.parametrize(
    argnames="value",
    argvalues=[
        Table(),
        Image.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC",
            ),
        )
    ],
    ids=[
        "value_table_plain", "value_image_plain"
    ],
)
def test_explicit_identity_deterministic_hash(value: Any) -> None:
    assert not _has_explicit_identity(value)
    _set_new_explicit_identity_deterministic_hash(value)
    assert _has_explicit_identity(value)
    assert hash(value) == value.__ex_hash__


@pytest.mark.parametrize(
    argnames="value",
    argvalues=[
        Table(),
        Image.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC",
            ),
        )
    ],
    ids=[
        "value_table_plain", "value_image_plain"
    ],
)
def test_explicit_identity_shared_memory(value: Any) -> None:
    _shared_memory_serialize_and_assign(value)
    assert _has_explicit_identity_memory(value)


@pytest.mark.parametrize(
    argnames="value,hashable,exception",
    argvalues=[
        (Table(), True, None),
        (Image.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC",
            ),
        ), True, None),
        ({"a": "b"}, False, TypeError),
        (["a", "b", "c"], False, TypeError),
        (lambda a, b: a + b, False, pickle.PicklingError)
    ],
    ids=[
        "value_table_hashable", "value_image_hashable", "value_dict_unhashable", "value_list_unhashable", "value_lambda_unhashable"
    ],
)
def test_make_hashable_non_wrapper(value: Any, hashable: bool, exception: Type[BaseException]) -> None:
    if not hashable:
        with pytest.raises(exception):
            hash(value)
            pickle.dumps(value)
    else:
        assert hash(value) is not None
    hashable_value = _make_hashable(value)
    assert hash(hashable_value) is not None
    if hashable:
        assert hashable_value == value


@pytest.mark.parametrize(
    argnames="value,wrapper",
    argvalues=[
        (Table(), True),
        (Image.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC",
            ),
        ), True),
    ],
    ids=[
        "value_table", "value_image",
    ],
)
def test_make_hashable_wrapper(value: Any, wrapper: bool) -> None:
    _set_new_explicit_identity_deterministic_hash(value)
    ExplicitIdentityWrapperLazy.shared(value)
    hashable_value = _make_hashable(value)
    if wrapper:
        assert isinstance(hashable_value, ExplicitIdentityWrapperLazy | ExplicitIdentityWrapper)
    assert hashable_value == value


@pytest.mark.parametrize(
    argnames="value,expected_size",
    argvalues=[
        (1, 0),
        ({}, 0),
        ({"a": "b"}, sys.getsizeof({})),
        ([], 0),
        ([1, 2, 3], sys.getsizeof([])),
        ((), 0),
        ((1, 2, 3), sys.getsizeof(())),
        (set(), 0),
        ({1, 2, 3}, sys.getsizeof(set())),
        (frozenset(), 0),
        (frozenset({1, 2, 3}), sys.getsizeof(frozenset())),
    ],
    ids=[
        "immediate",
        "dict_empty",
        "dict_values",
        "list_empty",
        "list_values",
        "tuple_empty",
        "tuple_values",
        "set_empty",
        "set_values",
        "frozenset_empty",
        "frozenset_values",
    ],
)
def test_memory_usage(value: Any, expected_size: int) -> None:
    assert _get_size_of_value(value) > expected_size


@pytest.mark.parametrize(
    argnames="value",
    argvalues=[
        1,
        [1, 2, 3],
        (1, 2, 3),
        Table(),
        (Table(), Table()),
        {"a": Table()},
        {"a", "b", Table()},
        frozenset({"a", "b", Table()})
    ],
    ids=[
        "int",
        "list",
        "tuple",
        "table",
        "tuple_table",
        "dict",
        "set",
        "frozenset"
    ],
)
def test_wrap_value_to_shared_memory(value: Any) -> None:
    def _delete_unpackvalue_field(wrapped_object: Any) -> None:
        if isinstance(wrapped_object, ExplicitIdentityWrapperLazy):
            object.__setattr__(wrapped_object, 'value', None)
        if isinstance(wrapped_object, tuple | list | set | frozenset):
            for entry in wrapped_object:
                _delete_unpackvalue_field(entry)
        if isinstance(wrapped_object, dict):
            for key, dict_value in wrapped_object.items():
                _delete_unpackvalue_field(key)
                _delete_unpackvalue_field(dict_value)

    wrapped = _wrap_value_to_shared_memory(value)
    _delete_unpackvalue_field(wrapped)
    assert wrapped == value
    _delete_unpackvalue_field(wrapped)
    unwrapped = _unwrap_value_from_shared_memory(wrapped)
    assert unwrapped == value


class NonPrimitiveObject:
    pass


@pytest.mark.parametrize(
    argnames="value,wrapper",
    argvalues=[
        (NonPrimitiveObject(), True),
    ],
    ids=[
        "object",
    ],
)
def test_make_hashable_wrapper_nonlazy(value: Any, wrapper: bool) -> None:
    _set_new_explicit_identity(value)
    ExplicitIdentityWrapper.shared(value)
    hashable_value = _make_hashable(value)
    if wrapper:
        assert isinstance(hashable_value, ExplicitIdentityWrapperLazy | ExplicitIdentityWrapper)
    assert hashable_value == value


@pytest.mark.parametrize(
    argnames="value",
    argvalues=[
        NonPrimitiveObject()
    ],
    ids=[
        "object"
    ],
)
def test_wrap_value_to_shared_memory_non_deterministic(value: Any) -> None:
    wrapped = _wrap_value_to_shared_memory(value)
    wrapped2 = _wrap_value_to_shared_memory(value)
    assert wrapped == wrapped2
    unwrapped = _unwrap_value_from_shared_memory(wrapped)
    assert unwrapped is not None


@pytest.mark.parametrize(
    argnames="value",
    argvalues=[
        1,
        [1, 2, 3],
        (1, 2, 3),
        Table(),
        (Table(), Table()),
        {"a": Table()},
        {"a", "b", Table()},
        frozenset({"a", "b", Table()})
    ],
    ids=[
        "int",
        "list",
        "tuple",
        "table",
        "tuple_table",
        "dict",
        "set",
        "frozenset"
    ],
)
def test_serialize_value_to_shared_memory(value: Any) -> None:
    _wrapped = _wrap_value_to_shared_memory(value)
    serialized = pickle.dumps(_wrapped)
    unserialized_wrapped = pickle.loads(serialized)
    assert unserialized_wrapped == value
    unwrapped = _unwrap_value_from_shared_memory(unserialized_wrapped)
    assert unwrapped == value


@pytest.mark.parametrize(
    argnames="value",
    argvalues=[
        NonPrimitiveObject()
    ],
    ids=[
        "object"
    ],
)
def test_serialize_value_to_shared_memory_non_lazy(value: Any) -> None:
    _wrapped = _wrap_value_to_shared_memory(value)
    serialized = pickle.dumps(_wrapped)
    unserialized_wrapped = pickle.loads(serialized)
    unserialized_wrapped2 = pickle.loads(serialized)
    assert unserialized_wrapped == unserialized_wrapped2
    unwrapped = _unwrap_value_from_shared_memory(unserialized_wrapped)
    assert unwrapped is not None


@pytest.mark.parametrize(
    argnames="value",
    argvalues=[
        Table(),
        Image.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC",
            ),
        ),
    ],
    ids=[
        "value_table", "value_image",
    ],
)
def test_compare_wrapper_to_lazy(value: Any) -> None:
    _set_new_explicit_identity_deterministic_hash(value)
    wrapper0 = ExplicitIdentityWrapper.shared(value)
    wrapper1 = ExplicitIdentityWrapperLazy.shared(value)
    assert wrapper0 == wrapper0
    assert wrapper1 == wrapper1
    # Cross Compare
    assert wrapper0 == wrapper1
    assert wrapper1 == wrapper0
    wrapper0_reserialized = pickle.loads(pickle.dumps(wrapper0))
    wrapper1_reserialized = pickle.loads(pickle.dumps(wrapper1))
    assert wrapper0_reserialized == wrapper1_reserialized
    wrapper0_reserialized = pickle.loads(pickle.dumps(wrapper0))
    wrapper1_reserialized = pickle.loads(pickle.dumps(wrapper1))
    assert wrapper1_reserialized == wrapper0_reserialized


@pytest.mark.parametrize(
    argnames="value1,value2",
    argvalues=[
        (Table(), Table()),
        (Image.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC",
            ),
        ), Image.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC",
            ),
        ))
    ],
    ids=[
        "value_table", "value_image",
    ],
)
def test_compare_wrapper_to_lazy_multi(value1: Any, value2: Any) -> None:
    _set_new_explicit_identity_deterministic_hash(value1)
    _set_new_explicit_identity_deterministic_hash(value2)
    wrapper0_value1 = ExplicitIdentityWrapper.shared(value1)
    wrapper1_value1 = ExplicitIdentityWrapperLazy.shared(value1)
    wrapper0_value2 = ExplicitIdentityWrapper.shared(value2)
    wrapper1_value2 = ExplicitIdentityWrapperLazy.shared(value2)
    # Cross Compare
    assert wrapper0_value1 == wrapper0_value2
    assert wrapper1_value1 == wrapper1_value2
    assert wrapper0_value2 == wrapper1_value1
    assert wrapper1_value2 == wrapper0_value1
    # Cross Compare + serialize/deserialize cycle
    wrapper0_reserialized_value1 = pickle.loads(pickle.dumps(wrapper0_value1))
    wrapper1_reserialized_value1 = pickle.loads(pickle.dumps(wrapper1_value1))
    wrapper0_reserialized_value2 = pickle.loads(pickle.dumps(wrapper0_value2))
    wrapper1_reserialized_value2 = pickle.loads(pickle.dumps(wrapper1_value2))
    assert wrapper0_reserialized_value1 == wrapper0_reserialized_value2
    assert wrapper1_reserialized_value2 == wrapper1_reserialized_value1
    assert wrapper1_reserialized_value2 == wrapper0_reserialized_value1
    assert wrapper1_reserialized_value1 == wrapper0_reserialized_value2
    wrapper0_reserialized_value1 = pickle.loads(pickle.dumps(wrapper0_value1))
    wrapper1_reserialized_value1 = pickle.loads(pickle.dumps(wrapper1_value1))
    wrapper0_reserialized_value2 = pickle.loads(pickle.dumps(wrapper0_value2))
    wrapper1_reserialized_value2 = pickle.loads(pickle.dumps(wrapper1_value2))
    assert wrapper0_reserialized_value2 == wrapper0_reserialized_value1
    assert wrapper1_reserialized_value1 == wrapper1_reserialized_value2
    assert wrapper0_reserialized_value1 == wrapper1_reserialized_value2
    assert wrapper0_reserialized_value2 == wrapper1_reserialized_value1
    # Compare against object
    wrapper0_reserialized_value1 = pickle.loads(pickle.dumps(wrapper0_value1))
    wrapper1_reserialized_value1 = pickle.loads(pickle.dumps(wrapper1_value1))
    wrapper0_reserialized_value2 = pickle.loads(pickle.dumps(wrapper0_value2))
    wrapper1_reserialized_value2 = pickle.loads(pickle.dumps(wrapper1_value2))
    assert wrapper0_reserialized_value1 == value1
    assert wrapper1_reserialized_value1 == value1
    assert wrapper0_reserialized_value2 == value1
    assert wrapper1_reserialized_value2 == value1


@pytest.mark.parametrize(
    argnames="value1,value2",
    argvalues=[
        (Table(), Table()),
        (Image.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC",
            ),
        ), Image.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC",
            ),
        ))
    ],
    ids=[
        "value_table", "value_image",
    ],
)
def test_wrapper_hash(value1: Any, value2: Any) -> None:
    _set_new_explicit_identity_deterministic_hash(value1)
    _set_new_explicit_identity(value2)
    wrapper0 = ExplicitIdentityWrapperLazy.shared(value1)
    wrapper1 = ExplicitIdentityWrapper.shared(value2)
    assert hash(wrapper0) == hash(value1)
    assert hash(wrapper1) == hash(value2)
    assert hash(wrapper0) == hash(wrapper1)


@pytest.mark.parametrize(
    argnames="value",
    argvalues=[
        Table(),
        Image.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC",
            ),
        )
    ],
    ids=[
        "value_table", "value_image",
    ],
)
def test_wrapper_size(value: Any) -> None:
    _set_new_explicit_identity_deterministic_hash(value)
    wrapper0 = ExplicitIdentityWrapperLazy.shared(value)
    wrapper1 = ExplicitIdentityWrapper.shared(value)
    assert sys.getsizeof(wrapper0) > sys.getsizeof(object())
    assert sys.getsizeof(wrapper1) > sys.getsizeof(object())
