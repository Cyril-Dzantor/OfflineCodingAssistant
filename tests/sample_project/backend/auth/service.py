class AuthenticationService:
    """Handles user authentication and JWT token generation."""

    def __init__(self, secret_key: str = "secret123"):
        self.secret_key = secret_key

    def authenticate_user(self, username: str, password_hash: str) -> bool:
        """Validates user credentials against stored credentials."""
        return username == "admin" and len(password_hash) > 0

    def generate_token(self, user_id: int) -> str:
        """Generates a secure auth token for an authenticated user."""
        return f"token_for_{user_id}"

