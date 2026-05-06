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
| `pick-runner-v2.yml` | Runtime runner selection -- defaults to `kombi` self-hosted runners, falls back to `blacksmith-2vcpu-ubuntu-2204`, then `ubuntu-latest` as last resort |
| `build-and-push.yml` | Build Docker image and push to GHCR on the selected runner; portable Buildx works on self-hosted runners, Blacksmith 2 vCPU is the hosted fallback |
| `deploy-render.yml` | Render deploy: resolve service IDs from Doppler `prd_render`, sync service runtime env from service-specific Doppler configs, update image tag via Render API, health check |
| `deploy-render-staged.yml` | Staged deploy: staging/production variant with the same Doppler-first Render runtime sync |
| `deploy-vps-ssh.yml` | SSH-basiertes VPS Deploy nur fuer dokumentierte VPS-Ausnahmen, aktuell kombify-Simulate |
| `aspire-integration-gate.yml` | Multi-Service Health Checks via Aspire AppHost |

### Retired Workflow History

| Workflow | Purpose |
|----------|---------|
| `pick-runner.yml` | Legacy runner selection (self-hosted `kombi` default) |
| Coolify deploy workflows | Removed; Render production and preview deploys are the standard path |

## Infrastructure Overview

**Canonical rule:** customer-facing `*.kombify.io` services and preview deployments default to Render, with explicit documented exceptions. kombify.dev is not a general dev-deployment target.
**Cost rule:** reduce GitHub Actions minutes and hosted runner minutes by doing work in the cheapest correct place first:

1. Local first: `mise`, Docker Desktop, and Aspire must catch avoidable build, test, compose, and smoke failures before remote CI is dispatched.
2. Provider native second: Render-owned deploys/builds and Cloudflare Workers Builds / Pages Git integration are preferred whenever the platform can own the work.
3. CI/CD orchestration third: GitHub Actions, CircleCI, Buildkite, and GitLab should only run the gap between local validation and provider-native deploys: image promotion, secret/env sync, migrations, release gates, deploy triggers, and final smoke checks.
4. Self-hosted runners are CI capacity only. They must not create kombify.dev service deployments.
5. Hosted fallback only when needed: Blacksmith standard is `blacksmith-2vcpu-ubuntu-2204`. Do not introduce `blacksmith-4vcpu-ubuntu-2204` for routine work. `ubuntu-latest` is a last resort or probe runner, not the normal path.

The full strategy lives in `docs/ci-cd-cost-and-deployment-strategy.md`.

| Platform | Role |
|----------|------|
| **Render** | **Production and preview default** -- customer-facing SaaS services, managed PostgreSQL 17 (pgvector), managed Valkey 8 |
| **kombify-ionos** (217.154.174.107) | **Production exception** -- kombify-Sim (Docker socket + privileged) and retained company tools via Docker Compose |
| **Dev IONOS** (82.165.251.178) | **No general app deployments** -- reserved for the kombify-Simulate preview exception and explicitly retained infrastructure only. Do not deploy Administration, Desk, Cloud, AI, Blog, StackKits, SpeechKit, or other kombify-tools services here. |
| **Hostinger VPS** | **Daily tools** -- kombify.space (Excalidraw, Docs-Tools), Coolify Cloud managed |
| **Marcel's PC** | **Local development** -- 2x kombi runners (fallback) |

Render Projects: kombify-websites, kombify-ai, kombify-tools, kombify-infra. Details in [Infrastructure Overview](../kombify%20Core/internal-docs/docs/infrastructure/infrastructure-overview.md).

## CI Runner Topology

Target state: workflows that need fallback-aware runner selection use `pick-runner-v2.yml`.
Current migration state: some repos still use static `vars.CI_RUNNER`, `vars.BUILD_RUNNER`, or `vars.DEPLOY_RUNNER` fallbacks directly. Until those workflows are migrated, the org/repo variables should point at trusted self-hosted labels first.

Runner labels:

- `kombi`: preferred GitHub Actions self-hosted runner label for trusted CI/deploy orchestration.
- `srv1161760`, `srv1161760-labs`, `oci-build`, or repo-specific labels: use when a workflow needs a specific Dev/build host capability.
- `blacksmith-2vcpu-ubuntu-2204`: only Blacksmith hosted standard for routine fallback jobs.
- `ubuntu-latest` / `ubuntu-24.04`: last resort for probe jobs or workloads that cannot run on self-hosted/Blacksmith.

Policy:

- Default Build/CI/Deploy orchestration: trusted self-hosted runner labels.
- Blacksmith fallback: `blacksmith-2vcpu-ubuntu-2204` only.
- `blacksmith-4vcpu-ubuntu-2204` is not the standard anymore and should not be added to new or updated workflows without an explicit exception.
- `ubuntu-latest` consumes GitHub Actions minutes; avoid except for probe/last-resort usage.
- **Never use kombify-ionos (production) as a CI runner** -- it runs active company tool deployments alongside kombify-Sim

Provider-specific self-hosted capacity:

- Buildkite: production chains that run in Buildkite should target the self-hosted queue, currently `kombify-selfhosted`. One Dev-server agent is enough to start; add a second only when queue pressure justifies it.
- CircleCI: jobs that stay in CircleCI should use the self-hosted Linux resource class, currently `kombiverselabs/kombify-linux-x64`; hosted Docker executors are exceptions.
- GitLab: only add `.gitlab-ci.yml` for jobs backed by a self-managed GitLab Runner or for deliberately tiny hosted jobs. Do not add another hosted deploy path just to move cost between providers.

## Deploy Targets

### Production (Render)

Render manages the default production path.
Prefer Render-native behavior whenever it can own the work:

- Static sites, simple Git-backed services, and Docker services that Render can build directly should use Render build/deploy as the primary path.
- Image-backed services should use prebuilt GHCR images only when we need immutable image promotion, multi-service image coordination, local/Aspire image qualification, or build behavior Render cannot own cleanly.
- GitHub Actions, Buildkite, or CircleCI may trigger Render deploys, sync runtime env, run migrations/release gates, and smoke-check the live service, but they should not duplicate work that Render can do natively.

Doppler `prd_render` config stores Render API key and service IDs.
Service runtime configuration should come from service-specific Doppler configs (for example `prd_cloud`, `prd_admin`, `prd_ai`) and is synced onto the Render service before deploy.

Exception:

- `kombify-Sim` deploys to the IONOS VPS via `deploy-vps-ssh.yml` because it requires Docker socket access and privileged runtime behavior.
- Render secret files and linked Render env groups remain explicit exceptions until migrated; they must not become the default place for normal app configuration.

### Production (Cloudflare)

Cloudflare owns Workers, Pages, edge routing, and Cloudflare-native bindings.
Prefer Cloudflare-native CI/CD whenever it is available:

- Workers Builds or Pages Git integration should be the primary deploy path for Workers/Pages that can build from GitHub or GitLab.
- GitHub Actions, Buildkite, or CircleCI direct `wrangler deploy` workflows should be fallback paths, operator tools, or secret-sync jobs unless the Cloudflare Git integration cannot support the deployment.
- Runtime secrets must remain in Cloudflare secrets or Doppler-backed sync workflows. Do not commit runtime secrets into Wrangler config.
- Direct Wrangler deploy is acceptable for disconnected Git integrations, required secret materialization, queue/cron binding changes, or emergency rollback/fallback operations.

### Preview And Development Deployments

Render owns previews and production for all services that can run there. Use Render preview environments, Render pull request previews, or explicit Render staging services where a shared preview is required.

Do not deploy normal kombify services to `kombify.dev` or the IONOS Dev VPS. Administration and Desk have one remote version each: the live Render/production version. Simulate is the only product exception with a VPS-backed preview surface on `simulate.kombify.dev`.

### Company Tools (IONOS Production VPS)

Company tools (Paperless, FreeScout, N8N, etc.) run on the IONOS production VPS via Docker Compose.
IONOS SSH credentials stored in Doppler `kombify-io/prd_infra` (`IONOS_VPS_HOST`, `IONOS_VPS_USER`, `IONOS_SSH_PRIVATE_KEY`).
Where feasible, production Compose services materialize runtime env from Doppler during deploy and do not maintain normal app configuration manually in Coolify/remote `.env` files.

### Company-Authentifizierung (mkvl.de)

Zentrale Auth-Services auf kombify IONOS Prod schuetzen alle internen/Company Services:

- **TinyAuth** (`auth.mkvl.de`): Traefik/Coolify Forward-Auth Middleware
- **Pocket ID** (`id.mkvl.de`): Identity Provider (Google Login, OAuth)

Auf IONOS Prod nativ (gleicher Server). Auf allen anderen Servern (Dev IONOS, Hostinger, etc.) MUESSEN die externen URLs (`auth.mkvl.de`, `id.mkvl.de`) referenziert werden -- nie interne Container-Namen.
