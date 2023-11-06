from safeds_runner.server.main import execute_pipeline


def test_execute_pipeline() -> None:
    context_globals = {}
    context_locals = {}
    result = execute_pipeline({
        "": {
            "gen_b": "import safeds_runner.codegen\n\ndef c():\n\ta1 = 1\n\ta2 = safeds_runner.codegen.eager_or(True, False)\n\tprint('test')\n\tprint('dynamic pipeline output')\n\treturn a1 + a2\n",
            "gen_b_c": "from gen_b import c\n\nif __name__ == '__main__':\n\tc()"}
    }, "a.test", "b", "c", context_globals)

    context_globals = {}
    context_locals = {}

    result = execute_pipeline({
        "": {
            "gen_b": "import safeds_runner.codegen\nfrom a.stub import u\nfrom v.u.s.testing import add1\n\ndef c():\n\ta1 = 1\n\ta2 = safeds_runner.codegen.eager_or(True, False)\n\tprint('test2')\n\tprint('new dynamic output')\n\tprint(f'Add1: {add1(1, 2)}')\n\treturn a1 + a2\n",
            "gen_b_c": "from gen_b import c\n\nif __name__ == '__main__':\n\tc()"
        },
        "a": {
            "stub": "def u():\n\treturn 1"
        },
        "v.u.s": {
            "testing": "import a.stub;\n\ndef add1(v1, v2):\n\treturn v1 + v2 + a.stub.u()\n"
        }
    }, "a.test", "b", "c", context_globals)
    # // __name__ is not __main__; Therefore the main script is not executed; use pyrun to execute main script (loading main script just like any other script is acceptable)
    # exec("from a.b import c", context_globals, context_locals)
