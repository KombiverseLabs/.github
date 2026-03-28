# CLAUDE.md - KombiverseLabs/.github

## Task Management
**Tools:** Doppler (Secrets), Beads (`bd list/create/update/sync`) für Issue-Tracking.

## Shared Workflows

| Workflow | Purpose |
|----------|---------|
| `pick-runner.yml` | Runtime runner selection -- defaults to `kombi` (all self-hosted runners) |
| `build-and-push.yml` | Build Docker image, push to GHCR |
| `deploy-coolify-v2.yml` | Coolify deploy: resolve UUIDs from Doppler prd_infra, update image tag, trigger redeploy, health check. No env sync. |
| `deploy-dual.yml` | Space-first canary deploy: wraps deploy-coolify-v2.yml for dual-server pattern (Space canary → IO production) |

## Infrastructure Overview

**All `*.kombify.io` services run on the kombify-ionos IONOS VPS.**

| Server | Role |
|--------|------|
| **kombify-ionos** (217.154.174.107) | **Production** -- all `*.kombify.io` services via Coolify |
| **Hostinger VPS** | **Test/Fallback** -- `*.kombify.space` services via Coolify |
| **Marcel's PC** | **Build** -- 2x kombi runners, local development |

OCI build server has been decommissioned (unreliable Docker connectivity during large image pushes).

## CI Runner Topology

All workflows use `pick-runner.yml` to select the preferred runner label at runtime.

Current self-hosted labels:

- `kombi`: All self-hosted runners (Marcel's PC, new server, Hostinger VPS)

Policy:

- Default: `kombi` (all self-hosted runners)
- `ubuntu-latest` consumes GitHub Actions minutes; avoid
- **Never use kombify-ionos as a CI runner** -- it is the production host

## Deploy Target

Coolify manages both IONOS (production) and Hostinger (test/fallback).
GitHub Actions trigger Coolify deployments, no direct SSH to production hosts.
