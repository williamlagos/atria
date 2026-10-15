import os

import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Showcase Python API", version="1.0.0")

# Enable CORS for local testing.
# When served through Firebase Hosting rewrites, requests bypass CORS automatically.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


@app.get("/api/health")
def health_check():
    """Health check endpoint that verifies database connectivity."""
    db_status = "unconfigured"
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
            conn.close()
            db_status = "connected"
        except Exception as e:
            db_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "service": "cloud-run",
        "database": db_status,
        "gemini_configured": bool(GEMINI_API_KEY),
    }


class PromptRequest(BaseModel):
    prompt: str


@app.post("/api/ai/generate")
def generate_ai_text(req: PromptRequest):
    """Example AI endpoint using Google Gemini (Google AI Pro)."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    try:
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=req.prompt,
        )
        return {"response": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
