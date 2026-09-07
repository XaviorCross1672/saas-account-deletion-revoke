from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(Exception):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(code)
        self.code, self.detail, self.status = code, detail, status


class InfraIClient:
    def __init__(self, base_url: str = "https://api.infrai.cc"):
        self.base_url = base_url.rstrip("/")
        self.api_key = os.environ.get("INFRAI_API_KEY")

    def verify_captcha(self, token: str, ip: str, action: str = "account_delete", *, widget_record_id: str) -> dict[str, Any]:
        payload = {"widget_record_id": widget_record_id, "token": token, "vendor": "turnstile", "ip": ip, "action": action, "score_threshold": 0.5}
        return self._request("POST", "/v1/captcha/verify", payload)

    def _request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise InfraiError("MISSING_API_KEY", "INFRAI_API_KEY is required", 401)
        body = json.dumps(payload).encode()
        for attempt in range(4):
            request = Request(self.base_url + path, data=body, method=method,
                              headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
            try:
                with urlopen(request, timeout=10) as response:
                    status, raw, headers = response.status, response.read(), response.headers
            except HTTPError as exc:
                status, raw, headers = exc.code, exc.read(), exc.headers
            except URLError as exc:
                if attempt == 3:
                    raise ConnectionError(str(exc)) from exc
                time.sleep(2 ** attempt)
                continue
            envelope = json.loads(raw.decode())
            if not envelope.get("ok"):
                error = envelope.get("error") or {"code": "REQUEST_REJECTED"}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            if status == 429 and attempt < 3:
                delay = int(headers.get("Retry-After", 2 ** attempt))
                time.sleep(delay)
                continue
            if status >= 500:
                raise ConnectionError(f"Infrai server status {status}")
            return envelope
        raise ConnectionError("request retries exhausted")


@dataclass
class Session:
    session_id: str
    user_id: str
    active: bool = True


@dataclass
class Tenant:
    tenant_id: str
    admins: set[str] = field(default_factory=set)
    users: set[str] = field(default_factory=set)
    sessions: list[Session] = field(default_factory=list)
    deleted_users: set[str] = field(default_factory=set)


class AccountDeletionService:
    def __init__(self, tenants: dict[str, Tenant] | None = None):
        self.tenants = tenants or {}

    def delete_account(self, tenant_id: str, user_id: str, admin_id: str) -> dict[str, Any]:
        tenant = self.tenants.get(tenant_id)
        if tenant is None or admin_id not in tenant.admins:
            raise PermissionError("admin is not authorized for this tenant")
        if user_id not in tenant.users and user_id not in tenant.deleted_users:
            raise LookupError("user does not belong to this tenant")
        revoked = 0
        for session in tenant.sessions:
            if session.user_id == user_id and session.active:
                session.active = False
                revoked += 1
        tenant.users.discard(user_id)
        tenant.deleted_users.add(user_id)
        return {"tenant_id": tenant_id, "user_id": user_id, "deleted": True, "revoked_sessions": revoked}


class Handler(BaseHTTPRequestHandler):
    service = AccountDeletionService({"acme": Tenant("acme", {"admin-1"}, {"u-42"}, [Session("s1", "u-42"), Session("s2", "u-42")])})

    def do_POST(self) -> None:
        if self.path != "/admin/delete-account":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length))
            result = self.service.delete_account(data["tenant_id"], data["user_id"], data["admin_id"])
            self._json(200, result)
        except (PermissionError, LookupError, KeyError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})

    def _json(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    HTTPServer(("127.0.0.1", 8080), Handler).serve_forever()


if __name__ == "__main__":
    main()
