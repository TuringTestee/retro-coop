# Project guidance

Build what the user asks for. Review, test, and merge that work. Ask for approval only before adding a new player-facing design the user did not request or reasonably imply.

- Use the Vaseline skills in `.agents/skills/`.
- Put journeys and behavior in `docs/design/`, technical plans in `docs/implementation/`, and delivery work in the epic and its issues. Start human-facing documents with a short plain-English summary.
- Describe each journey through success and recovery. Keep only useful UI, and verify affected journeys in the integrated product.
- Review and merge governing plans before implementation. A faithful plan needs no second approval.
- Use `project-orchestrator` for dependencies, then `pr-testing` and `pr-draft-review`. Substantive PRs need independent review in a separate detached worktree. Follow the [handoff contract](tooling/vaseline/docs/agent/review-handoff.md).
- Agent merging is authorized for this repo after independent review and passing checks. Follow the ignored `.agents/preferences.local.json`, branch protections, and integration checks. Without scoped merge authorization, use an external merge owner.
- Start the reviewer with `sh scripts/review-bot.sh`. Run the README pre-flight command and follow the [verification strategy](docs/implementation/browser-nes-platform.md#verification-strategy).
