import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import uvicorn

from routes.index import router

# ── Logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
)

# ── App FastAPI ────────────────────────────────────────────────────────
app = FastAPI(
    title="Fortnite Tracker API",
    description="API pessoal para consultar estatísticas de jogadores no Fortnite Tracker.",
    version="2.0.0",
)

app.include_router(router)

# ── Static Frontend ───────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", include_in_schema=False)
async def serve_frontend():
    return RedirectResponse(url="/static/index.html")


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
