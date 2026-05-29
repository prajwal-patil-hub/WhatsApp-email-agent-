from pydantic import BaseModel


class TokenRequest(BaseModel):
    phone_number: str
    admin_secret: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: str
    role: str
    jti: str
