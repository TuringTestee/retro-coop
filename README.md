# Retro Coop

A new project. Product scope and technology choices are pending.

## Start working

Open this repository in your agent and ask:

> Use `project-planner` to help me define Retro Coop and its first iteration.

For an existing issue, ask for `issue-resolver` with its URL. Vaseline’s planner turns CEO direction into architecture decisions and a prioritized dependency plan in the epic. After approval and planning merge, its orchestrator organizes linked issues and coordinates agents, using GitHub Projects when accessible or issue-only tracking otherwise. There is no separate breakdown stage. Implementation PRs include local review and test evidence. A bot or person reviews; a separate bot or human merges.

## Shared skills

Vaseline is pinned as a submodule at `tooling/vaseline`. Relative links expose its skills without copying their text. After cloning or creating a worktree, run:

```sh
git submodule update --init --recursive
```

You need read access to the private Vaseline repository and an authenticated SSH connection to GitHub. Refresh your agent's skill discovery after initialization. If needed, ask it to read `.agents/skills/project-planner/SKILL.md` directly.

To update deliberately, fetch Vaseline, check out a reviewed commit inside `tooling/vaseline`, and submit the changed submodule pointer in a PR. Reconcile skill links if the bundled names changed. Project instructions stay in `AGENTS.md`.

## Verification

Run from the repository root on a system with Git, a POSIX shell, and `timeout`:

```sh
timeout 60s sh scripts/preflight.sh
```

This initial pre-flight checks whitespace and shell syntax only; there is no application or product test suite yet. CI also checks submitted whitespace against the base revision. Add focused tests and useful fast checks as features arrive. Pre-flight must finish in under one minute; presubmit CI has a 30-minute hard limit. Separate post-submit tests may run for hours.

CI currently needs no submodule checkout. Future jobs that use shared skills must authenticate with read access to Vaseline and initialize the submodule; the default repository token does not grant cross-repository access.
