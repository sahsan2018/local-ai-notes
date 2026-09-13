# Security Policy

## Supported versions

There are no production-ready releases yet. Security fixes will target the default branch until a versioned support policy is published.

## Reporting a vulnerability

Please do not disclose suspected vulnerabilities in public issues, discussions, or pull requests. Use GitHub's private vulnerability reporting feature when enabled. If it is unavailable, contact the maintainer privately through the contact method listed on their GitHub profile and include only enough detail to establish a safe reporting channel.

Include affected versions or commits, reproduction conditions, potential impact, and suggested mitigations when possible. Do not include real note content, credentials, tokens, or personal infrastructure details.

## Project security posture

The project is pre-release and should not be exposed directly to the public Internet. Planned controls include application authentication, authorization at the capability layer, CSRF protection, content sanitization, safe upload handling, secret isolation, audit records, and confirmation for destructive or bulk AI actions.

## Planned project scope enforcement

Future AI project scope is enforced server-side in retrieval, direct-ID access, attachments, caches, citations and writes. Prompts and project instructions cannot grant authority. Cross-project access requires explicit user scope selection; switching projects defaults to fresh conversation context. Scope does not erase pretrained knowledge or provide encryption isolation. Revalidate queued jobs when note membership changes. See [Architecture](docs/ARCHITECTURE.md).
