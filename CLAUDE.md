# CLAUDE.md - KombiverseLabs/.github

## Shared Workflows

This repo holds reusable GitHub Actions workflows for all KombiverseLabs repos.

| Workflow | Purpose |
|----------|---------|
| `pick-runner.yml` | Runtime runner selection — bootstraps on `srv1161760-labs`, falls back to Blacksmith then ubuntu-latest |
| `build-and-push.yml` | Build Docker image with Dagger, push to GHCR |
| `deploy-vps-ssh.yml` | SSH deploy to a VPS: pull new image, docker compose up, health check |
| `health-monitor.yml` | Periodic health check of deployed services |

## Infrastructure Overview

**All `*.kombify.io` services run on the kombify-ionos IONOS VPS** — there is no Azure Front Door.

| Server | Hostname | IP | Role |
|--------|----------|----|------|
| **kombify-ionos** | `kombify-ionos` | `217.154.174.107` | **Production host** — runs all live `*.kombify.io` and `*.mkvl.de` services |
| **srv1161760** | `srv1161760` | separate IP | **Build & CI fallback** — GitHub Actions runners for `kombify.space`; does NOT host kombify.io services |

## CI Runner Chain

All workflows use `pick-runner.yml` to select a runner at runtime:

```
srv1161760-labs  →  blacksmith-4vcpu-ubuntu-2204  →  ubuntu-latest
    (primary)           (fallback, cloud)             (last resort)
```

- `srv1161760-labs` is budget-free (self-hosted); prefer it always
- Blacksmith and ubuntu-latest consume GitHub Actions minutes — use only as fallback
- **Never use kombify-ionos as a CI runner** — it is the production host

## Deploy Target for kombify.io Services

When a workflow deploys to `*.kombify.io`, the `VPS_HOST` secret must be `217.154.174.107` (kombify-ionos).
The `srv1161760` server is NOT a deployment target for kombify.io — it is a build server for kombify.space.
