"""OfferCheck web server: `python app.py`, then open http://localhost:8000"""
import json
import os
import pathlib

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

from investigate import investigate  # noqa: E402  (needs env loaded first)

STATIC = pathlib.Path(__file__).parent / "static"
app = FastAPI(title="OfferCheck", description="Is that internship offer real? Live evidence from SerpApi.")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class OfferIn(BaseModel):
    text: str = Field(..., min_length=10, max_length=8000)
    company: str | None = Field(None, max_length=120)
    email: str | None = Field(None, max_length=200)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "serpapi_key": bool(os.getenv("SERPAPI_API_KEY"))}


@app.post("/api/investigate")
def run(offer: OfferIn):
    def stream():
        for event in investigate(offer.text, offer.company, offer.email):
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8000")))
