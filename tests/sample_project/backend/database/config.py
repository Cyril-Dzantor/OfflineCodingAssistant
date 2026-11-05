class DatabaseConfig:
    """Database connection settings and pool configuration."""
    HOST = "localhost"
    PORT = 5432
    DB_NAME = "app_db"
    POOL_SIZE = 10


def init_db_connection(host: str = DatabaseConfig.HOST, port: int = DatabaseConfig.PORT):
    """Initializes connection to the PostgreSQL database."""
    print(f"Connecting to database at {host}:{port}")
    return True

