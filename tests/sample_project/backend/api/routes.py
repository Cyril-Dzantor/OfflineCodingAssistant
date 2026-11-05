from backend.auth.service import AuthenticationService


def login_route(request_data: dict) -> dict:
    """API endpoint handling user login requests."""
    auth_service = AuthenticationService()
    username = request_data.get("username", "")
    password = request_data.get("password", "")

    if auth_service.authenticate_user(username, password):
        token = auth_service.generate_token(1)
        return {"status": "success", "token": token}
    return {"status": "error", "message": "Invalid credentials"}

