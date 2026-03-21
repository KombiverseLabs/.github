

## Task Management (MANDATORY)

This repo uses **Beads** for persistent issue tracking. ALL AI agents MUST use Beads when working in this repo.

### Rules
- **Before starting work**: Run `bd list` to check existing issues
- **When finding a bug/task**: Run `bd create "description"` to track it
- **When starting work on an issue**: Run `bd update <id> --status in_progress`
- **When completing work**: Run `bd update <id> --status done`
- **Before committing**: Run `bd sync` to ensure issues are persisted
- **NEVER leave tasks untracked** - if you identify work to be done, create a Beads issue

### Integration with GitHub Issues
- Beads issues are the **local source of truth** for repo-level tasks
- Cross-repo or milestone-level tasks belong in GitHub Issues + KombiverseLabs Roadmap Project
- When a Beads issue becomes cross-repo, promote it to a GitHub Issue