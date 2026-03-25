# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Default points to localhost (default for native Windows install)
    DATABASE_URL: str = "postgresql+psycopg2://postgres:password@localhost:5432/edu_ai"

    SEARCH_SERVICE_BASE_URL: str = "http://127.0.0.1:9990"
    MINIO_DEFAULT_BUCKET: str = "content-search"

    class Config:
        env_file = ".env"

settings = Settings()