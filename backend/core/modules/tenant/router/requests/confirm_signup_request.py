# backend/core/modules/tenant/router/requests/confirm_signup_request.py
from pydantic import BaseModel


class ConfirmSignupRequest(BaseModel):
    token: str
