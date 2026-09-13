# v0.0.1 acceptance record

Status: In progress
Target: v0.0.1 — Trustworthy Personal Notebook
Branch: `stage-7-v0.0.1-acceptance`

This document is the release evidence record for [Milestone v0.0.1](MILESTONE_0_0_1.md). A required scenario is not considered complete until it has recorded evidence. Automated evidence is tied to named tests or CI jobs; hardware/manual evidence is recorded with environment, commit and result.

## Result vocabulary

- **PASS — automated**: exercised by committed automated tests in CI.
- **PASS — manual**: manually exercised and recorded on the intended environment.
- **PARTIAL**: meaningful evidence exists, but the full scenario is not yet demonstrated.
- **GAP**: required behavior is missing or known to be incorrect.
- **PENDING — manual**: implementation exists but requires real-device/operator verification.
- **DEFERRED**: explicitly outside v0.0.1.

## Core acceptance scenarios

| ID | Scenario | Current status | Existing / planned evidence |
| --- | --- | --- | --- |
| AC-01 | Clean setup and owner bootstrap | PARTIAL | Foundation CI proves empty-volume migration/startup; final fresh-main setup and real Pi bootstrap remain manual. |
| AC-02 | Authorization protects notes, search, history and exports | PASS — automated | Authentication/service/web/export tests. Recheck through browser smoke suite. |
| AC-03 | Save creates stable identity and exact normalized content | PASS — automated | Service/web tests. |
| AC-04 | Unchanged save creates no revision/version/time change | PASS — automated | Service tests. |
| AC-05 | Concurrent edit conflict preserves unsaved draft | PASS — automated | Service/web conflict tests; browser smoke will exercise UI behavior. |
| AC-06 | Idempotent retry and key/payload conflict | PASS — automated | Service tests. |
| AC-07 | History lists saved revisions; restore creates new revision with lineage; historical content can be viewed | GAP | Revision listing/restore are implemented and tested. Historical read capability exists in `Notebook.get_revision`, but Stage 6 UI/HTTP does not expose historical title/body. Stage 7 must close this gap. |
| AC-08 | Trash hides from normal lists/search; restore returns it; trashed note cannot edit | PASS — automated | Service/search/web tests. |
| AC-09 | Search uses current active content; rebuild equivalent | PASS — automated | Stage 4 search tests and Stage 6 recovery rebuild test. |
| AC-10 | Export filenames/path safety and YAML round trip | PASS — automated | `tests/test_exports.py`. |
| AC-11 | Workspace export is one consistent snapshot | PASS — automated | Stage 5 detached snapshot/mutation tests. |
| AC-12 | Container restart preserves notes/history/project membership | PENDING — manual | CI proves container start/migration; real persistence across restart/reboot must be recorded on Pi/OMV. |
| AC-13 | Consistent backup restores into separate instance; history/ownership/search recover | PASS — automated | `tests/test_backup.py`; real Pi recovery rehearsal remains required for release confidence. |
| AC-14 | Simulated write/storage failure is atomic and UI keeps draft/reports failure | PARTIAL | Transaction rollback/failure paths are covered in service/search tests; Stage 7 audit/browser tests must verify user-visible failure behavior. |
| AC-15 | Markdown/script safety and CSRF protections | PASS — automated | Web sanitization, same-origin/CSRF and preview tests. |
| AC-16 | Primary workflows work with keyboard, phone and desktop; focus/save state understandable | PENDING — manual | Stage 7 will add browser/a11y smoke checks; real keyboard and phone/desktop acceptance remains manual. |
| AC-17 | Core notebook works with all AI services/GPU machine off | PASS — automated | No AI runtime dependency exists in v0.0.1. Final Pi validation will record this explicitly. |

## Project acceptance scenarios

| ID | Scenario | Current status | Existing / planned evidence |
| --- | --- | --- | --- |
| PA-01 | Exactly one stable Inbox; default capture still targets it after rename | PASS — automated | Foundation/service/recovery tests. |
| PA-02 | Create/list/rename projects and move active notes without content revision changes | PASS — automated | Service tests. |
| PA-03 | Stale move/save conflicts; moving trashed note rejected | PASS — automated | Service tests. |
| PA-04 | Selected-project list/search omits other projects; all-project access explicit | PASS — automated | Service/search/web tests. |
| PA-05 | Cross-owner project/note IDs cannot authorize reads/writes | PASS — automated | Service authorization tests. |
| PA-06 | Exports preserve project identity/membership, empty projects and duplicate titles; scoped export excludes unrelated data | PASS — automated | Export tests. |
| PA-07 | Historical restore leaves current project membership unchanged | PASS — automated | Service tests. |
| PA-08 | Nested folders, project deletion and AI behavior remain absent | PASS — inspection | Explicitly deferred by milestone/roadmap; no such capability is exposed. |

## Stage 7 automated release-hardening work

Before manual hardware acceptance, Stage 7 will:

1. close AC-07 by exposing authorized read-only historical revision viewing;
2. add browser-level smoke tests for primary UI workflows and relevant viewport behavior;
3. add automated accessibility checks for principal pages and fix high-confidence violations;
4. strengthen dependency reproducibility for the deployment image;
5. add dependency/security scanning suitable for CI or release review;
6. rerun the complete Stage 1–7 test/build/migration/startup suite;
7. update this record with exact test names and CI evidence.

## Manual acceptance still required

The following evidence must be supplied from the intended deployment before v0.0.1 can be marked complete:

- Raspberry Pi 5 / ARM64 image build and application startup;
- OMV bind-mount ownership, SQLite locking and persistence across container restart and Pi reboot;
- real desktop keyboard workflow;
- real phone workflow at a small viewport and with the software keyboard;
- Tailscale HTTPS/Serve login, CSRF writes, session persistence/logout, exports and password-reset session revocation;
- verification that application port 8000 is not directly exposed publicly;
- real backup/verify/restore/search-rebuild rehearsal using synthetic data;
- final fresh-checkout installation following documentation literally.

These results will be recorded here with date, tested commit, environment and notes. No unperformed manual item should be marked PASS by inference.

## Release gate

v0.0.1 is a **GO** only when every required milestone scenario is PASS, CI is green on the release candidate, the manual evidence above is recorded, no unresolved release-blocking security/dependency issue remains, and README/milestone/changelog claims match the implementation.
