from fastapi import FastAPI
from api.routes import articles
from logging_config import configure_logging

configure_logging()

app = FastAPI()

app.include_router(articles.router)
