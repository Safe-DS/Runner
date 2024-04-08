"""Module that contains the memoization logic and stats."""
from __future__ import annotations

import dataclasses
import inspect
import functools
import operator
import logging
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from multiprocessing.shared_memory import SharedMemory
from typing import Any, TypeAlias

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


@dataclass(frozen=True)
class MemoizationStats:
    """
    Statistics calculated for every memoization call.

    Parameters
    ----------
    access_timestamps
        Absolute timestamp since the unix epoch of the last access to the memoized value in nanoseconds
    lookup_times
        Duration the lookup of the value took in nanoseconds (key comparison + IPC)
    computation_times
        Duration the computation of the value took in nanoseconds
    memory_sizes
        Amount of memory the memoized value takes up in bytes
    """

    access_timestamps: list[int] = dataclasses.field(default_factory=list)
    lookup_times: list[int] = dataclasses.field(default_factory=list)
    computation_times: list[int] = dataclasses.field(default_factory=list)
    memory_sizes: list[int] = dataclasses.field(default_factory=list)

    def update_on_hit(self, access_timestamp: int, lookup_time: int) -> None:
        """
        Update the memoization stats on a cache hit.

        Parameters
        ----------
        access_timestamp
            Timestamp when this value was last accessed
        lookup_time
            Duration the comparison took in nanoseconds
        """
        self.access_timestamps.append(access_timestamp)
        self.lookup_times.append(lookup_time)

    def update_on_miss(self, access_timestamp: int, lookup_time: int, computation_time: int, memory_size: int) -> None:
        """
        Update the memoization stats on a cache miss.

        Parameters
        ----------
        access_timestamp
            Timestamp when this value was last accessed
        lookup_time
            Duration the comparison took in nanoseconds
        computation_time
            Duration the computation of the new value took in nanoseconds
        memory_size
            Memory the newly computed value takes up in bytes
        """
        self.access_timestamps.append(access_timestamp)
        self.lookup_times.append(lookup_time)
        self.computation_times.append(computation_time)
        self.memory_sizes.append(memory_size)

    def __str__(self) -> str:
        """
        Summarizes stats contained in this object.

        Returns
        -------
        Summary of stats
        """
        return (  # pragma: no cover
            f"Last access: {self.access_timestamps}, computation time: {self.computation_times}, lookup time:"
            f" {self.lookup_times}, memory size: {self.memory_sizes}"
        )


# Lambda = Stat Key Extractor, Boolean = Reverse Order
StatOrderExtractor: TypeAlias = tuple[Callable[[tuple[str, MemoizationStats]], Any], bool]

# Sort functions by miss-rate in reverse (max. misses first)
STAT_ORDER_MISS_RATE: StatOrderExtractor = (lambda function_stats: len(function_stats[1].computation_times) / len(function_stats[1].lookup_times), True)

# Sort functions by LRU (last access timestamp, in ascending order, least recently used first)
STAT_ORDER_LRU: StatOrderExtractor = (lambda function_stats: max(function_stats[1].access_timestamps), False)

# Sort functions by time saved (difference average computation time and average lookup time, least time saved first)
STAT_ORDER_TIME_SAVED: StatOrderExtractor = (lambda function_stats: (sum(function_stats[1].computation_times) / len(function_stats[1].computation_times)) - (sum(function_stats[1].lookup_times) / len(function_stats[1].lookup_times)), False)

# Sort functions by priority (ratio average computation time to average size, lowest priority first)
STAT_ORDER_PRIORITY: StatOrderExtractor = (lambda function_stats: (sum(function_stats[1].computation_times) / len(function_stats[1].computation_times)) / (sum(function_stats[1].memory_sizes) / len(function_stats[1].memory_sizes)), False)

# Sort functions by inverse LRU (last access timestamp, in descending order, least recently used last)
STAT_ORDER_LRU_INVERSE: StatOrderExtractor = (lambda function_stats: -max(function_stats[1].access_timestamps), False)


class MemoizationMap:
    """
    The memoization map handles memoized function calls.

    This contains looking up stored values, computing new values if needed and calculating and updating statistics.
    """

    def __init__(
        self,
        map_values: dict[MemoizationKey, Any],
        map_stats: dict[str, MemoizationStats],
    ):
        """
        Create a new memoization map using a value store dictionary and a stats dictionary.

        Parameters
        ----------
        map_values
            Value store dictionary
        map_stats
            Stats dictionary
        """
        self._map_values: dict[MemoizationKey, Any] = map_values
        self._map_stats: dict[str, MemoizationStats] = map_stats
        self.max_size = None
        self.value_removal_strategy = STAT_ORDER_PRIORITY #

    def get_cache_size(self) -> int:
        """
        Calculate the current size of the memoization cache.

        Returns
        -------
        Amount of bytes, this cache occupies. This may be an estimate.
        """
        return functools.reduce(operator.add, [_get_size_of_value(value) for value in self._map_values.values()], 0)

    def ensure_capacity(self, needed_capacity: int) -> None:
        """
        Ensure that the requested capacity is at least available, by freeing values from the cache.
        If the needed capacity is larger than the max capacity, this function will not do anything to ensure further operation.

        Parameters
        ----------
        needed_capacity
            Amount of free storage space requested, in bytes
        """
        free_size = self.max_size - self.get_cache_size()
        while free_size < needed_capacity < self.max_size:
            self.remove_worst_element(needed_capacity - free_size)
            free_size = self.max_size - self.get_cache_size()

    def remove_worst_element(self, capacity_to_free: int) -> None:
        """
        Remove the worst elements (most useless) from the cache, to free at least the provided amount of bytes.

        Parameters
        ----------
        capacity_to_free
            Amount of bytes that should be additionally freed, after this function returns
        """
        copied_stats = [(function, stats) for function, stats in self._map_stats.copy().items()]
        # Sort functions to remove them from the cache in a specific order
        copied_stats.sort(key=self.value_removal_strategy[0], reverse=self.value_removal_strategy[1])
        # Calculate which functions should be removed from the cache
        bytes_freed = 0
        functions_to_free = []
        for (function, stats) in copied_stats:
            if bytes_freed >= capacity_to_free:
                break
            function_sum_bytes = functools.reduce(operator.add, stats.memory_sizes, 0)
            bytes_freed += function_sum_bytes
            functions_to_free.append(function)
        # Remove references to values, and let the gc handle the actual objects
        for key in self._map_values.keys():
            for function_to_free in functions_to_free:
                if key[0] == function_to_free:
                    del self._map_values[key]
        # Remove stats, as content is gone
        for function_to_free in functions_to_free:
            del self._map_stats[function_to_free]

    def memoized_function_call(
        self,
        function_name: str,
        function_callable: Callable,
        parameters: list[Any],
        hidden_parameters: list[Any],
    ) -> Any:
        """
        Handle a memoized function call.

        Looks up the stored value, determined by function name, parameters and hidden parameters and returns it if found.
        If no value is found, computes the value using the provided callable and stores it in the map.
        Every call to this function will update the memoization stats.

        Parameters
        ----------
        function_name
            Fully qualified function name
        function_callable
            Function that is called and memoized if the result was not found in the memoization map
        parameters
            List of parameters passed to the function
        hidden_parameters
            List of hidden parameters for the function. This is used for memoizing some impure functions.

        Returns
        -------
        The result of the specified function, if any exists
        """
        access_timestamp = time.time_ns()

        # Lookup memoized value
        lookup_time_start = time.perf_counter_ns()
        key = self._create_memoization_key(function_name, parameters, hidden_parameters)
        try:
            memoized_value = self._lookup_value(key)
        # Pickling may raise AttributeError, hashing may raise TypeError
        except (AttributeError, TypeError):
            return function_callable(*parameters)
        lookup_time = time.perf_counter_ns() - lookup_time_start

        # Hit
        if memoized_value is not None:
            self._update_stats_on_hit(function_name, access_timestamp, lookup_time)
            if isinstance(memoized_value, ExplicitIdentityWrapper):
                return memoized_value.value
            elif isinstance(memoized_value, ExplicitIdentityWrapperLazy):
                memoized_value._unpackvalue()
                return memoized_value.value
            else:
                return memoized_value

        # Miss
        computation_time_start = time.perf_counter_ns()
        computed_value = function_callable(*parameters)
        computation_time = time.perf_counter_ns() - computation_time_start
        memory_size = _get_size_of_value(computed_value)

        memoizable_value = self._convert_value_to_memoizable_format(computed_value)
        if self.max_size is not None:
            self.ensure_capacity(_get_size_of_value(memoized_value))
        self._map_values[key] = memoizable_value

        self._update_stats_on_miss(
            function_name,
            access_timestamp,
            lookup_time,
            computation_time,
            memory_size,
        )

        logging.info(
            "New memoization stats for %s: (access_timestamp=%s, lookup_time=%s, computation_time=%s, memory_size=%s)",
            key[0],
            access_timestamp,
            lookup_time,
            computation_time,
            memory_size,
        )

        if isinstance(computed_value, ExplicitIdentityWrapper):
            return computed_value.value
        else:
            return computed_value

    def _create_memoization_key(
        self,
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

    def _lookup_value(self, key: MemoizationKey) -> Any | None:
        """
        Lookup a potentially existing value from the memoization cache.

        Parameters
        ----------
        key
            Memoization Key

        Returns
        -------
        The value corresponding to the provided memoization key, if any exists.
        """
        looked_up_value = self._map_values.get(key)
        if isinstance(looked_up_value, tuple):
            results = []
            for entry in looked_up_value:
                if isinstance(entry, ExplicitIdentityWrapperLazy):
                    entry._unpackvalue()
                    results.append(entry.value)
            return tuple(results)
        if isinstance(looked_up_value, ExplicitIdentityWrapperLazy):
            looked_up_value._unpackvalue()
            return looked_up_value.value
        if isinstance(looked_up_value, ExplicitIdentityWrapper):
            return looked_up_value.value
        return looked_up_value

    def _convert_value_to_memoizable_format(
        self,
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

    def _update_stats_on_hit(self, function_name: str, access_timestamp: int, lookup_time: int) -> None:
        """
        Update the memoization stats on a cache hit.

        Parameters
        ----------
        function_name
            Fully qualified function name
        access_timestamp
            Timestamp when this value was last accessed
        lookup_time
            Duration the comparison took in nanoseconds
        """
        stats = self._map_stats[function_name]
        stats.update_on_hit(access_timestamp, lookup_time)

        # This assignment is required for multiprocessing, see
        # https://docs.python.org/3.11/library/multiprocessing.html#proxy-objects
        self._map_stats[function_name] = stats

    def _update_stats_on_miss(
        self,
        function_name: str,
        access_timestamp: int,
        lookup_time: int,
        computation_time: int,
        memory_size: int,
    ) -> None:
        """
        Update the memoization stats on a cache miss.

        Parameters
        ----------
        function_name
            Fully qualified function name
        access_timestamp
            Timestamp when this value was last accessed
        lookup_time
            Duration the comparison took in nanoseconds
        computation_time
            Duration the computation of the new value took in nanoseconds
        memory_size
            Memory the newly computed value takes up in bytes
        """
        stats = self._map_stats.get(function_name)
        if stats is None:
            stats = MemoizationStats()

        stats.update_on_miss(access_timestamp, lookup_time, computation_time, memory_size)
        self._map_stats[function_name] = stats


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
