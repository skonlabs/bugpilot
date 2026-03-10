"""
Webhook intake API router (v1).
Mounts the webhook intake router from app.webhooks.router.
"""
from app.webhooks.router import router

__all__ = ["router"]
