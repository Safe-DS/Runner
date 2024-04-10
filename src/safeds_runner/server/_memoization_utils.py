"""Module that contains the memoization utilities and functionality related to explicit ids and shared memory."""
from __future__ import annotations

from multiprocessing.shared_memory import SharedMemory
from typing import Any, TypeAlias
import uuid
import inspect
import sys
import pickle

from dataclasses import dataclass

MemoizationKey: TypeAlias = tuple[str, tuple[Any], tuple[Any]]


@dataclass(frozen=True)
class ExplicitIdentityWrapper:
    """
    Wrapper containing a value that lives in a shared memory location, and does not support a deterministic hash.

    This wrapper makes IPC actions more efficient, by only sending the shared memory location.
    The contained object is always unpickled at the receiving side.
    """
    value: Any
    memory: SharedMemory

    @classmethod
    def shared(cls, value: Any) -> ExplicitIdentityWrapper:
        """
        Create a new wrapper around the provided value.

        The provided value will be pickled and stored in shared memory, for storage in the memoization cache.
        An explicit identity should already be assigned.

        Parameters
        ----------
        value
            Object to create a shared memory based wrapper for.

        Returns
        -------
        result
            A new wrapper object containing the provided value.
        """
        _shared_memory_serialize_and_assign(value)
        return cls.existing(value)

    @classmethod
    def existing(cls, value: Any) -> ExplicitIdentityWrapper:
        """
        Create a wrapper around the provided value, by using the existing assigned shared memory location.

        Parameters
        ----------
        value
            Object to create a shared memory based wrapper for.

        Returns
        -------
        result
            A new wrapper object containing the provided value.
        """
        return cls(value, value.__ex_id_mem__)

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ExplicitIdentityWrapperLazy):
            if self.value.__ex_id__ == other.id:
                return True
            other._unpackvalue()
            return self.value == other.value
        if isinstance(other, ExplicitIdentityWrapper):
            return self.value.__ex_id__ == other.value.__ex_id__ or self.value == other.value
        if _has_explicit_identity(other):
            return self.value.__ex_id__ == other.__ex_id__
        return self.value == other

    def __sizeof__(self) -> int:
        return self.memory.size

    def __getstate__(self) -> object:
        return self.memory

    def __setstate__(self, state: object) -> None:
        object.__setattr__(self, 'memory', state)
        object.__setattr__(self, 'value', pickle.loads(self.memory.buf))
        _set_new_explicit_memory(self.value, self.memory)


@dataclass(frozen=True)
class ExplicitIdentityWrapperLazy:
    """
    Wrapper containing a value that lives in a shared memory location, and supports a deterministic hash.

    This wrapper allows to skip deserializing the contained value, if only a comparison is required, as the hash is deterministic and also sent.
    If the comparison using the explicit identity fails, the object is unpickled as a fallback solution and compared using the __eq__ function.
    """
    value: Any
    memory: SharedMemory
    id: uuid.UUID
    hash: int

    @classmethod
    def shared(cls, value: Any) -> ExplicitIdentityWrapperLazy:
        """
        Create a new wrapper around the provided value.

        The provided value will be pickled and stored in shared memory, for storage in the memoization cache.
        An explicit identity should already be assigned, and the object should be deterministically hashable.

        Parameters
        ----------
        value
            Object to create a shared memory based wrapper for.

        Returns
        -------
        result
            A new wrapper object containing the provided value.
        """
        _shared_memory_serialize_and_assign(value)
        return cls.existing(value)

    @classmethod
    def existing(cls, value: Any) -> ExplicitIdentityWrapperLazy:
        """
        Create a wrapper around the provided value, by using the existing assigned shared memory location.

        Parameters
        ----------
        value
            Object to create a shared memory based wrapper for.

        Returns
        -------
        result
            A new wrapper object containing the provided value.
        """
        return cls(value, value.__ex_id_mem__, value.__ex_id__, value.__ex_hash__)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ExplicitIdentityWrapperLazy) and self.id == other.id:
            return True
        elif isinstance(other, ExplicitIdentityWrapper) and self.id == other.value.__ex_id__:
            return True
        elif _has_explicit_identity(other) and self.id == other.__ex_id__:
            return True
        self._unpackvalue()
        if isinstance(other, ExplicitIdentityWrapperLazy):
            other._unpackvalue()
            return self.value == other.value
        elif isinstance(other, ExplicitIdentityWrapper):
            return self.value == other.value
        return self.value == other

    def __hash__(self) -> int:
        return self.hash

    def _unpackvalue(self) -> None:
        """Unpack the value contained in this wrapper, if not currently present."""
        if self.value is None:
            object.__setattr__(self, 'value', pickle.loads(self.memory.buf))
            _set_new_explicit_memory(self.value, self.memory)

    def __sizeof__(self) -> int:
        return self.memory.size

    def __getstate__(self) -> object:
        return self.memory, self.id, self.hash

    def __setstate__(self, state: tuple[SharedMemory, uuid.UUID, int]) -> None:
        memory_value, id_value, hash_value = state
        object.__setattr__(self, 'value', None)
        object.__setattr__(self, 'memory', memory_value)
        object.__setattr__(self, 'id', id_value)
        object.__setattr__(self, 'hash', hash_value)


def _is_not_primitive(value: Any) -> bool:
    """
    Check, if this value is not primitive, that can be trivially cloned.

    Parameters
    ----------
    value
        Object to check, whether it is not primitive.

    Returns
    -------
    result
        True, if the object is not primitive.
    """
    return not isinstance(value, str | int | float | type(None) | bool)


def _is_deterministically_hashable(value: Any) -> bool:
    """
    Check, whether the provided value is hashed without using the python object id.

    This check only checks, if this value is not primitive and if the value overrides the __hash__ function.

    Parameters
    ----------
    value
        Object to check, if it is (probably) deterministically hashable.

    Returns
    -------
    result
        True, if the object can be deterministically hashed.
    """
    return _is_not_primitive(value) and hasattr(value, "__class__") and value.__class__.__hash__ != object.__hash__


def _has_explicit_identity(value: Any) -> bool:
    """
    Check, whether an explicit identity was assigned to the provided object.

    Parameters
    ----------
    value
        Object to check

    Returns
    -------
    result
        Whether the object has been assigned an explicit identity.
    """
    return hasattr(value, "__ex_id__")


def _has_explicit_identity_memory(value: Any) -> bool:
    """
    Check, whether a shared memory location was assigned to the provided object.

    Parameters
    ----------
    value
        Object to check

    Returns
    -------
    result
        Whether the object has been assigned shared memory location.
    """
    return hasattr(value, "__ex_id_mem__")


def _set_new_explicit_identity_deterministic_hash(value: Any) -> None:
    """
    Assign a new explicit identity to the provided object, and assign a deterministic hash.

    Parameters
    ----------
    value
        Object to assign an explicit identity and a deterministic hash to
    """
    value.__ex_id__ = uuid.uuid4()
    value.__ex_hash__ = hash(value)


def _set_new_explicit_identity(value: Any) -> None:
    """
    Assign a new explicit identity to the provided object.

    Parameters
    ----------
    value
        Object to assign an explicit identity to
    """
    value.__ex_id__ = uuid.uuid4()


def _set_new_explicit_memory(value: Any, memory: SharedMemory) -> None:
    """
    Assign a shared memory location to the provided object.

    Parameters
    ----------
    value
        Object to assign a shared memory location to
    """
    value.__ex_id_mem__ = memory


def _shared_memory_serialize_and_assign(value: Any) -> SharedMemory:
    """
    Serialize the provided value to a shared memory location and assign this location to the provided object and return it.

    Parameters
    ----------
    value
        Any value that should be stored in a shared memory location

    Returns
    -------
    memory
        Shared Memory location containing the provided object in a serialized representation.
    """
    bytes_dump = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
    bytes_len = len(bytes_dump)
    shared_memory = SharedMemory(create=True, size=bytes_len)
    shared_memory.buf[:bytes_len] = bytes_dump
    _set_new_explicit_memory(value, shared_memory)
    return shared_memory


def _make_hashable(value: Any) -> Any:
    """
    Make a value hashable.

    Parameters
    ----------
    value
        Value to be converted.

    Returns
    -------
    converted_value:
        Converted value.
    """
    if _is_deterministically_hashable(value) and _has_explicit_identity_memory(value):
        return ExplicitIdentityWrapperLazy.existing(value)
    elif not _is_deterministically_hashable(value) and _is_not_primitive(value) and _has_explicit_identity_memory(value):
        return ExplicitIdentityWrapper.existing(value)
    elif isinstance(value, dict):
        return tuple((_make_hashable(key), _make_hashable(value)) for key, value in value.items())
    elif isinstance(value, list):
        return tuple(_make_hashable(element) for element in value)
    elif callable(value):
        # This is a band-aid solution to make callables serializable. Unfortunately, `getsource` returns more than just
        # the source code for lambdas.
        return inspect.getsource(value)
    else:
        return value


def _get_size_of_value(value: Any) -> int:
    """
    Recursively calculate the memory usage of a given value.

    Parameters
    ----------
    value
        Any value of which the memory usage should be calculated.

    Returns
    -------
    Size of the provided value in bytes
    """
    size_immediate = sys.getsizeof(value)
    if isinstance(value, dict):
        return (
            sum(map(_get_size_of_value, value.keys())) + sum(map(_get_size_of_value, value.values())) + size_immediate
        )
    elif isinstance(value, frozenset | list | set | tuple):
        return sum(map(_get_size_of_value, value)) + size_immediate
    else:
        return size_immediate


def _create_memoization_key(
    function_name: str,
    parameters: list[Any],
    hidden_parameters: list[Any],
) -> MemoizationKey:
    """
    Convert values provided to a memoized function call to a memoization key.

    Parameters
    ----------
    function_name
        Fully qualified function name
    parameters
        List of parameters passed to the function
    hidden_parameters
        List of parameters not passed to the function

    Returns
    -------
    A memoization key, which contains the lists converted to tuples
    """
    return function_name, _make_hashable(parameters), _make_hashable(hidden_parameters)


def _wrap_value_to_shared_memory(
    result: Any,
) -> Any:
    """
    Convert a value to a more easily memoizable format.

    Parameters
    ----------
    result
        Value to convert to memoizable format.

    Returns
    -------
    value
        The value in a memoizable format, wrapped if needed.
    """
    if isinstance(result, tuple):
        results: list[Any] = []
        for entry in result:
            if _is_deterministically_hashable(entry):
                _set_new_explicit_identity_deterministic_hash(entry)
                results.append(ExplicitIdentityWrapperLazy.shared(entry))
            elif _is_not_primitive(entry):
                _set_new_explicit_identity(entry)
                results.append(ExplicitIdentityWrapper.shared(entry))
            else:
                results.append(entry)
        return tuple(results)
    elif _is_deterministically_hashable(result):
        _set_new_explicit_identity_deterministic_hash(result)
        return ExplicitIdentityWrapperLazy.shared(result)
    elif _is_not_primitive(result):
        _set_new_explicit_identity(result)
        return ExplicitIdentityWrapper.shared(result)
    return result


def _unwrap_value_from_shared_memory(
    result: Any,
) -> Any:
    """
    Convert a value from the memoizable format to a usable format.

    Parameters
    ----------
    result
        Value to convert to a usable format.

    Returns
    -------
    value
        The value in a usable format, unwrapped if needed.
    """
    if isinstance(result, tuple):
        results = []
        for entry in result:
            if isinstance(entry, ExplicitIdentityWrapperLazy):
                entry._unpackvalue()
                results.append(entry.value)
            if isinstance(entry, ExplicitIdentityWrapper):
                results.append(entry.value)
        return tuple(results)
    if isinstance(result, ExplicitIdentityWrapperLazy):
        result._unpackvalue()
        return result.value
    if isinstance(result, ExplicitIdentityWrapper):
        return result.value
    return result
