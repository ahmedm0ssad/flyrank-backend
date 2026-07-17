from fastapi import FastAPI

from app.routers import tasks

app = FastAPI(title="FlyRank API", version="0.2.0")

app.include_router(tasks.router)


@app.get("/")
def home():
    return {"message": "Hello FlyRank"}


@app.get("/health")
def health():
    return {"status": "ok"}
