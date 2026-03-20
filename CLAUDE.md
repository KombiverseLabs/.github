# CLAUDE.md - KombiverseLabs/.github

## Shared Workflows

This repo holds reusable GitHub Actions workflows for all KombiverseLabs repos.

| Workflow | Purpose |
|----------|---------|
| `pick-runner.yml` | Runtime runner selection — defaults to `oci-build-labs` and stays on explicitly chosen self-hosted capacity |
| `build-and-push.yml` | Build Docker image with Dagger, push to GHCR |
| `deploy-coolify.yml` | Coolify deploy: sync Doppler env vars, update image tag, trigger redeploy, verify health |
| `deploy-vps-ssh.yml` | Legacy SSH deploy to a VPS; keep only for repos that have not yet moved to Coolify |
| `health-monitor.yml` | Periodic health check of deployed services |

## Infrastructure Overview

**All `*.kombify.io` services run on the kombify-ionos IONOS VPS** — there is no Azure Front Door.

| Server | Hostname | IP | Role |
|--------|----------|----|------|
| **kombify-ionos** | `kombify-ionos` | `217.154.174.107` | **Production host** — runs all live `*.kombify.io` and `*.mkvl.de` services |
| **oci-build** | `instance-20260317-2138` | `89.168.97.60` | **Primary build host** — OCI self-hosted GitHub Actions runners, Docker, Dagger |
| **srv1161760** | `srv1161760` | separate IP | **Legacy CI fallback** — existing self-hosted runners and non-canonical fallback capacity |

## CI Runner Topology

All workflows use `pick-runner.yml` to select the preferred runner label at runtime.
This workflow does not auto-fallback; it queues on the requested runner class.

Current self-hosted labels:

- `oci-build-labs`: shared label backed by the OCI runner pool
- `oci-build-core`: SaaS core repos and deployment work
- `oci-build-tools`: Stack/Sim/tooling repos
- `srv1161760-labs`: legacy fallback capacity

Policy:

- prefer `oci-build-labs` unless a repo clearly belongs to the `core` or `tools` split
- use `srv1161760-labs` only as fallback while OCI capacity is being adopted
- Blacksmith and `ubuntu-latest` consume GitHub Actions minutes; use only by explicit override
- **Never use kombify-ionos as a CI runner** — it is the production host

## Deploy Target for kombify.io Services

`kombify-ionos` and `srv1161760` are managed as Coolify remote servers.
GitHub Actions should trigger Coolify deployments instead of logging into those hosts directly.

The OCI build host is now the preferred CI runner target.
The `kombify-ionos` host remains a runtime target, but through Coolify orchestration rather than ad hoc SSH deploy steps.
