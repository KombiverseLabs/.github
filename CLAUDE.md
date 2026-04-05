# CLAUDE.md - KombiverseLabs/.github

## Task Management
**Tools:** Doppler (Secrets), Beads (`bd list/create/update/sync`) für Issue-Tracking.

## Shared Workflows

| Workflow | Purpose |
|----------|---------|
| `pick-runner-v2.yml` | Runtime runner selection -- defaults to `blacksmith-2vcpu-ubuntu-2204` (Blacksmith cloud runners), fallback `kombi` |
| `build-and-push.yml` | Build Docker image, push to GHCR (Blacksmith runners, GHA cache) |
| `deploy-render.yml` | Render deploy: resolve service IDs from Doppler prd_render, update image tag via Render API, health check |
| `deploy-render-staged.yml` | Staged deploy: wraps deploy-render.yml for Staging → Production pattern |

### Archived Workflows (Coolify -- deactivated, not deleted)

| Workflow | Purpose |
|----------|---------|
| `pick-runner.yml` | Legacy runner selection (self-hosted `kombi` default) |
| `deploy-coolify-v2.yml` | Legacy Coolify deploy (replaced by deploy-render.yml) |
| `deploy-dual.yml` | Legacy Space→IO canary deploy (replaced by deploy-render-staged.yml) |

## Infrastructure Overview

**Canonical rule:** customer-facing `*.kombify.io` services default to Render, with explicit documented exceptions.

| Platform | Role |
|----------|------|
| **Render** | **Production default** -- customer-facing SaaS services, managed PostgreSQL 17 (pgvector), managed Redis |
| **kombify-ionos** (217.154.174.107) | **Production exception** -- kombify-Sim and company tools requiring VPS capabilities |
| **Hostinger VPS** | **Fallback** -- archived Coolify deployments |
| **Marcel's PC** | **Local development** -- 2x kombi runners (fallback) |

IaC Blueprint: `render.yaml` in workspace root defines all services and databases.

## CI Runner Topology

All workflows use `pick-runner-v2.yml` to select the preferred runner label at runtime.

Runner labels:

- `blacksmith-2vcpu-ubuntu-2204`: Blacksmith cloud runners (primary, ephemeral)
- `kombi`: Self-hosted runners (fallback -- Marcel's PC, kombi-server)

Policy:

- Default: `blacksmith-2vcpu-ubuntu-2204` (Blacksmith cloud runners)
- Fallback: `kombi` (self-hosted runners)
- `ubuntu-latest` consumes GitHub Actions minutes; avoid
- **Never use kombify-ionos as a CI runner** -- it hosts archived Coolify deployments

## Deploy Target

Render manages the default production path via API-driven deployments.
GitHub Actions trigger Render deployments via `deploy-render.yml`.
Render Preview Environments provide automatic PR-based staging.
Doppler `prd_render` config stores Render API key and service IDs.

Exception:

- `kombify-Sim` deploys to the IONOS VPS via `deploy-vps-ssh.yml` because it requires Docker socket access and privileged runtime behavior.
