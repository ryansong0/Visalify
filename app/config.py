from pydantic_settings import BaseSettings
from pydantic import HttpUrl

class Settings(BaseSettings):
    APP_NAME: str = "VisaGuard Compliance Engine"
    VERSION: str = "2.0"
    GROQ_API_KEY: str = ""
    GROQ_URL: str = "https://api.groq.com/openai/v1"
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    VECTOR_THRESHOLD: float = 0.42
    MAX_INPUT_CHARS: int = 6000
    CORS_ORIGINS: str = "http://localhost:3000"

    class Config:
        env_file = ".env"

settings = Settings()