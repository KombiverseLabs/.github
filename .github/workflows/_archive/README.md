# Workflow-Archiv

Archivierte Shared Workflows, die durch aktuelle Varianten ersetzt wurden.
**Nicht nutzen.** Dienen nur als Referenz.

## Archivierte Workflows

| Archiviert | Ersetzt durch | Grund |
|------------|--------------|-------|
| `deploy-dual.yml` | `deploy-render-staged.yml` | Coolify Space→IO Pattern abgelöst durch Render Staged Deploy |
| `deploy-coolify-v2.yml` | `deploy-render.yml` | Coolify durch Render CLI Deploy ersetzt |
| `pick-runner.yml` | `pick-runner-v2.yml` | Runner-Auswahl überarbeitet (Blacksmith Default) |

## Aktive Deployment-Pfade (ab 2026-04-04)

| Pfad | Ziel | Shared Workflow | Doppler Config |
|------|------|----------------|----------------|
| **Production (Render)** | `*.kombify.io` | `deploy-render-staged.yml` → `deploy-render.yml` | `kombify-io/prd_render` |
| **Production (VPS)** | `simulate.kombify.io` | `deploy-vps-ssh.yml` | `kombify-io/prd_infra` |
| **Development** | `*.kombify.dev` | `deploy-vps-ssh.yml` | `kombify-ionos-dev/dev` |

> Siehe `kombify Core/standards/DEVELOPMENT-STANDARDS.md` Section 4 für Details.
