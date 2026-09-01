from sqlalchemy.orm import Session
from app.db.models import User
from app.auth.security import hash_password

DEFAULT_USERS = [
    {
        "email": "admin@revora.ai",
        "name": "System Administrator",
        "password": "admin123",
        "role": "ADMIN"
    },
    {
        "email": "ops@revora.ai",
        "name": "Operations Lead",
        "password": "ops123",
        "role": "OPS"
    },
    {
        "email": "viewer@revora.ai",
        "name": "Financial Analyst",
        "password": "viewer123",
        "role": "VIEWER"
    },
    {
        "email": "admin@recoverai.io",
        "name": "System Administrator (Legacy)",
        "password": "admin123",
        "role": "ADMIN"
    },
    {
        "email": "ops@recoverai.io",
        "name": "Operations Lead (Legacy)",
        "password": "ops123",
        "role": "OPS"
    },
    {
        "email": "viewer@recoverai.io",
        "name": "Financial Analyst (Legacy)",
        "password": "viewer123",
        "role": "VIEWER"
    }
]

def seed_default_users(db: Session):
    """Seeds default accounts for Admin, Ops, and Viewer roles if not present."""
    for user_info in DEFAULT_USERS:
        existing = db.query(User).filter(User.email == user_info["email"]).first()
        if not existing:
            user = User(
                email=user_info["email"],
                name=user_info["name"],
                password_hash=hash_password(user_info["password"]),
                role=user_info["role"],
                is_active=True
            )
            db.add(user)
    db.commit()
