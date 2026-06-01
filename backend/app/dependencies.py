import json
import logging
import os

import firebase_admin
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

logger = logging.getLogger(__name__)
_bearer = HTTPBearer()


def _ensure_firebase() -> None:
    if firebase_admin._apps:
        return

    creds_json = os.getenv("FIREBASE_ADMIN_CREDENTIALS")
    if creds_json:
        cred = credentials.Certificate(json.loads(creds_json))
        firebase_admin.initialize_app(cred)
        return

    service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if service_account_path:
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
        return

    raise RuntimeError(
        "Firebase Admin credentials not configured. "
        "Set FIREBASE_ADMIN_CREDENTIALS (JSON string) or "
        "GOOGLE_APPLICATION_CREDENTIALS (path to service account file)."
    )


async def get_current_firebase_uid(
    http_creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    try:
        _ensure_firebase()
    except RuntimeError as exc:
        logger.error("Firebase Admin setup error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    try:
        decoded = firebase_auth.verify_id_token(http_creds.credentials)
        uid: str = decoded["uid"]
        return uid
    except Exception as exc:
        logger.warning("Token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase token",
            headers={"WWW-Authenticate": "Bearer"},
        )
