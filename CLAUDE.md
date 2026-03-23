# CLAUDE.md - KombiverseLabs/.github

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

## Shared Workflows

| Workflow | Purpose |
|----------|---------|
| `pick-runner.yml` | Runtime runner selection -- defaults to `docker-desktop` (local runners) |
| `build-and-push.yml` | Build Docker image, push to GHCR |
| `deploy-coolify.yml` | Coolify deploy: sync Doppler env vars, update image tag, trigger redeploy, verify health |
| `deploy-vps-ssh.yml` | Legacy SSH deploy to a VPS; keep only for repos that have not yet moved to Coolify |
| `health-monitor.yml` | Periodic health check of deployed services |

## Infrastructure Overview

**All `*.kombify.io` services run on the kombify-ionos IONOS VPS.**

| Server | Role |
|--------|------|
| **kombify-ionos** (217.154.174.107) | **Production** -- all `*.kombify.io` services via Coolify |
| **Hostinger VPS** | **Test/Fallback** -- `*.kombify.space` services via Coolify + SSH |
| **Marcel's PC** | **Build** -- 2x docker-desktop runners, local development |

OCI build server has been decommissioned (unreliable Docker connectivity during large image pushes).

## CI Runner Topology

All workflows use `pick-runner.yml` to select the preferred runner label at runtime.

Current self-hosted labels:

- `docker-desktop`: Marcel's PC (2 runners) -- Go builds, Docker builds, heavy CI
- `hostinger-runner`: Hostinger VPS -- SvelteKit builds, lightweight CI

Policy:

- Default: `docker-desktop` (local runners, fastest)
- SvelteKit-only repos: `hostinger-runner` acceptable
- `ubuntu-latest` consumes GitHub Actions minutes; avoid
- **Never use kombify-ionos as a CI runner** -- it is the production host

## Deploy Target

Coolify manages both IONOS (production) and Hostinger (test/fallback).
GitHub Actions trigger Coolify deployments, no direct SSH to production hosts.
