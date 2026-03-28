# CLAUDE.md - KombiverseLabs/.github

## Task Management
**Tools:** Doppler (Secrets), Beads (`bd list/create/update/sync`) für Issue-Tracking.

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
