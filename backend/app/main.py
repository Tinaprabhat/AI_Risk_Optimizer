from fastapi import FastAPI
from app.api.routes import (health, audit, chat)
from app.utils.db import init_db
from fastapi.middleware.cors import CORSMiddleware

init_db()

app = FastAPI(
    title="AI Visibility Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)   

app.include_router(health.router)
app.include_router(audit.router)

app.include_router(
    chat.router,
    prefix="/api",
    tags=["Chat"],
)

@app.get("/")
def root():
    return {
        "message": "AI Visibility Backend Running"
    }