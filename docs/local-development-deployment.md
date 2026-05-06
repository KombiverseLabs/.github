# Kombify Local Development Deployment

This is the shared local pre-CI standard for Kombify repositories. It is an
internal developer/operator process in the `.github` repo, not a public docs
site contract.

## Core Rule

`mise` is the repo-local command contract. The shared `.github` tooling audits
and orchestrates that contract, but it does not replace repo-owned `mise.toml`
files.

Every manifest repo must also keep `docs/LOCAL_TESTING.md`. That file is the
repo-local developer entrypoint for this standard and must describe the required
`mise` gates, shared `.github` commands, preview mode, smoke command, and
preflight receipt usage for the repo.

Required developer loop:

```powershell
./scripts/kombi-bootstrap-local.ps1 -DryRun
./scripts/kombi-bootstrap-local.ps1
./scripts/kombi-dress-rehearsal.ps1 -DryRun
node scripts/kombi-local-gate.mjs doctor
node scripts/kombi-local-gate.mjs audit
node scripts/kombi-local-gate.mjs run kombify-cloud --gate quick
node scripts/kombi-local-gate.mjs run kombify-cloud --gate standard
```

Equivalent repo-local commands:

```powershell
mise run preflight:quick
mise run preflight:release
mise run preflight:deploy
```

## Gate Levels

`quick` runs `mise run preflight:quick`. It is the normal before-commit gate and
should avoid Docker unless the repo already defines Docker in that task.

`standard` runs `mise run preflight:release`. It is the default before-push or
before-remote-CI gate. It should build locally, start a Docker Desktop preview
when applicable, run health or smoke checks, and clean up unless the operator
keeps the stack running.

`full` runs the repo's hard deploy gate when present and can use Aspire for
multi-repo integration. It is the gate to run before dispatching expensive CI,
release, or deploy workflows.

## Docker Desktop

Docker Desktop remains the local runtime for production-like component checks.
Use Docker Compose for component-level preview when the repo owns a realistic
compose file.

```powershell
node scripts/kombi-local-gate.mjs up kombify-blog --mode local --keep
node scripts/kombi-local-gate.mjs smoke kombify-blog
node scripts/kombi-local-gate.mjs down kombify-blog
```

For components whose manifest runtime is `docker-compose`, `up --mode local`
uses Docker Compose directly. SaaS-like and hybrid modes continue to delegate to
repo `mise` Aspire aliases or the central Aspire AppHost.

Keep private ports, local env files, and machine-specific settings out of the
tracked manifest. Put them in:

```text
local-dev/kombify-gates.local.json
local-dev/.env*.local
local-dev/reports/
local-dev/logs/
local-dev/state/
```

Those paths are ignored by git.

## Auth0 Test Users

Cloud Login/Auth0 test identities are centrally owned in Doppler root configs,
not repo-local child configs or `.env` files:

| Runtime | Root config | Consumed through |
|---|---|---|
| Production-like tests | `kombify-io/prd` | `prd_cloud`, `prd_admin`, `prd_ai`, `prd_techstack`, `prd_sim`, `prd_stackkits` |
| Local/dev tests | `kombify-io/dev` | `dev_cloud`, `dev_admin`, `dev_ai`, `dev_techstack`, `dev_sim`, `dev_stackkits` |

Each repo's `docs/LOCAL_TESTING.md` must state which canonical role it uses
(`TEST_PRO_USER_*`, `TEST_PRO_PLUS_USER_*`, `TEST_ALL_YOU_NEED_USER_*`,
`TEST_STARTER_USER_*`, `TEST_ADMIN_*`, etc.). Workflow aliases are allowed only
as compatibility exports; the source value must remain the shared root matrix.

## Local Bootstrap

Use `kombi-bootstrap-local.ps1` to turn a fresh checkout into an executable
local development environment:

```powershell
./scripts/kombi-bootstrap-local.ps1 -DryRun
./scripts/kombi-bootstrap-local.ps1
```

The bootstrap runs the shared `doctor` and `audit` checks, then prepares each
registered repo through the repo-owned `mise` contract:

```powershell
mise trust
mise install
mise run setup
```

Useful focused runs:

```powershell
./scripts/kombi-bootstrap-local.ps1 -Repo kombify-blog -Repo kombify-cloud
./scripts/kombi-bootstrap-local.ps1 -SkipInstall -SkipSetup
```

Bootstrap evidence is written to `local-dev/reports/` and stays local-only.

Required local tools are checked by `doctor`: Docker Desktop, Docker Compose,
Doppler CLI, `mise`, Node, npm, Bun, pnpm, Go, the .NET SDK, and Aspire CLI. On
Windows, `mise` can be installed with `winget install jdx.mise`, and Doppler can
be installed with `winget install Doppler.doppler`. Aspire should be installed
after the .NET SDK, either through the official Aspire install script or
`dotnet tool install -g Aspire.Cli --prerelease`.

## Dress Rehearsals

Use `kombi-dress-rehearsal.ps1` before spending remote CI minutes:

```powershell
./scripts/kombi-dress-rehearsal.ps1 -DryRun
./scripts/kombi-dress-rehearsal.ps1
./scripts/kombi-dress-rehearsal.ps1 -LiveAspireModes local,saas
```

The dry run verifies that the local command plan is resolvable:

- `quick` gate for `kombify-blog`
- `standard` gate for `kombify-techstack`
- `full` gate for `kombify-db`
- Docker Compose `up`, `smoke`, and `down` for `kombify-blog`
- SaaS/Aspire `up` for `kombify-cloud`
- hybrid/Aspire `up` for `kombify-techstack`

The live rehearsal runs what is safe to run unattended. Docker Compose previews
are started detached and stopped again unless `-Keep` is set. The focused Cloud
Aspire topology also starts detached through the central AppHost, runs the
manifest smoke check, and stops again unless `-Keep` is set. Larger SaaS-like
topology rehearsals should be started explicitly once the focused local probe is
green.

Use `-LiveAspireModes` to opt into additional Aspire modes after the focused
Cloud probe is green. The default is `local`; `-StartAspire` remains a backwards
compatible alias that adds `saas`.

## Aspire Profiles

Aspire is the standard orchestrator when a check needs realistic multi-repo
topology, service discovery, dependency ordering, or SaaS/self-hosted/hybrid
coverage.

Profile mapping:

| Mode | Aspire profile | Purpose |
| --- | --- | --- |
| `local` | `local-minimal` | Focus repo plus required local dependencies |
| `saas` | `local-saas-like` | Full SaaS-like source topology |
| `selfhosted` | `local-minimal` | Standalone/self-hosted focus service |
| `hybrid` | `local-hybrid` | SaaS shell plus local self-hosted tool |
| `integration` | `integration-ghcr` | Qualified image verification before deploy |

Examples:

```powershell
node scripts/kombi-local-gate.mjs up kombify-cloud --mode saas --keep
node scripts/kombi-local-gate.mjs up kombify-cloud --mode integration --keep
node scripts/kombi-local-gate.mjs up kombify-simulate --mode hybrid --keep
node scripts/kombi-local-gate.mjs smoke kombify-cloud --mode saas
```

If a repo defines an explicit `mise` alias such as `aspire:hybrid`, the shared
CLI delegates to that task. Otherwise it falls back to the central AppHost at
`kombify-Core/aspire/apphost.cs` and sets `KOMBIFY_ASPIRE_PROFILE`,
`KOMBIFY_FOCUS_SERVICE`, and `KOMBIFY_REPOS_ROOT`.

For manifest components with `runtime: aspire`, the shared CLI owns the runtime
directly. It restores the AppHost with `aspire restore`, starts it detached with
`dotnet run apphost.cs --no-restore`, records local state under
`local-dev/state/`, and stops it with `aspire stop` plus process/container
cleanup. This keeps Windows/local orchestration out of repo-specific shell
syntax.

Smoke checks can use mode-specific URLs through `healthUrlsByMode` in the
manifest. This matters when one profile exposes a source dev server while
another profile exposes the production-like container port.

## Required `mise.toml` Tasks

Every Kombify repo should expose these tasks:

```text
setup
doctor
build
test
check
health
preview:local
preflight:quick
preflight:release
preflight:deploy
aspire:start
aspire:full
```

Optional aliases:

```text
aspire:saas
aspire:selfhosted
aspire:hybrid
```

The audit command reports missing tasks without modifying repos:

```powershell
node scripts/kombi-local-gate.mjs audit --json
```

## Local Reports

Use `--report` when a run should leave evidence for local triage:

```powershell
node scripts/kombi-local-gate.mjs doctor --json --report local-dev/reports/doctor.json
```

Reports are local-only. The CLI redacts environment keys containing values such
as `TOKEN`, `SECRET`, `PASSWORD`, `KEY`, `DSN`, or `DATABASE_URL`.

## Preflight receipts

Every repo-scoped CLI report also includes a local preflight receipt. Receipts
capture the repo, component, gate or mode, status, command, cwd, and current Git
metadata including branch, SHA, and dirty state.

Example:

```powershell
node scripts/kombi-local-gate.mjs run kombify-blog --gate standard --report local-dev/reports/kombify-blog-standard.json --json
```

Keep these receipts local until a CI workflow explicitly asks for a receipt or
SHA. They are intended to avoid spending remote minutes on changes that have not
passed the matching local gate.

## CI Cost Rule

Before dispatching GitHub Actions, Buildkite, CircleCI, GitLab, Render, VPS, or
Cloudflare deploy workflows, run the matching local gate first. Remote CI should
verify and deploy already-qualified changes, not discover avoidable local build,
Docker, Aspire, or smoke failures.

The cost hierarchy is:

1. Run `mise`, Docker Desktop, and Aspire locally first.
2. Let Render and Cloudflare own deploy work they can handle natively.
3. Use GitHub Actions, Buildkite, CircleCI, or GitLab only for the remaining
   orchestration: image promotion, secret/env sync, migrations, deploy triggers,
   release gates, and live smoke checks.
4. Prefer trusted self-hosted runners for that orchestration.
5. Use hosted runners only as fallback. The Blacksmith standard is
   `blacksmith-2vcpu-ubuntu-2204`; `blacksmith-4vcpu-ubuntu-2204` is not the
   default for routine work.

See `docs/ci-cd-cost-and-deployment-strategy.md` for the full provider and
runner policy.
