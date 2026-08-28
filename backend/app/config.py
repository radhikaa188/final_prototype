import os

class Settings:
    PROJECT_NAME: str = "RecoverAI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Absolute path to database file in project root
    ROOT_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    DB_PATH: str = os.path.join(ROOT_DIR, "recoverai.db")
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
    MODEL_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ml", "saved_models")
    
    # Webhook cryptographic secret
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "whsec_recoverai_test_secret_key_12345")

settings = Settings()
