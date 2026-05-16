from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load .env file
load_dotenv()


class Settings(BaseSettings):

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ai_visibility"

    REDIS_URL: str = "redis://localhost:6379"

    GEMINI_API_KEY: str = ""

    class Config:
        env_file = ".env"


settings = Settings()