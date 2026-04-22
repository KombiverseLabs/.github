# CLAUDE.md - KombiverseLabs/.github

## Task Management
**Tools:** Doppler (Secrets), Beads (`bd list/create/update/sync`) für Issue-Tracking.

## Docs Impact + Beads

Shared workflow changes are docs-impact relevant by default because they affect CI/CD, deployment, runtime configuration, or validation behavior.

- Follow `../kombify Core/standards/DOCS_STANDARDS.md` Section 8 for every workflow, action, script, or deployment-rule change.
- Update the owning Tier 2 docs/standards in the same change when workflow behavior changes.
- Use `docs-impact: none` only when the change is purely mechanical and has no operator/developer-facing behavior.
- If docs must be deferred, create or update a Beads issue in the owning repo and mention it in the handoff.
- AI/Workers AI may draft workflow documentation or classify impact, but reviewed git changes remain the source of truth.

## Shared Workflows

| Workflow | Purpose |
|----------|---------|
| `pick-runner-v2.yml` | Runtime runner selection -- defaults to `blacksmith-4vcpu-ubuntu-2204` (Blacksmith cloud runners), fallback `kombi` |
| `build-and-push.yml` | Build Docker image, push to GHCR (Blacksmith runners, GHA cache) |
| `deploy-render.yml` | Render deploy: resolve service IDs from Doppler `prd_render`, sync service runtime env from service-specific Doppler configs, update image tag via Render API, health check |
| `deploy-render-staged.yml` | Staged deploy: staging/production variant with the same Doppler-first Render runtime sync |
| `deploy-vps-ssh.yml` | SSH-basiertes VPS Deploy (Docker Compose auf Coolify/Remote Servern), materialisiert service-spezifische Runtime-Variablen aus Doppler und merged nur noch transitorische Remote-Reste |
| `aspire-integration-gate.yml` | Multi-Service Health Checks via Aspire AppHost |

### Production-Only Archived Workflows (not used for production deploys, kept for reference)

| Workflow | Purpose |
|----------|---------|
| `pick-runner.yml` | Legacy runner selection (self-hosted `kombi` default) |
| `deploy-coolify-v2.yml` | Coolify deploy (no longer used for production -- production moved to Render) |
| `deploy-dual.yml` | Legacy Space→IO canary deploy (replaced by deploy-render-staged.yml) |

## Infrastructure Overview

**Canonical rule:** customer-facing `*.kombify.io` services default to Render, with explicit documented exceptions.

| Platform | Role |
|----------|------|
| **Render** | **Production default** -- customer-facing SaaS services, managed PostgreSQL 17 (pgvector), managed Valkey 8 |
| **kombify-ionos** (217.154.174.107) | **Production exception, Coolify Remote Server** -- kombify-Sim (Docker socket + privileged), Company Tools (Paperless, FreeScout, Ollama, etc.) via Docker Compose auf Coolify |
| **Dev IONOS** (82.165.251.178) | **Dev environment, Coolify Remote Server** -- dev versions of services (`*.kombify.dev`), 4 self-hosted runners, Appwrite, Ollama, ToolHive (MCP Gateway), SpeechKit AI models. Doppler: `kombify-ionos-dev/dev` |
| **Hostinger VPS** | **Daily tools** -- kombify.space (Excalidraw, Docs-Tools), Coolify Cloud managed |
| **Marcel's PC** | **Local development** -- 2x kombi runners (fallback) |

Render Projects: kombify-websites, kombify-ai, kombify-tools, kombify-infra. Details in [Infrastructure Overview](../kombify%20Core/internal-docs/docs/infrastructure/infrastructure-overview.md).

## CI Runner Topology

All workflows use `pick-runner-v2.yml` to select the preferred runner label at runtime.

Runner labels:

- `blacksmith-4vcpu-ubuntu-2204`: Blacksmith cloud runners (primary, ephemeral, Build-Jobs)
- `blacksmith-2vcpu-ubuntu-2204`: Blacksmith cloud runners (lightweight CI-Jobs)
- `kombi`: Self-hosted runners (fallback -- Marcel's PC, kombi-server)

Policy:

- Default Build: `blacksmith-4vcpu-ubuntu-2204` (Blacksmith cloud runners)
- Default CI: `blacksmith-4vcpu-ubuntu-2204` oder `blacksmith-2vcpu-ubuntu-2204`
- Fallback: `kombi` (self-hosted runners)
- `ubuntu-latest` consumes GitHub Actions minutes; avoid
- **Never use kombify-ionos (production) as a CI runner** -- it runs active company tool deployments alongside kombify-Sim

## Deploy Targets

### Production (Render)

Render manages the default production path via API-driven deployments.
GitHub Actions trigger Render deployments via `deploy-render.yml`.
Render Preview Environments provide automatic PR-based staging.
Doppler `prd_render` config stores Render API key and service IDs.
Service runtime configuration should come from service-specific Doppler configs (for example `prd_cloud`, `prd_admin`, `prd_ai`) and is synced onto the Render service before deploy.

Exception:

- `kombify-Sim` deploys to the IONOS VPS via `deploy-vps-ssh.yml` because it requires Docker socket access and privileged runtime behavior.
- Render secret files and linked Render env groups remain explicit exceptions until migrated; they must not become the default place for normal app configuration.

### Dev Environment (kombify.dev on IONOS Dev VPS)

Dev versions of all services run on the IONOS Dev VPS via Docker Compose.
Deploy via `deploy-vps-ssh.yml` with:

- `doppler-project` / `doppler-config` for SSH credentials
- `runtime-env-project` / `runtime-env-config` for the service runtime environment

IONOS SSH credentials stay in Doppler `kombify-ionos-dev/dev`.
Service runtime values must come from service-specific Doppler configs and are materialized into the remote `.env` at deploy time.
Coolify/Compose directories are not the source of truth for application secrets anymore; remaining remote-only keys are temporary migration exceptions that should be moved into Doppler.
Also hosts: 4x self-hosted runners, Appwrite, Ollama, ToolHive (MCP Gateway).

### Company Tools (IONOS Production VPS)

Company tools (Paperless, FreeScout, N8N, etc.) run on the IONOS production VPS via Docker Compose.
IONOS SSH credentials stored in Doppler `kombify-io/prd_infra` (`IONOS_VPS_HOST`, `IONOS_VPS_USER`, `IONOS_SSH_PRIVATE_KEY`).
Where feasible, production Compose services follow the same rule as dev: runtime env is materialized from Doppler during deploy and not maintained manually in Coolify/remote `.env` files.

### Company-Authentifizierung (mkvl.de)

Zentrale Auth-Services auf kombify IONOS Prod schuetzen alle internen/Company Services:

- **TinyAuth** (`auth.mkvl.de`): Traefik/Coolify Forward-Auth Middleware
- **Pocket ID** (`id.mkvl.de`): Identity Provider (Google Login, OAuth)

Auf IONOS Prod nativ (gleicher Server). Auf allen anderen Servern (Dev IONOS, Hostinger, etc.) MUESSEN die externen URLs (`auth.mkvl.de`, `id.mkvl.de`) referenziert werden -- nie interne Container-Namen.
