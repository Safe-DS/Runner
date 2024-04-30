from typing import Any

from safeds_runner.server._pipeline_manager import get_current_pipeline_process
from safeds_runner.server.messages._from_server import create_progress_message


def report_placeholder_computed(placeholder_name: str) -> None:
    """
    Report that a placeholder has been computed.

    Parameters
    ----------
    placeholder_name:
        Name of the placeholder.
    """
    current_pipeline = get_current_pipeline_process()
    if current_pipeline is None:
        return  # pragma: no cover

    current_pipeline.send_message(
        create_progress_message(
            run_id=current_pipeline._payload.run_id,
            placeholder_name=placeholder_name,
            percentage=100,
        ),
    )


def report_placeholder_value(placeholder_name: str, value: Any) -> None:
    """
    Report the value of a placeholder.

    Parameters
    ----------
    placeholder_name:
        Name of the placeholder.
    value:
        Value of the placeholder.
    """
    current_pipeline = get_current_pipeline_process()
    if current_pipeline is None:
        return  # pragma: no cover

    # # TODO
    # from safeds.data.image.containers import Image
    #
    # if isinstance(value, Image):
    #     import torch
    #
    #     value = Image(value._image_tensor, torch.device("cpu"))
    # placeholder_type = _get_placeholder_type(value)
    # if _is_deterministically_hashable(value) and _has_explicit_identity_memory(value):
    #     value = ExplicitIdentityWrapperLazy.existing(value)
    # elif (
    #     not _is_deterministically_hashable(value)
    #     and _is_not_primitive(value)
    #     and _has_explicit_identity_memory(value)
    # ):
    #     value = ExplicitIdentityWrapper.existing(value)
    # TODO
    # self._placeholder_map[placeholder_name] = value
    # self._send_message(
    #     message_type_placeholder_type,
    #     create_placeholder_description(placeholder_name, placeholder_type),
    # )


        # @sio.event
        # async def placeholder_query(_sid: str, payload: Any) -> None:
        #     try:
        #         placeholder_query_message = QueryMessage(**payload)
        #     except (TypeError, ValidationError):
        #         logging.exception("Invalid message data specified in: %s", payload)
        #         return
        #
        #     placeholder_type, placeholder_value = self._pipeline_manager.get_placeholder(
        #         placeholder_query_message.id,
        #         placeholder_query_message.data.name,
        #     )
        #
        #     if placeholder_type is None:
        #         # Send back empty type / value, to communicate that no placeholder exists (yet)
        #         # Use name from query to allow linking a response to a request on the peer
        #         data = json.dumps(create_placeholder_value(placeholder_query_message.data, "", ""))
        #         await sio.emit(message_type_placeholder_value, data, to=placeholder_query_message.id)
        #         return
        #
        #     try:
        #         data = json.dumps(
        #             create_placeholder_value(
        #                 placeholder_query_message.data,
        #                 placeholder_type,
        #                 placeholder_value,
        #             ),
        #             cls=SafeDsEncoder,
        #         )
        #     except TypeError:
        #         # if the value can't be encoded send back that the value exists but is not displayable
        #         data = json.dumps(
        #             create_placeholder_value(
        #                 placeholder_query_message.data,
        #                 placeholder_type,
        #                 "<Not displayable>",
        #             ),
        #         )
        #
        #     await sio.emit(message_type_placeholder_value, data, to=placeholder_query_message.id)



    # TODO: move into process that creates placeholder value messages
# def create_placeholder_value(placeholder_query: QueryMessageData, type_: str, value: Any) -> dict[str, Any]:
#     """
#     Create the message data of a placeholder value message containing name, type and the actual value.
#
#     If the query only requests a subset of the data and the placeholder type supports this,
#     the response will contain only a subset and the information about the subset.
#
#     Parameters
#     ----------
#     placeholder_query:
#         Query of the placeholder.
#     type_:
#         Type of the placeholder.
#     value:
#         Value of the placeholder.
#
#     Returns
#     -------
#     message_data:
#         Message data of "placeholder_value" messages.
#     """
#     import safeds.data.tabular.containers
#
#     message: dict[str, Any] = {"name": placeholder_query.name, "type": type_}
#     # Start Index >= 0
#     start_index = max(placeholder_query.window.begin if placeholder_query.window.begin is not None else 0, 0)
#     # End Index >= Start Index
#     end_index = (
#         (start_index + max(placeholder_query.window.size, 0)) if placeholder_query.window.size is not None else None
#     )
#     if isinstance(value, safeds.data.tabular.containers.Table) and (
#         placeholder_query.window.begin is not None or placeholder_query.window.size is not None
#     ):
#         max_index = value.number_of_rows
#         # End Index <= Number Of Rows
#         end_index = min(end_index, value.number_of_rows) if end_index is not None else None
#         value = value.slice_rows(start=start_index, end=end_index)
#         window_information: dict[str, int] = {"begin": start_index, "size": value.number_of_rows, "max": max_index}
#         message["window"] = window_information
#     message["value"] = value
#     return message
