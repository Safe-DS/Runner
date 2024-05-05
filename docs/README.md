# Safe-DS Runner

[![PyPI](https://img.shields.io/pypi/v/safe-ds-runner)](https://pypi.org/project/safe-ds-runner)
[![Main](https://github.com/Safe-DS/Runner/actions/workflows/main.yml/badge.svg)](https://github.com/Safe-DS/Runner/actions/workflows/main.yml)
[![codecov](https://codecov.io/gh/Safe-DS/Runner/branch/main/graph/badge.svg?token=ma0ytglhO1)](https://codecov.io/gh/Safe-DS/Runner)
[![Documentation Status](https://readthedocs.org/projects/safe-ds-runner/badge/?version=stable)](https://runner.safeds.com)

Execute Safe-DS programs that were compiled to Python.

## Installation

Get the latest version from [PyPI](https://pypi.org/project/safe-ds-runner):

```shell
pip install safe-ds-runner
```

On a Windows PC with an NVIDIA graphics card, you may also want to install the CUDA versions of `torch` and
`torchvision`:

```shell
pip install --upgrade torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

## Usage

Start the runner server:

```shell
safe-ds-runner start
```

## Documentation

You can find the full documentation [here](https://runner.safeds.com).

## Contributing

We welcome contributions from everyone. As a starting point, check the following resources:

* [Setting up a development environment](https://runner.safeds.com/en/latest/development/environment/)
* [Project guidelines](https://runner.safeds.com/en/latest/development/project_guidelines/)
* [Contributing page](https://github.com/Safe-DS/Runner/contribute)

If you need further help, please [use our discussion forum][forum].

[forum]: https://github.com/orgs/Safe-DS/discussions
