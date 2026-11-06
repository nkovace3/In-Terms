from fastapi import FastAPI
from api.routes import articles
from logging_config import configure_logging

configure_logging()

app = FastAPI()

app.include_router(articles.router)

# Pinged every few minutes by an external uptime monitor so Render's free
# tier never spins the API down (a cold start took 30-60s on first visit).
# Deliberately doesn't touch the database: pings shouldn't keep Neon awake
# and burn its free compute hours. HEAD too, since monitors often use it.
@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok"}
