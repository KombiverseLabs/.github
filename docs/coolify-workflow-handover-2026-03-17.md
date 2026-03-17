# Coolify Workflow Handover - 2026-03-17

## Scope

This note captures the current state of the centralized Coolify deployment migration for the Kombify SaaS repos.

Target standard:

- `CI`
- `Build`
- `Deploy kombify.io (IONOS via Coolify)`
- `Deploy kombify.space (Hostinger via Coolify)`

Central reusable workflows live in:

- `.github/workflows/deploy-coolify.yml`
- `.github/workflows/sync-ghcr-auth.yml`

## What Was Already Landed

Central `.github` commits already on `main`:

- `1a821c5` `ci: allow health-check fallback for coolify deploys`
- `ff28d66` `ci: support coolify application image repositories`
- `645dc2f` `ci: add reusable ghcr auth sync workflow`
- `c0661f2` `ci: bootstrap ghcr auth into doppler`
- `a6d3524` `ci: harden ghcr auth fallback`

Key behavior after `a6d3524`:

- `sync-ghcr-auth.yml` now falls back to `github.token` when `GHCR_TOKEN_FALLBACK` is not provided.
- Doppler write-back is best-effort only (`continue-on-error: true`), because the current deploy token has read-only secret access.

Verified locally before pushing `a6d3524`:

- YAML parse of `.github/workflows/sync-ghcr-auth.yml`
- `python -m pytest tests\\test_deploy_coolify_contract.py`
- Result: `12 passed`

## Repo Status Summary

### Working or Mostly Working

- `kombify-AI`
  - `Deploy kombify.io` succeeded on run `23213580559`
  - deploy path through Coolify is functional
  - CI is still red for repo-specific E2E reasons

- `kombify-Cloud`
  - previously confirmed successful deploy over new Coolify path

- `kombify-Gateway`
  - previously confirmed successful deploy over new Coolify path

### Needs Immediate Recheck After `a6d3524`

- `kombify-Stack`
  - `Build` succeeded on run `23215701425`
  - `Deploy kombify.space` failed on run `23215814554`
  - root cause in logs: GHCR auth bootstrap failed before deploy because Doppler secret write was mandatory at that point
  - expected next outcome after `a6d3524`: auth step should proceed using fallback token even if Doppler write-back is denied

- `kombify-StackKits`
  - `Deploy kombify.space` failed on runs `23215698166`, `23215814605`, `23215881640`
  - root causes seen in logs:
    - missing GHCR token in Doppler
    - no repo `GH_PAT` available in some runs
    - hard failure on Doppler write-back before `a6d3524`
  - expected next outcome after `a6d3524`: reusable workflow should fall back to `github.token` and continue

### Deploy Workflow Green, App Runtime Still Red

- `kombify-Administration`
  - deploy run `23214762728` reaches Coolify correctly
  - failure is not GitHub Actions wiring
  - Coolify resource remains `starting:unknown`
  - app/service health still needs investigation in Coolify or container logs

### CI Red For Product/Test Reasons

- `kombify-Sim`
  - CI run `23213312221` failed in Docker E2E
  - confirmed failing assertions:
    - `tests/e2e/specs/docker-integration/docker-lifecycle.spec.ts:697`
      - SSH readiness never becomes `true`
    - `tests/e2e/specs/docker-integration/saas-mode-validation.spec.ts:262`
      - DigitalOcean provider card does not show `Test Connection`
  - also saw one flaky Chromium crash and artifact upload quota exhaustion
  - deploy workflows were skipped because CI gate stayed red

- `kombify-AI`
  - deploy works, but CI is red due repo E2E failures
  - latest inspected failing CI run: `23213514766`
  - major signal from logs:
    - large embedded widget E2E failure set
    - widget selector `[data-testid="kombify-widget"], #kombify-widget` not found across many tests
    - artifact upload also failed because Actions artifact storage quota was exhausted

## Root Causes Confirmed So Far

1. Cross-repo deploy orchestration is mostly migrated correctly.
2. Remaining deploy failures are split into two categories:
   - infrastructure/auth bootstrap issues on host runners
   - actual app/runtime readiness issues in Coolify
3. The GHCR bootstrap path was too strict before `a6d3524`.
4. Some repos do not have `GH_PAT`, so the reusable auth workflow must not assume that secret exists.
5. Several red CI runs are not deployment wiring problems. They are product/test failures.

## TODOs For Next Session

### Priority 1: Re-run the Auth-Sensitive Deploys

Re-run these first because they should be affected directly by `a6d3524`:

1. `kombify-StackKits` `Deploy kombify.space (Hostinger via Coolify)`
2. `kombify-Stack` `Deploy kombify.space (Hostinger via Coolify)`
3. `kombify-Stack` `Deploy kombify.io (IONOS via Coolify)`

Success criteria:

- `Prepare GHCR Auth` no longer fails on missing `GH_PAT`
- `Prepare GHCR Auth` no longer fails hard on Doppler write-back denial
- Coolify moves past `docker compose pull` without `unauthorized`

### Priority 2: If Stack or StackKits Still Fail, Check For New Failure Class

If the new runs are still red, inspect whether the error changed to one of:

- wrong image repository
- wrong resource UUID mapping
- app health/readiness failure after successful image pull
- server-side Docker credential persistence problem

Do not assume the old GHCR issue is still the blocker unless the new logs prove it.

### Priority 3: Administration Runtime Investigation

Focus repo:

- `kombify-Administration`

Known facts:

- deploy workflow reaches Coolify
- no public HTTP health probe is configured in workflow anymore
- Coolify still reports `starting:unknown`
- service definition from logs shows:
  - backend healthcheck `http://127.0.0.1:8080/health`
  - frontend healthcheck `http://127.0.0.1:4300/`

Next checks:

1. inspect Coolify/container logs for backend and frontend containers
2. verify backend actually binds on `8080`
3. verify frontend actually serves on `4300`
4. confirm healthcheck paths are valid inside containers

### Priority 4: Sim CI Stabilization

Focus repo:

- `kombify-Sim`

Start with the two real failing assertions, not the quota noise:

1. debug SSH readiness failure around `tests/e2e/specs/docker-integration/docker-lifecycle.spec.ts:678-697`
2. debug missing DigitalOcean `Test Connection` button around `tests/e2e/specs/docker-integration/saas-mode-validation.spec.ts:237-262`

Secondary cleanup:

- make Playwright artifact upload non-fatal if budget exhaustion keeps happening
- review whether flaky Chromium crash should be tolerated or retried separately

### Priority 5: AI CI Stabilization

Focus repo:

- `kombify-AI`

Start with the actual functional break:

1. inspect why the embedded widget selector never appears in mock-project E2E
2. confirm whether the test fixture app still mounts the widget under the expected selector
3. only after that, decide whether artifact uploads should be made non-fatal under quota pressure

## Recommended Resume Order

1. pull latest `.github` `main`
2. re-run `StackKits` and `Stack` deploy workflows
3. inspect fresh logs, not stale runs
4. only then move to `Administration`
5. after deploy path is stable, clean up `Sim` and `AI` CI

## Useful Commands

### Check recent runs

```powershell
gh run list --repo KombiverseLabs/kombify-Stack --limit 8
gh run list --repo KombiverseLabs/kombify-StackKits --limit 8
gh run list --repo KombiverseLabs/kombify-Administration --limit 8
gh run list --repo KombiverseLabs/kombify-Sim --limit 8
gh run list --repo KombiverseLabs/kombify-AI --limit 8
```

### View failing logs

```powershell
gh run view <run-id> --repo KombiverseLabs/<repo> --log-failed
```

### Re-run the likely-unblocked deploys

```powershell
gh workflow run deploy-kombify-space.yml --repo KombiverseLabs/kombify-StackKits
gh workflow run deploy-kombify-space.yml --repo KombiverseLabs/kombify-Stack
gh workflow run deploy-kombify-io.yml --repo KombiverseLabs/kombify-Stack
```

## Notes

- Treat GitHub Actions artifact quota errors as secondary unless they are the only red signal.
- Do not assume all red runs are workflow-migration regressions; several are real product/test failures.
- The highest-value next verification is whether `a6d3524` clears the Hostinger GHCR auth bottleneck.
