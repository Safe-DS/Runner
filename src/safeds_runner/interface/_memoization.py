from __future__ import annotations

import typing
from typing import Any

from safeds_runner.server import _pipeline_manager


def memoized_static_call(
    fully_qualified_function_name: str,
    callable_: typing.Callable,
    positional_arguments: list[Any],
    keyword_arguments: dict[str, Any],
    hidden_arguments: list[Any],
) -> Any:
    """
    Call a function that can be memoized and save the result.

    If a function has been previously memoized, the previous result may be reused.

    Parameters
    ----------
    fully_qualified_function_name:
        Fully qualified function name.
    callable_:
        Function that is called and memoized if the result was not found in the memoization map.
    positional_arguments:
        List of positions arguments for the function.
    keyword_arguments:
        Dictionary of keyword arguments for the function.
    hidden_arguments:
        List of hidden arguments for the function. This is used for memoizing some impure functions.

    Returns
    -------
    result:
        The result of the specified function, if any exists.
    """
    if _pipeline_manager.current_pipeline is None:
        return None  # pragma: no cover

    memoization_map = _pipeline_manager.current_pipeline.get_memoization_map()
    return memoization_map.memoized_function_call(
        fully_qualified_function_name,
        callable_,
        positional_arguments,
        keyword_arguments,
        hidden_arguments,
    )


def memoized_dynamic_call(
    receiver: Any,
    function_name: str,
    positional_arguments: list[Any],
    keyword_arguments: dict[str, Any],
    hidden_arguments: list[Any],
) -> Any:
    """
    Dynamically call a function that can be memoized and save the result.

    If a function has been previously memoized, the previous result may be reused. Dynamic calling in this context
    means, the function name will be used to look up the function on the instance passed as receiver.

    Parameters
    ----------
    receiver : Any
        Instance the function should be called on.
    function_name:
        Simple function name.
    positional_arguments:
        List of positions arguments for the function.
    keyword_arguments:
        Dictionary of keyword arguments for the function.
    hidden_arguments:
        List of hidden parameters for the function. This is used for memoizing some impure functions.

    Returns
    -------
    result:
        The result of the specified function, if any exists.
    """
    if _pipeline_manager.current_pipeline is None:
        return None  # pragma: no cover

    fully_qualified_function_name = (
        receiver.__class__.__module__ + "." + receiver.__class__.__qualname__ + "." + function_name
    )

    member = getattr(receiver, function_name)
    callable_ = member.__func__

    memoization_map = _pipeline_manager.current_pipeline.get_memoization_map()
    return memoization_map.memoized_function_call(
        fully_qualified_function_name,
        callable_,
        [receiver, *positional_arguments],
        keyword_arguments,
        hidden_arguments,
    )
