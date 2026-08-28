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
    PROJECT_NAME: str = "RecoverAI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Paths
    ROOT_DIR: str = ROOT_DIR
    DB_PATH: str = os.path.join(ROOT_DIR, "recoverai.db")
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
    MODEL_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ml", "saved_models")
    
    # Webhook cryptographic secret
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "whsec_recoverai_test_secret_key_12345")

    # LLM Settings
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
    MISTRAL_MODEL: str = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

settings = Settings()
