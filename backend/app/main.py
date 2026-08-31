from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db.session import engine, Base, SessionLocal
from app.db import models
from app.auth.init_users import seed_default_users

# Ensure tables exist and seed demo users
Base.metadata.create_all(bind=engine)
with SessionLocal() as db_session:
    seed_default_users(db_session)

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.payments import router as payments_router
from app.api.customers import router as customers_router
from app.api.recovery_cases import router as recovery_cases_router
from app.api.agent import router as agent_router
from app.api.analytics import router as analytics_router
from app.api.audit import router as audit_router
from app.api.policies import router as policies_router
from app.api.notifications import router as notifications_router
from app.api.test_mode import router as test_mode_router
from app.api.webhooks import router as webhooks_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url="/api/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Cache-Control",
        "Pragma",
        "Accept",
        "Origin",
        "X-Requested-With",
    ],
)

# Register routers under /api
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(dashboard_router, prefix=settings.API_V1_STR)
app.include_router(payments_router, prefix=settings.API_V1_STR)
app.include_router(customers_router, prefix=settings.API_V1_STR)
app.include_router(recovery_cases_router, prefix=settings.API_V1_STR)
app.include_router(agent_router, prefix=settings.API_V1_STR)
app.include_router(analytics_router, prefix=settings.API_V1_STR)
app.include_router(audit_router, prefix=settings.API_V1_STR)
app.include_router(policies_router, prefix=settings.API_V1_STR)
app.include_router(notifications_router, prefix=settings.API_V1_STR)
app.include_router(test_mode_router, prefix=settings.API_V1_STR)
app.include_router(webhooks_router, prefix=settings.API_V1_STR)

@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.PROJECT_NAME, "version": settings.VERSION}
