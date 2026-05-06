# Workflow-Archiv

Archivierte Shared Workflows, die durch aktuelle Varianten ersetzt wurden.
**Nicht nutzen.** Alte kombify.dev-Deployment-Workflows wurden entfernt
und duerfen nicht wiederhergestellt werden.

## Archivierte Workflows

| Archiviert | Ersetzt durch | Grund |
|------------|--------------|-------|
| `pick-runner.yml` | `pick-runner-v2.yml` | Runner-Auswahl ueberarbeitet (self-hosted default, Blacksmith 2 vCPU fallback) |

## Aktive Deployment-Pfade (ab 2026-04-04)

| Pfad | Ziel | Shared Workflow | Doppler Config |
|------|------|----------------|----------------|
| **Production (Render)** | `*.kombify.io` | `deploy-render-staged.yml` → `deploy-render.yml` | `kombify-io/prd_render` |
| **Production (VPS)** | `simulate.kombify.io` | `deploy-vps-ssh.yml` | `kombify-io/prd_infra` |
| **Development** | Retired for normal services | Use Render Preview Environments | n/a |

`kombify.dev`/IONOS Dev VPS deployments were retired for normal services on 2026-05-05. Do not restore removed dual deploy or dev deploy workflows for Administration, Desk, Cloud, AI, Blog, StackKits, SpeechKit, or other kombify-tools services. The remaining VPS exception is kombify-Simulate.

> Siehe `kombify Core/standards/DEVELOPMENT-STANDARDS.md` Section 4 für Details.
