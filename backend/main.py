import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.models import router as models_router

# Ensure pipeline logs (including persist) are visible
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
logging.getLogger("pipeline").setLevel(logging.INFO)

app = FastAPI(title="Orbital Modeling Engine", version="1.0.0")

allowed_origins = [
    "http://localhost:3000",
]

# Allow Vercel deployment origins
frontend_url = os.environ.get("FRONTEND_URL")
if frontend_url:
    allowed_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(models_router, prefix="/v1")
