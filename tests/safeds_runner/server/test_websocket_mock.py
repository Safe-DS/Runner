# @pytest.mark.parametrize(
#     argnames="initial_messages,initial_execution_message_wait,appended_messages,expected_responses",
#     argvalues=[
#         (
#             [
#                 json.dumps(
#                     {
#                         "type": "program",
#                         "id": "abcdefg",
#                         "data": {
#                             "code": {
#                                 "": {
#                                     "gen_test_a": (
#                                         "import safeds_runner\nimport base64\nfrom safeds.data.image.containers import Image\nfrom safeds.data.tabular.containers import Table\nimport safeds_runner\nfrom safeds_runner.server._json_encoder import SafeDsEncoder\n\ndef pipe():\n\tvalue1 ="
#                                         " 1\n\tsafeds_runner.save_placeholder('value1',"
#                                         " value1)\n\tsafeds_runner.save_placeholder('obj',"
#                                         " object())\n\tsafeds_runner.save_placeholder('image',"
#                                         " Image.from_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAD0lEQVQIW2NkQAOMpAsAAADuAAVDMQ2mAAAAAElFTkSuQmCC')))\n\t"
#                                         "table = safeds_runner.memoized_static_call(\"safeds.data.tabular.containers.Table.from_dict\", Table.from_dict, [{'a': [1, 2], 'b': [3, 4]}], {}, [])\n\t"
#                                         "safeds_runner.save_placeholder('table',table)\n\t"
#                                         'object_mem = safeds_runner.memoized_static_call("random.object.call", SafeDsEncoder, [], {}, [])\n\t'
#                                         "safeds_runner.save_placeholder('object_mem',object_mem)\n"
#                                     ),
#                                     "gen_test_a_pipe": (
#                                         "from gen_test_a import pipe\n\nif __name__ == '__main__':\n\tpipe()"
#                                     ),
#                                 },
#                             },
#                             "main": {"modulepath": "", "module": "test_a", "pipeline": "pipe"},
#                         },
#                     },
#                 ),
#             ],
#             6,
#             [
#                 # Query Placeholder
#                 json.dumps({"type": "placeholder_query", "id": "abcdefg", "data": {"name": "value1", "window": {}}}),
#                 # Query Placeholder (memoized type)
#                 json.dumps({"type": "placeholder_query", "id": "abcdefg", "data": {"name": "table", "window": {}}}),
#                 # Query not displayable Placeholder
#                 json.dumps({"type": "placeholder_query", "id": "abcdefg", "data": {"name": "obj", "window": {}}}),
#                 # Query invalid placeholder
#                 json.dumps({"type": "placeholder_query", "id": "abcdefg", "data": {"name": "value2", "window": {}}}),
#             ],
#             [
#                 # Validate Placeholder Information
#                 Message(message_type_placeholder_type, "abcdefg", create_placeholder_description("value1", "Int")),
#                 Message(message_type_placeholder_type, "abcdefg", create_placeholder_description("obj", "object")),
#                 Message(message_type_placeholder_type, "abcdefg", create_placeholder_description("image", "Image")),
#                 Message(message_type_placeholder_type, "abcdefg", create_placeholder_description("table", "Table")),
#                 Message(
#                     message_type_placeholder_type,
#                     "abcdefg",
#                     create_placeholder_description("object_mem", "SafeDsEncoder"),
#                 ),
#                 # Validate Progress Information
#                 Message(message_type_runtime_progress, "abcdefg", create_runtime_progress_done()),
#                 # Query Result Valid
#                 Message(
#                     message_type_placeholder_value,
#                     "abcdefg",
#                     create_placeholder_value(QueryMessageData(name="value1"), "Int", 1),
#                 ),
#                 # Query Result Valid (memoized)
#                 Message(
#                     message_type_placeholder_value,
#                     "abcdefg",
#                     create_placeholder_value(QueryMessageData(name="table"), "Table", {"a": [1, 2], "b": [3, 4]}),
#                 ),
#                 # Query Result not displayable
#                 Message(
#                     message_type_placeholder_value,
#                     "abcdefg",
#                     create_placeholder_value(QueryMessageData(name="obj"), "object", "<Not displayable>"),
#                 ),
#                 # Query Result Invalid
#                 Message(
#                     message_type_placeholder_value,
#                     "abcdefg",
#                     create_placeholder_value(QueryMessageData(name="value2"), "", ""),
#                 ),
#             ],
#         ),
#     ],
#     ids=["query_valid_query_invalid"],
# )
# @pytest.mark.asyncio()
# async def test_should_execute_pipeline_return_valid_placeholder(
#     initial_messages: list[str],
#     initial_execution_message_wait: int,
#     appended_messages: list[str],
#     expected_responses: list[Message],
# ) -> None:
#     # Initial execution
#     sds_server = SafeDsServer()
#     test_client = sds_server._app.test_client()
#     async with test_client.websocket("/WSMain") as test_websocket:
#         for message in initial_messages:
#             await test_websocket.send(message)
#         # Wait for at least enough messages to successfully execute pipeline
#         for _ in range(initial_execution_message_wait):
#             received_message = await test_websocket.receive()
#             next_message = Message.from_dict(json.loads(received_message))
#             assert next_message == expected_responses.pop(0)
#         # Now send queries
#         for message in appended_messages:
#             await test_websocket.send(message)
#         # And compare with expected responses
#         while len(expected_responses) > 0:
#             received_message = await test_websocket.receive()
#             next_message = Message.from_dict(json.loads(received_message))
#             assert next_message == expected_responses.pop(0)
#     await sds_server.shutdown()
#
# )
# @pytest.mark.asyncio()
# async def test_should_successfully_execute_simple_flow(messages: list[str], expected_response: Message) -> None:
#     sds_server = SafeDsServer()
#     test_client = sds_server._app.test_client()
#     async with test_client.websocket("/WSMain") as test_websocket:
#         for message in messages:
#             await test_websocket.send(message)
#         received_message = await test_websocket.receive()
#         query_result_invalid = Message.from_dict(json.loads(received_message))
#         assert query_result_invalid == expected_response
#     await sds_server.shutdown()
#
# @pytest.mark.parametrize(
#     argnames="query,type_,value,result",
#     argvalues=[
#         (
#             QueryMessageData(name="name"),
#             "Table",
#             Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
#             '{"name": "name", "type": "Table", "value": {"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}}',
#         ),
#         (
#             QueryMessageData(name="name", window=QueryMessageWindow(begin=0, size=1)),
#             "Table",
#             Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
#             (
#                 '{"name": "name", "type": "Table", "window": {"begin": 0, "size": 1, "max": 7}, "value": {"a": [1],'
#                 ' "b": [3]}}'
#             ),
#         ),
#         (
#             QueryMessageData(name="name", window=QueryMessageWindow(begin=4, size=3)),
#             "Table",
#             Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
#             (
#                 '{"name": "name", "type": "Table", "window": {"begin": 4, "size": 3, "max": 7}, "value": {"a": [3, 2,'
#                 ' 1], "b": [1, 2, 3]}}'
#             ),
#         ),
#         (
#             QueryMessageData(name="name", window=QueryMessageWindow(begin=0, size=0)),
#             "Table",
#             Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
#             (
#                 '{"name": "name", "type": "Table", "window": {"begin": 0, "size": 0, "max": 7}, "value": {"a": [], "b":'
#                 " []}}"
#             ),
#         ),
#         (
#             QueryMessageData(name="name", window=QueryMessageWindow(begin=4, size=30)),
#             "Table",
#             Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
#             (
#                 '{"name": "name", "type": "Table", "window": {"begin": 4, "size": 3, "max": 7}, "value": {"a": [3, 2,'
#                 ' 1], "b": [1, 2, 3]}}'
#             ),
#         ),
#         (
#             QueryMessageData(name="name", window=QueryMessageWindow(begin=4, size=None)),
#             "Table",
#             Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
#             (
#                 '{"name": "name", "type": "Table", "window": {"begin": 4, "size": 3, "max": 7}, "value": {"a": [3, 2,'
#                 ' 1], "b": [1, 2, 3]}}'
#             ),
#         ),
#         (
#             QueryMessageData(name="name", window=QueryMessageWindow(begin=0, size=-5)),
#             "Table",
#             Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
#             (
#                 '{"name": "name", "type": "Table", "window": {"begin": 0, "size": 0, "max": 7}, "value": {"a": [], "b":'
#                 " []}}"
#             ),
#         ),
#         (
#             QueryMessageData(name="name", window=QueryMessageWindow(begin=-5, size=None)),
#             "Table",
#             Table.from_dict({"a": [1, 2, 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}),
#             (
#                 '{"name": "name", "type": "Table", "window": {"begin": 0, "size": 7, "max": 7}, "value": {"a": [1, 2,'
#                 ' 1, 2, 3, 2, 1], "b": [3, 4, 6, 2, 1, 2, 3]}}'
#             ),
#         ),
#     ],
#     ids=[
#         "query_nowindow",
#         "query_windowed_0_1",
#         "query_windowed_4_3",
#         "query_windowed_empty",
#         "query_windowed_size_too_large",
#         "query_windowed_4_max",
#         "query_windowed_negative_size",
#         "query_windowed_negative_offset",
#     ],
# )
# def test_windowed_placeholder(query: QueryMessageData, type_: str, value: Any, result: str) -> None:
#     message = create_placeholder_value(query, type_, value)
#     assert json.dumps(message, cls=SafeDsEncoder) == result
#
