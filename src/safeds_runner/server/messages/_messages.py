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
