from backend.auth.service import AuthenticationService


def test_authenticate_success():
    """Verifies that valid credentials authenticate successfully."""
    service = AuthenticationService()
    assert service.authenticate_user("admin", "hashed_pwd") is True


def test_authenticate_failure():
    """Verifies that invalid credentials fail authentication."""
    service = AuthenticationService()
    assert service.authenticate_user("wrong_user", "") is False

