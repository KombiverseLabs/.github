# Feature Flag Release Gate (composite action)

Checks that all required feature flags for a tool category are released
on the kombify-Administration side before a production deploy proceeds.

## Auth paths

The action supports two auth paths to talk to
`https://admin.kombify.io/api/v1/feature-flags/release-manifest`:

### 1. `service-auth-secret` — preferred (stateless)

Pass the HMAC `SERVICE_AUTH_SECRET` shared with kombify-Administration
(Doppler: `kombify-io/prd_admin`). The action:

1. Mints a 5-minute HS256 JWT inline with claims
   `{iss, aud:"kombify-administration", svc:<caller-name>, iat, exp}`.
2. Sends it via the `X-Kombify-Service-Auth` header.
3. Admin verifies it via
   [`tryServiceAuth()`](../../../kombify-Administration/frontend/src/lib/server/api-helpers.ts).

No long-lived bearer tokens. No Doppler key to rotate. The HMAC is the
same secret already used for service-to-service auth across the platform.

```yaml
- uses: KombiverseLabs/.github/.github/actions/feature-flag-gate@<sha>
  with:
    category: kombify-ai
    required-flags: '["ai_enabled"]'
    service-auth-secret: ${{ steps.fetch-secret.outputs.service_auth_secret }}
    caller-name: ai   # must be in SERVICE_AUTH_ALLOWED_CALLERS on Admin
```

`caller-name` defaults to `ai`. The Admin's
`DEFAULT_SERVICE_AUTH_ALLOWED_CALLERS` is
`[cloud, ai, sim, techstack, stackkits, admin-jobs]` — set
`SERVICE_AUTH_ALLOWED_CALLERS` env on the Admin to override.

### 2. `service-key` — legacy

Pre-signed shared key compared against `ADMIN_SERVICE_KEY` (Doppler:
`kombify-io/prd_admin`) on the Admin side via
`Authorization: Bearer`. Existing pipelines using this path keep
working unchanged.

```yaml
- uses: KombiverseLabs/.github/.github/actions/feature-flag-gate@<sha>
  with:
    category: kombify-ai
    required-flags: '["ai_enabled"]'
    service-key: ${{ secrets.ADMIN_SERVICE_KEY }}
```

If both `service-auth-secret` and `service-key` are set,
`service-auth-secret` wins.

## Bypass

For true emergencies only. Writes a bypass-audit line to
`$GITHUB_STEP_SUMMARY` for review.

```yaml
- uses: KombiverseLabs/.github/.github/actions/feature-flag-gate@<sha>
  with:
    category: kombify-ai
    bypass-fragile: "true"
```

## Doppler token convention

The deploy workflow needs a Doppler token with read access to
`kombify-io/prd_admin` to fetch `SERVICE_AUTH_SECRET` (or
`ADMIN_SERVICE_KEY`). Repos store it as repository secret
`DOPPLER_TOKEN_IO_ADMIN`. Naming convention for the Doppler service
token: `gha-prd-admin-readonly`.
