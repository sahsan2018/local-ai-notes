# Contributing

Thank you for helping shape Local AI Notes. The project is currently documentation-first, so design feedback is as useful as code.

## Before contributing

- Search existing issues and discussions.
- For a substantial feature or architectural change, open a proposal before implementation.
- Keep personal paths, hostnames, Tailnet details, note content, and credentials out of examples and tests.
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Development workflow

See [development setup](docs/DEVELOPMENT.md) for Python, migrations, tests and Docker commands. Run `pytest -q` before submitting foundation changes. Documentation pull requests should use clear Markdown and relative links where practical; documentation CI remains required.

## Architecture decisions

Changes to canonical storage, trust boundaries, identity, revision semantics, public APIs, deployment topology, or major dependencies should include an ADR in `docs/adr/` based on the template.

## Pull requests

- Keep changes focused.
- Explain user impact and tradeoffs.
- Add or update tests and documentation when applicable.
- Identify migrations, security implications, and compatibility effects.
- Do not commit generated data, model files, personal notes, databases, attachments, or secrets.
