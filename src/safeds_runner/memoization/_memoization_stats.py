"""Module that contains the memoization stats."""

import dataclasses
from dataclasses import dataclass


@dataclass(frozen=True)
class MemoizationStats:
    """
    Statistics calculated for every memoization call.

    Parameters
    ----------
    access_timestamps:
        Absolute timestamp since the unix epoch of the last access to the memoized value in nanoseconds
    lookup_times:
        Duration the lookup of the value took in nanoseconds (key comparison + IPC)
    computation_times:
        Duration the computation of the value took in nanoseconds
    memory_sizes:
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
        access_timestamp:
            Timestamp when this value was last accessed
        lookup_time:
            Duration the comparison took in nanoseconds
        """
        self.access_timestamps.append(access_timestamp)
        self.lookup_times.append(lookup_time)

    def update_on_miss(
        self,
        access_timestamp: int,
        lookup_time: int,
        computation_time: int,
        memory_size: int,
    ) -> None:
        """
        Update the memoization stats on a cache miss.

        Parameters
        ----------
        access_timestamp:
            Timestamp when this value was last accessed
        lookup_time:
            Duration the comparison took in nanoseconds
        computation_time:
            Duration the computation of the new value took in nanoseconds
        memory_size:
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
        string_representation:
            Summary of stats
        """
        return (  # pragma: no cover
            f"Last access: {self.access_timestamps}, computation time: {self.computation_times}, lookup time:"
            f" {self.lookup_times}, memory size: {self.memory_sizes}"
        )
