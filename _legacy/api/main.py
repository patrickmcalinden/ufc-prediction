from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import fighters, bets, blog, predictions
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="UFC Prediction Engine API",
    description="Backend ML routing system serving fighter metrics, Elo stats, and live predictions.",
    version="1.0.0"
)

env_cors = os.getenv("ENV", "development")
origins = ["*"] if env_cors == "development" else [os.environ.get("FRONTEND_URL", "http://localhost:5173")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fighters.router, prefix="/fighters", tags=["fighters"])
app.include_router(predictions.router, prefix="/predictions", tags=["predictions"])
app.include_router(bets.router, prefix="/bets", tags=["bets"])
app.include_router(blog.router, prefix="/blog", tags=["blog"])

@app.get("/health")
def health_check():
    return {"status": "optimized and live"}
