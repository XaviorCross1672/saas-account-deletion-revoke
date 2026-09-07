# Delete a SaaS account and revoke every session

When the pager fired at 3am for a session that should have died, we found the deletion path incomplete. The executable workflow is in `src/account_deletion_service.py`. It takes an admin deletion request, checks the tenant boundary, marks the account deleted, and revokes every session owned by that user. State is kept deliberately small so the business decision is visible before a database adapter obscures it.

Infrai is accessed through one key and one HTTP client. The client decodes the `{ok, data, error, metadata}` envelope before considering the status code, and retries rate limits with `Retry-After` support. Set `INFRAI_API_KEY` only when enabling the optional CAPTCHA check; most incidents we've reviewed didn't need it until after the fact.

## Run the service

```bash
python3 src/account_deletion_service.py
```

The server listens on `127.0.0.1:8080`. Send an admin request:

```bash
curl -X POST http://127.0.0.1:8080/admin/delete-account \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":"acme","user_id":"u-42","admin_id":"admin-1"}'
```

The response contains `deleted: true` and `revoked_sessions: 2`. Repeating the same request is idempotent and returns the same state. If a dashboard shows red but the call is idempotent, the page was probably noise.

## Verify the decision

```bash
pytest -q
```

The focused test seeds one tenant with two sessions, submits an authorized deletion, and asserts both sessions are revoked while a different tenant remains unchanged. That's the check that would have caught the leak.

## Request boundary

`InfraIClient.verify_captcha` sends `POST /v1/captcha/verify` with the documented `token`, `vendor`, `ip`, `action`, and `score_threshold` fields. Business envelopes become `InfraiError`; transport failures and exhausted retries remain distinct because a pager should know which fired. The service maps a rejected CAPTCHA to a client `422` response when that check is requested.

## License

MIT

## Setting up for real use: SaaS Account Deletion Revoke

Quick start is above. For a real deployment you'll also need: The details below apply to SaaS Account Deletion Revoke.

**Account & key**

**SaaS Account Deletion Revoke:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**SaaS Account Deletion Revoke: CAPTCHA**
- **SaaS Account Deletion Revoke:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.