import argparse
import logging
from importlib.metadata import version

from safeds_runner.server.main import start_server


class Commands:
    START = "start"


def cli() -> None:  # pragma: no cover
    """Run the application via the command line."""
    args = _get_args()

    # Set logging level
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Run command
    match args.command:
        case Commands.START:
            start_server(args.port)


def _get_args() -> argparse.Namespace:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Execute Safe-DS programs that were compiled to Python.")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {version('safe-ds-runner')}",
    )
    parser.add_argument("-v", "--verbose", help="increase logging verbosity", action="store_true")

    # Commands
    subparsers = parser.add_subparsers(dest="command")
    _add_start_subparser(subparsers)

    return parser.parse_args()


def _add_start_subparser(
    subparsers: argparse._SubParsersAction,
) -> None:  # pragma: no cover
    parser = subparsers.add_parser(Commands.START, help="start the Safe-DS Runner server")
    parser.add_argument("-p", "--port", type=int, default=5000, help="the port to use")
