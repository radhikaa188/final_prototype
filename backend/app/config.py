import os
from dotenv import load_dotenv

# Locate project root and load environment variables from .env
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
env_path = os.path.join(ROOT_DIR, "backend", ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
elif os.path.exists(os.path.join(ROOT_DIR, ".env")):
    load_dotenv(os.path.join(ROOT_DIR, ".env"))

class Settings:
    PROJECT_NAME: str = "Revora AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Paths
    ROOT_DIR: str = ROOT_DIR
    DB_PATH: str = os.path.join(ROOT_DIR, "recoverai.db")
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
    MODEL_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ml", "saved_models")
    
    # Environment & Demo settings
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")

    # Webhook cryptographic secret
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "whsec_recoverai_test_secret_key_12345")

    # LLM Settings
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
    MISTRAL_MODEL: str = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

    # JWT Authentication & Authorization Settings (Strictly loaded from environment)
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))

    # CORS Allowed Origins
    DEFAULT_CORS_ORIGINS: list = [
        "https://frontend-six-tau-27.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]

    @property
    def CORS_ORIGINS(self) -> list:
        origins = list(self.DEFAULT_CORS_ORIGINS)
        custom_origins = os.getenv("CORS_ORIGINS") or os.getenv("FRONTEND_URL")
        if custom_origins:
            for o in custom_origins.split(","):
                cleaned = o.strip().strip("'").strip('"')
                if cleaned and cleaned not in origins:
                    origins.append(cleaned)
        return origins

settings = Settings()

