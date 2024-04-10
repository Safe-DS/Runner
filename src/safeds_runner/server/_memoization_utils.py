"""Module that contains the memoization utilities and functionality related to explicit ids and shared memory."""
from __future__ import annotations

from multiprocessing.shared_memory import SharedMemory
from typing import Any, TypeAlias
import uuid
import inspect
import sys

from dataclasses import dataclass

MemoizationKey: TypeAlias = tuple[str, tuple[Any], tuple[Any]]

# Contains classes that can be lazily compared, as they implement a deterministic hash
explicit_identity_classes = frozenset([
    "safeds.data.tabular.containers._table.Table",
    "safeds.data.tabular.containers._row.Row",
    "safeds.data.tabular.containers._column.Column"
    "safeds.data.tabular.containers._tagged_table.TaggedTable",
    "safeds.data.tabular.containers._time_series.TimeSeries",
    "safeds.data.tabular.transformation._discretizer.Discretizer",
    "safeds.data.tabular.transformation._imputer.Imputer",
    "safeds.data.tabular.transformation._invertible_table_transformer.InvertibleTableTransformer",
    "safeds.data.tabular.transformation._label_encoder.LabelEncoder",
    "safeds.data.tabular.transformation._one_hot_encoder.OneHotEncoder",
    "safeds.data.tabular.transformation._range_scaler.RangeScaler",
    "safeds.data.tabular.transformation._standard_scaler.StandardScaler",
    "safeds.data.tabular.transformation._table_transformer.TableTransformer",
    "safeds.ml.classical.classification._ada_boost.AdaBoost",
    "safeds.ml.classical.classification._classifier.Classifier",
    "safeds.ml.classical.classification._decision_tree.DecisionTree",
    "safeds.ml.classical.classification._gradient_boosting.GradientBoosting",
    "safeds.ml.classical.classification._k_nearest_neighbors.KNearestNeighbors",
    "safeds.ml.classical.classification._logistic_regression.LogisticRegression",
    "safeds.ml.classical.classification._random_forest.RandomForest",
    "safeds.ml.classical.classification._support_vector_machine.SupportVectorMachine",
    "safeds.ml.classical.regression._ada_boost.AdaBoost",
    "safeds.ml.classical.regression._decision_tree.DecisionTree",
    "safeds.ml.classical.regression._elastic_net_regression.ElasticNetRegression",
    "safeds.ml.classical.regression._gradient_boosting.GradientBoosting",
    "safeds.ml.classical.regression._k_nearest_neighbors.KNearestNeighbors",
    "safeds.ml.classical.regression._lasso_regression.LassoRegression",
    "safeds.ml.classical.regression._linear_regression.LinearRegression",
    "safeds.ml.classical.regression._random_forest.RandomForest",
    "safeds.ml.classical.regression._regressor.Regressor",
    "safeds.ml.classical.regression._ridge_regression.RidgeRegression",
    "safeds.ml.classical.regression._support_vector_machine.SupportVectorMachine",
])


@dataclass(frozen=True)
class ExplicitIdentityWrapper:
    """
    Wrapper containing a value that lives in a shared memory location, and does not support a deterministic hash.

    This wrapper makes IPC actions more efficient, by only sending the shared memory location.
    The contained object is always unpickled at the receiving side.
    """
    value: Any
    memory: SharedMemory

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
        return _get_size_of_value(self.value)

    def __getstate__(self) -> object:
        return self.memory

    def __setstate__(self, state: object) -> None:
        import pickle
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
        import pickle
        bytes_dump = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        bytes_len = len(bytes_dump)
        shared_memory = SharedMemory(create=True, size=bytes_len)
        shared_memory.buf[:bytes_len] = bytes_dump
        _set_new_explicit_memory(value, shared_memory)
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
            import pickle
            object.__setattr__(self, 'value', pickle.loads(self.memory.buf))
            _set_new_explicit_memory(self.value, self.memory)

    def __sizeof__(self) -> int:
        return self.memory.size

    def __getstate__(self) -> object:
        return self.memory, self.id, self.hash

    def __setstate__(self, state: object) -> None:
        memory_value, id_value, hash_value = state
        object.__setattr__(self, 'value', None)
        object.__setattr__(self, 'memory', memory_value)
        object.__setattr__(self, 'id', id_value)
        object.__setattr__(self, 'hash', hash_value)


def _is_explicit_identity_class(value: Any) -> bool:
    """
    Check, whether the provided value is whitelisted, by comparing the module name and qualified classname to assign an explicit identity.

    Parameters
    ----------
    value
        Object to check, if allowed to receive an explicit identity.

    Returns
    -------
    result
        True, if the object can be assigned an explicit identity, otherwise false.
    """
    return hasattr(value, "__class__") and (value.__class__.__module__ + "." + value.__class__.__qualname__) in explicit_identity_classes


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


def _set_new_explicit_memory(value: Any, memory: SharedMemory) -> None:
    """
    Assign a shared memory location to the provided object.

    Parameters
    ----------
    value
        Object to assign a shared memory location to
    """
    value.__ex_id_mem__ = memory


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
    if _is_explicit_identity_class(value) and _has_explicit_identity_memory(value):
        return ExplicitIdentityWrapperLazy.existing(value)
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


def _convert_value_to_memoizable_format(
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
    The value in a memoizable format.
    """
    if isinstance(result, tuple):
        results = []
        for entry in result:
            if _is_explicit_identity_class(entry):
                _set_new_explicit_identity_deterministic_hash(entry)
                results.append(ExplicitIdentityWrapperLazy.shared(entry))
        return tuple(results)
    elif _is_explicit_identity_class(result):
        _set_new_explicit_identity_deterministic_hash(result)
        return ExplicitIdentityWrapperLazy.shared(result)
    return result
