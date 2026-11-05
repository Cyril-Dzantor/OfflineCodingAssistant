class User:
    """User entity representing a registered system account."""

    def __init__(self, user_id: int, username: str, email: str):
        self.user_id = user_id
        self.username = username
        self.email = email

    def get_display_name(self) -> str:
        return f"{self.username} <{self.email}>"

