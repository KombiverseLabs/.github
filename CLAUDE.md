# CLAUDE.md - KombiverseLabs/.github

## Shared Workflows

This repo holds reusable GitHub Actions workflows for all KombiverseLabs repos.

| Workflow | Purpose |
|----------|---------|
| `pick-runner.yml` | Runtime runner selection — defaults to `oci-build-labs` and stays on explicitly chosen VM runner capacity |
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
| **srv1161760** | `srv1161760` | separate IP | **Overflow CI host** — secondary VM runner capacity for core/tools spillover |

## CI Runner Topology

All workflows use `pick-runner.yml` to select the preferred runner label at runtime.
The runner labels are intentionally shared across the OCI primary host and the
`srv1161760-labs` overflow host so existing jobs can spill over without YAML changes.

Current self-hosted labels:

- `oci-build-labs`: shared VM runner label spanning OCI primary + `srv1161760-labs` overflow
- `oci-build-core`: SaaS core repos and deployment work
- `oci-build-tools`: Stack/Sim/tooling repos
- `srv1161760-labs`: explicit overflow capacity label

Policy:

- prefer `oci-build-labs` unless a repo clearly belongs to the `core` or `tools` split
- keep `oci-build-core` / `oci-build-tools` as the canonical repo defaults
- maintain `srv1161760-labs` as warm overflow capacity under the same shared labels
- Blacksmith and `ubuntu-latest` consume GitHub Actions minutes; use only by explicit override
- **Never use kombify-ionos as a CI runner** — it is the production host

Operational baseline:

- OCI build host runs three systemd-managed runners: `oci-build-core-1`, `oci-build-core-2`, `oci-build-tools-1`
- OCI build host runs `kombify-runner-health.timer` every 5 minutes to verify Docker and runner services and self-heal failures

## Deploy Target for kombify.io Services

`kombify-ionos` and `srv1161760` are managed as Coolify remote servers.
GitHub Actions should trigger Coolify deployments instead of logging into those hosts directly.

The OCI build host is now the preferred CI runner target.
The `kombify-ionos` host remains a runtime target, but through Coolify orchestration rather than ad hoc SSH deploy steps.
