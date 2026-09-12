# Project guidance

Use Vaseline to agree on what to build, divide it into dependent issues, and deliver reviewed changes. Product scope and technology choices still need user alignment.

- Start every human-facing document with a concise summary a second-year CS student can understand. Put technical detail afterward.
- Skills are linked from `.agents/skills/` to the pinned `tooling/vaseline` submodule. Read the named skill's `SKILL.md` if discovery is unavailable. Keep project-specific guidance here.
- Use `project-planner` to align on behavior, write `docs/design/<project>.md` and `docs/implementation/<project>.md`, and create an epic indexing them. Strongly recommend careful user review of the planning PR.
- `project-breakdown` requires actual user approval of the reviewed version and merged planning documents. It creates child issues and a dependency map PR. Changes to agreed behavior or major constraints require renewed alignment.
- `project-orchestrator` dispatches `issue-resolver` only after required planning and breakdown PRs have merged and dependencies are satisfied. Verify live issue ownership and merge state before dispatching.
- Use `pr-testing` and `local-pr-review` before PR handoff. Substantive changes require a fresh reviewer with no inherited builder context, a separate detached worktree, and only the PR URL and review instructions as input. Publish evidence following [the handoff contract](tooling/vaseline/docs/review-handoff.md).
- A bot or person approves or gives feedback. A separate bot or human merges. Confirm integration before starting dependent work.
- Run the README's pre-flight command in under one minute. Keep presubmit CI under 30 minutes with a hard timeout. Separate post-submit E2E or soak tests may run for hours. Add suitable focused tests and evolve pre-flight when the project gains executable features; no language or framework has been chosen.
