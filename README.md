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

Stages 1-3 add the FastAPI/SQLite foundation, trusted note/project services and authenticated responsive Markdown notebook. Stage 4 adds scoped current-content FTS5 search and retained-history usage reporting. Stage 5 adds authenticated note Markdown export plus project/workspace ZIP snapshots with versioned manifests; see [stage 5 scope](docs/STAGE_5.md). The stacked draft PRs remain unmerged.

The complete v0.0.1 milestone is still unfinished: tested backup/restore, broader acceptance checks and Pi/ARM64 verification remain. No AI feature is implemented yet. See [development setup](docs/DEVELOPMENT.md).

See the [first milestone](docs/MILESTONE_0_0_1.md), [data model](docs/DATA_MODEL.md), and [capability contracts](docs/CAPABILITIES.md). These describe accepted behavior beyond what is currently implemented. Revision cleanup, nested folders and rich document/image editing follow later.

## Contributing

Ideas and design feedback are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md), [SUPPORT.md](SUPPORT.md), and the [Code of Conduct](CODE_OF_CONDUCT.md) before opening an issue.

## Security

Do not report vulnerabilities in public issues. Follow [SECURITY.md](SECURITY.md).

## License

Copyright (c) 2026 Shajib Ahsan. Licensed under the [MIT License](LICENSE).
