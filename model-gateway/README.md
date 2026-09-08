# DM Assistant Model Gateway

This is the private Node 22.19+ model transport and provider-credential boundary
for the DM Assistant. It owns no campaign, retrieval, canonical, preparation, or
arbitrary filesystem state.

`@earendil-works/pi-ai` is pinned and lockfile-resolved at `0.84.1`. The only
registered providers are GitHub Copilot subscription OAuth, OpenAI Codex OAuth,
OpenAI API-key fallback, and Pi's deterministic faux provider. Automated tests
use faux only. OAuth and live-model
checks are deliberate manual operations and are not CI tests.

## Run locally

```bash
npm ci
export DM_MODEL_GATEWAY_INTERNAL_TOKEN="$(openssl rand -hex 32)"
export MODEL_GATEWAY_CREDENTIAL_PATH=/secure-volume/credentials.json
npm run build
node dist/src/index.js
```

The process refuses public bind addresses. Every endpoint, including `/health`,
requires the private Python caller's `Authorization: Bearer` internal token.
The browser reaches provider operations only through authenticated Workbench routes and never
receives a provider token.

When the Workbench enables the gateway, set the same value as
`DM_MODEL_GATEWAY_INTERNAL_TOKEN` in the ignored root `.env`, together with
`DM_MODEL_GATEWAY_POLICY=optional` (or `required`) and the private
`DM_MODEL_GATEWAY_URL`. This is a transport secret, not a provider credential.

OAuth login is started through `/v1/auth/login`; its status response conveys
only device-code, URL, progress, and non-secret prompt events. The gateway does
not expose a credential read endpoint. Provider OAuth data is stored only in
the configured `CredentialStore`, atomically with `0600` file permissions and
serialized updates per provider.

## Provider Operations

Before enabling a live provider, the operator must verify that the selected
account/subscription permits the intended endpoint, model, and workload. This
gateway does not treat an OAuth login as authorization for unattended or
high-volume workloads. Live OAuth and model checks are manual, explicitly
opt-in operational checks; CI exercises only the deterministic faux provider.

## Checks

```bash
npm run check
npm test
```

Do not use an unreviewed audit upgrade to change the pinned `pi-ai` transport
baseline. Run `npm audit --omit=dev` from a network-permitted environment as
part of dependency review.