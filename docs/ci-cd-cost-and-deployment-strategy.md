# Kombify CI/CD Cost and Deployment Strategy

This document is the internal operating model for reducing GitHub Actions
minutes and hosted runner minutes while keeping production deploys controlled.

## Goal

Remote CI should verify and deploy already-qualified changes. It should not be
the first place where avoidable local build, test, Docker, Aspire, or smoke
failures are discovered.

The cost target is:

1. Spend developer machine time first.
2. Spend deployment-provider native capacity second.
3. Spend self-hosted CI runner time third.
4. Spend hosted CI runner minutes only as a deliberate fallback.

## Execution Order

### 1. Local preflight

Before dispatching remote CI or deploy workflows, run the matching local gate:

```powershell
mise run preflight:quick
mise run preflight:release
mise run preflight:deploy
```

Use Docker Desktop for component previews and Aspire for realistic multi-repo
topologies. The shared process is documented in
`docs/local-development-deployment.md`.

### 2. Provider-native deploy

Use the deployment provider as much as possible.

Render should own builds/deploys for static sites, simple Git-backed services,
and Docker services that fit Render's model. Render image-backed services are
still acceptable when we need immutable GHCR image promotion, coordinated
multi-service releases, or local/Aspire image qualification before production.

Cloudflare should own Workers and Pages deploys through Workers Builds or Pages
Git integration when the project can be connected directly. Direct Wrangler
deploys from CI should be fallback/operator paths or secret-sync paths unless a
Cloudflare-native integration cannot support the deployment.

### 3. Minimal CI orchestration

GitHub Actions, CircleCI, Buildkite, and GitLab should cover the gap between
local validation and provider-native deploys:

- promote a prebuilt image;
- sync Doppler/runtime env into Render or Cloudflare;
- run migrations or release gates that need centralized credentials;
- trigger provider deploys or fallbacks;
- run final smoke checks.

Do not use remote CI to repeat broad local checks unless the repo needs a
required server-side signal for branch protection.

### 4. Self-hosted runners

Trusted CI and deploy orchestration should prefer self-hosted runner capacity.

- GitHub Actions: prefer `kombi` or more specific Dev/build-host labels.
- Buildkite: prefer the self-hosted queue, currently `kombify-selfhosted`.
- CircleCI: prefer the self-hosted Linux resource class, currently
  `kombiverselabs/kombify-linux-x64`.
- GitLab: only add pipelines that use a self-managed runner, or keep hosted jobs
  intentionally tiny.

The production IONOS host must not be used as general CI capacity.

### 5. Hosted fallback

Blacksmith standard is `blacksmith-2vcpu-ubuntu-2204`.

Do not add `blacksmith-4vcpu-ubuntu-2204` for routine CI/build/deploy work.
If a job really needs more hosted capacity, document the exception in the
owning workflow or repo docs.

Use `ubuntu-latest` or `ubuntu-24.04` only as a probe runner, last resort, or
for jobs that cannot run on self-hosted or Blacksmith.

## Platform Rules

### Render

Classify every Render-adjacent repo into one of these modes:

- `render-native`: Render builds/deploys from Git, Dockerfile, or static site
  config. CI should only validate, trigger, or smoke-check.
- `render-image-backed`: CI builds an immutable GHCR image and Render deploys
  that image. Use this for multi-service images, image qualification, or
  release promotion.
- `not-render`: the repo does not deploy to Render. Keep `render.yaml` absent or
  explicitly documented as a no-service marker.

### Cloudflare

Classify every Cloudflare-adjacent repo into one of these modes:

- `cloudflare-native`: Workers Builds or Pages Git integration is primary.
- `wrangler-fallback`: CI can run direct Wrangler deploy only when native builds
  are unavailable or disconnected.
- `secret-sync`: CI exists only to sync runtime secrets/configuration before the
  provider-owned deploy.

### GitHub Actions

Reusable workflows should remain available, but their defaults must support the
cost model:

- self-hosted first;
- Blacksmith 2 vCPU fallback;
- GitHub-hosted last resort.

Workflows that still use static `vars.CI_RUNNER`, `vars.BUILD_RUNNER`, or
`vars.DEPLOY_RUNNER` should either migrate to `pick-runner-v2.yml` or have the
variables set to self-hosted labels.

### Buildkite

Buildkite is a good fit for deploy-heavy production chains when it runs on our
self-hosted queue. Keep production steps branch-gated and avoid running
untrusted PR code on persistent agents.

### CircleCI

CircleCI should remain small and targeted. Use the self-hosted Linux runner for
jobs that stay there. Hosted Docker executors should be treated as temporary
exceptions.

### GitLab

GitLab can be used to spread orchestration load only when the work is backed by
self-managed runner capacity or is deliberately low-cost. Do not add GitLab as a
new production deploy control plane unless secrets, runner isolation, and
rollback ownership are documented first.

## Review Checklist

When changing a workflow or deployment doc, check:

- Did the matching local preflight exist and run first?
- Can Render or Cloudflare own more of this deploy?
- Is this workflow doing only the gap work that remains?
- Does it use self-hosted runner capacity first?
- Is Blacksmith limited to `blacksmith-2vcpu-ubuntu-2204`?
- Is `ubuntu-latest` only a probe or last resort?
- Is any exception documented near the workflow?
