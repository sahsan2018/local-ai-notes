# Local AI Notes

> [!IMPORTANT]
> This project is in early development. It is not yet ready for production use.

A local-first, self-hosted note-taking platform designed to remain fully useful without AI while supporting optional local AI assistance, OCR, semantic retrieval, and controlled agent tools.

## Vision

- Durable, human-owned notes with SQLite as the system of record.
- Projects for organization and future server-enforced AI context scope.
- Responsive desktop and mobile web experience.
- Revisions, provenance, soft deletion, export, and recovery from the beginning.
- One capability layer shared by the UI, API, and future AI tools.
- Optional AI workers that can be replaced or turned off without disabling note-taking.
- Public, reproducible deployment without personal paths, credentials, or network assumptions.

## Planned topology

The initial target deployment is a Dockerized FastAPI application on a Raspberry Pi 5 with persistent storage, accessed over Tailscale. Optional AI workloads run on a separate GPU-equipped machine through an OpenAI-compatible provider boundary.

See [Architecture](docs/ARCHITECTURE.md), [Product specification](docs/PRODUCT_SPEC.md), and [Roadmap](ROADMAP.md).

## Status

Stage 1 adds a FastAPI health service, SQLite migration, local owner/Inbox setup, Docker configuration and foundation tests. Stage 2 adds internal project/note services, revisions, trash/restore, conflict checks and safe retries; see [stage 2 scope](docs/STAGE_2.md). See [development setup](docs/DEVELOPMENT.md) to run tests. Browser login, public note endpoints, search, exports and the editor are not implemented yet.

See the [first milestone](docs/MILESTONE_0_0_1.md), [data model](docs/DATA_MODEL.md), and [capability contracts](docs/CAPABILITIES.md). These describe planned behavior, not implemented features. Revision cleanup, nested folders and rich document/image editing follow later.

## Contributing

Ideas and design feedback are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md), [SUPPORT.md](SUPPORT.md), and the [Code of Conduct](CODE_OF_CONDUCT.md) before opening an issue.

## Security

Do not report vulnerabilities in public issues. Follow [SECURITY.md](SECURITY.md).

## License

Copyright (c) 2026 Shajib Ahsan. Licensed under the [MIT License](LICENSE).
