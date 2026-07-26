from fastapi.middleware.cors import CORSMiddleware

CORS_CONFIG = {
    "allow_origins": ["*"],
    "allow_methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type"],
    "allow_credentials": False,
}
