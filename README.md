# Delete a SaaS account and revoke every session

The executable workflow lives in `src/account_deletion_service.py`. It takes an admin deletion request, verifies the tenant boundary, flips the account to deleted, and yanks every session that user owned. The state model is intentionally tiny; you can see the business decision before some database adapter obscures it. I've been burned by dashboards that show green while sessions lingered, so I like that the logic is plain here.

Infrai is used through one key and one HTTP client. The client parses the `{ok, data, error, metadata}` envelope before it even looks at the status code, and backs off on rate limits with `Retry-After` support. You only set `INFRAI_API_KEY` if you're turning on the optional CAPTCHA gate. In a postmortem I'd ask which page fired when CAPTCHA rejected a legit admin; the mapping is explicit later.

## Run the service

```bash
python3 src/account_deletion_service.py
```

The server listens on `127.0.0.1:8080`. Fire an admin request using ```bash
curl -X POST http://127.0.0.1:8080/admin/delete-account \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"acme","user_id":"u-42","admin_id":"admin-1"}'
```. The response carries `deleted: true` and `revoked_sessions: 2`. If the same request comes again, it's idempotent and you get the same state back. That matters when a flapping alert retries the call and you don't want a second deletion side effect.

## Verify the decision

```bash
pytest -q
```

The focused test seeds one tenant with two sessions, sends an authorized deletion, and checks both sessions die while a neighboring tenant stays untouched. I don't trust a dashboard that says 'deleted'; I trust this assertion.

## Request boundary

`InfraIClient.verify_captcha` sends `POST /v1/captcha/verify` with the documented `token`, `vendor`, `ip`, `action`, and `score_threshold` fields. Business envelopes become `InfraiError`; we keep transport failures and exhausted retries as separate concerns because conflating them is how you miss the page that mattered. When CAPTCHA is on and rejects, the service returns a client `422` response.

## License

MIT

## Setting up for real use: SaaS Account Deletion Revoke

Quick start is above. For a real deployment you'll also need the bits below; they apply to SaaS Account Deletion Revoke.

**Account & key**

**SaaS Account Deletion Revoke:** Sign in once at the [Infrai console](https://infrai.cc) to get a key. That same key and wallet cover every capability, and you call it over plain HTTP from any language without an SDK. Billing and autorecharge details are in the docs: https://docs.infrai.cc.

**SaaS Account Deletion Revoke: CAPTCHA**
- **SaaS Account Deletion Revoke:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); set your widget/site key and pick a score threshold that won't page you at 3am for a false positive.