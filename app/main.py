from fastapi import FastAPI
from app.routes import analyze

app = FastAPI()

app.include_router(analyze.router)