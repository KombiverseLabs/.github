# CLAUDE.md - KombiverseLabs/.github

## Shared Workflows

This repo holds reusable GitHub Actions workflows for all KombiverseLabs repos.

| Workflow | Purpose |
|----------|---------|
| `pick-runner.yml` | Runtime runner selection — bootstraps on `srv1161760-labs`, falls back to Blacksmith then ubuntu-latest |
| `build-and-push.yml` | Build Docker image with Dagger, push to GHCR |
| `deploy-coolify.yml` | Coolify deploy: sync Doppler env vars, update image tag, trigger redeploy, verify health |
| `deploy-vps-ssh.yml` | Legacy SSH deploy to a VPS; keep only for repos that have not yet moved to Coolify |
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

`kombify-ionos` and `srv1161760` are managed as Coolify remote servers.
GitHub Actions should trigger Coolify deployments instead of logging into those hosts directly.

The `srv1161760` server remains the preferred CI runner.
The `kombify-ionos` host remains a runtime target, but through Coolify orchestration rather than ad hoc SSH deploy steps.
