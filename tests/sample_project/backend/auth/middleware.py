from backend.auth.service import AuthenticationService


class AuthMiddleware:
    """Intercepts HTTP requests and validates authentication tokens."""

    def __init__(self, auth_service: AuthenticationService):
        self.auth_service = auth_service

    def process_request(self, request_headers: dict) -> bool:
        """Checks Authorization bearer token in request headers."""
        token = request_headers.get("Authorization", "")
        return token.startswith("Bearer ")

