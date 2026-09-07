from src.account_deletion_service import AccountDeletionService, Session, Tenant


def test_admin_deletion_revokes_all_sessions_and_is_idempotent():
    tenant = Tenant("acme", {"admin-1"}, {"u-42"}, [Session("s1", "u-42"), Session("s2", "u-42")])
    service = AccountDeletionService({"acme": tenant})
    result = service.delete_account("acme", "u-42", "admin-1")
    assert result == {"tenant_id": "acme", "user_id": "u-42", "deleted": True, "revoked_sessions": 2}
    assert all(not session.active for session in tenant.sessions)
    assert service.delete_account("acme", "u-42", "admin-1")["revoked_sessions"] == 0
