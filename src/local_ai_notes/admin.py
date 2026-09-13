"""Top-level administrative command dispatcher."""
import inspect
import sys

from . import cli as legacy_cli
from .recovery_cli import COMMANDS


def _run_registered(handler, args):
    signature = inspect.signature(handler)
    positional = []
    keywords = {}
    for value in args:
        if value.startswith("--"):
            name = value[2:].replace("-", "_")
            parameter = signature.parameters.get(name)
            if parameter is None or not isinstance(parameter.default, bool):
                raise ValueError(f"Unsupported option: {value}")
            keywords[name] = True
        else:
            positional.append(value)
    try:
        signature.bind(*positional, **keywords)
    except TypeError as error:
        raise ValueError(str(error)) from error
    return handler(*positional, **keywords)


def main():
    if len(sys.argv) > 1 and sys.argv[1] in COMMANDS:
        try:
            _run_registered(COMMANDS[sys.argv[1]], sys.argv[2:])
        except ValueError as error:
            raise SystemExit(str(error)) from error
        return
    legacy_cli.main()
