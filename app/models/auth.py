from pydantic import BaseModel


class AuthSignup(BaseModel):
    email: str
    password: str


class AuthLogin(BaseModel):
    email: str
    password: str
