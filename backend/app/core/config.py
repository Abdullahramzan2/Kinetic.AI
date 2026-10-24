from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    OPENAI_API_KEY: str = ""
    JWT_TOKEN_KEY: str
    ALGORITHM: str
    LLM_PROVIDER: str = "openai"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434/v1"
    OLLAMA_MODEL: str = "llama3.2"
    HF_HOME: str = "./model_cache"
    ALLOWED_ORIGINS: list = [
        "*",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://mellifluous-noncalculative-gwenn.ngrok-free.dev",
        "http://localhost:5173"
        ]
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
