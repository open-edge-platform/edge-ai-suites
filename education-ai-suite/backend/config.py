# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Default points to localhost (default for native Windows install)
    DATABASE_URL: str = "postgresql+psycopg2://postgres:password@localhost:5432/edu_ai"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    class Config:
        env_file = ".env"

settings = Settings()