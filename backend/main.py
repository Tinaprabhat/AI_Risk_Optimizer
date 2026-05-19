import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.utils.db import init_db
from backend.app.api.routes import router

app = FastAPI(
    title="AI Rep Optimizer",
    description="Audit how AI shopping agents see your Shopify store",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()

app.include_router(router, prefix="/api")

@app.get("/")
def root():
    return {"status": "AI Rep Optimizer API is running"}