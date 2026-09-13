# Stage 3: authenticated browser notebook

This draft builds on the unmerged stage-two services. It adds the first authenticated browser boundary and a responsive Markdown notebook interface. Search, exports, backup/restore tooling, attachments and AI remain later work.

## Implemented

- Local owner login/logout backed by opaque random session secrets; only token hashes are stored.
- Seven-day absolute sessions, revocation on logout, and local `notes reset-password` recovery that revokes all sessions.
- HttpOnly, SameSite=Strict session cookies. Secure cookies are the default; explicit local HTTP development must set `LOCAL_AI_NOTES_COOKIE_SECURE=false`.
- CSRF protection for browser mutations and same-origin checks. Client-supplied actor/provenance fields are rejected by allowlisted form parsing.
- Basic in-process login throttling with generic credential failures. This is a single-process defense, not a distributed rate-limit service.
- Authenticated project, note and revision collection endpoints with recent-update/revision ordering and opaque scope-bound cursors.
- Separate server-generated request IDs from mutation idempotency keys.
- Responsive project/list/editor/trash/history UI, explicit all-project mode, Markdown toolbar and sanitized preview.
- Explicit Save and Ctrl/Cmd+S. Save failures keep the open draft; conflicting saves show the latest saved content without automatically overwriting either version.
- Project moves, trash/restore and restore-as-new-revision through the existing application services.
- Security response headers and disabled raw HTML in Markdown preview; unsafe link schemes and remote images are not rendered.

## Security boundary

The browser never supplies an actor ID. A valid session is resolved to the owner server-side and only then is `Notebook(engine, actor_id)` constructed. Direct note selection in a project-scoped page must match the selected project and lifecycle view; explicit all-project browsing is separate.

Mutation forms carry independent UUID retry keys. AJAX note saves reuse a key only for an exact retry and generate a fresh key after success or an explicit conflict-resolution choice. Correlation/request IDs are generated independently for audit and revision provenance.

## Pagination contract

Projects and active/trash note collections sort by `updated_at DESC, id DESC`; revisions sort by `revision_number DESC`. Transport cursors are base64url-encoded implementation details carrying their collection kind, scope, lifecycle mode and position. A cursor from one project/lifecycle collection is rejected in another. Cursors are not authorization tokens; ownership and scope are checked separately.

## Verification and limitations

Run `pytest -q`. Stage-three tests cover login/session expiry/logout/recovery, CSRF, spoofed fields, conflicting browser saves, exact retry behavior, scope-bound cursors, direct-ID project isolation and unsafe Markdown rendering. Existing foundation/service tests remain required in CI.

This UI is intentionally small. It has not been verified on physical phones/tablets or on Raspberry Pi/ARM64 hardware. The in-process login limiter resets on process restart and is not shared across multiple workers. Search, history byte counts, exports, tested backup restoration and release dependency locking still block completion of v0.0.1.
