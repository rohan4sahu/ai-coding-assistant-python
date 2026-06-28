import os
import asyncio
import subprocess
import urllib.request
import urllib.error
import json
import time
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set")

MODEL = "gemini-2.0-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_API_KEY}"

app = FastAPI()

SYSTEM_PROMPT = (
    "You are an expert coding assistant. You help users understand, debug, test, and optimize code. "
    "You only answer questions related to programming and software development. "
    "When providing code, always use fenced code blocks with the language specified. "
    "Be concise, accurate, and practical."
)

ACTION_PREFIXES = {
    "explain": "Explain the following code in detail, describing what it does step by step:\n\n",
    "debug": "Debug the following code. Identify all bugs, explain why each is a problem, and provide a corrected version:\n\n",
    "test": "Write comprehensive unit tests for the following code. Cover edge cases and normal usage:\n\n",
    "optimize": "Optimize the following code for performance, readability, and best practices. Explain every change you make:\n\n",
    "chat": "",
}

MAX_HISTORY = 20


class ChatRequest(BaseModel):
    message: str
    code: Optional[str] = None
    history: Optional[list] = []
    action: Optional[str] = "chat"


class RunRequest(BaseModel):
    code: str
    language: Optional[str] = "python"


def gemini_request(contents: list, retries: int = 3) -> str:
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 8192},
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        GEMINI_URL,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    for attempt in range(retries):
        try:
            res = urllib.request.urlopen(req, timeout=30)
            data = json.loads(res.read())
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            if e.code == 429 and attempt < retries - 1:
                wait = 2 ** attempt * 2
                time.sleep(wait)
                continue
            try:
                err = json.loads(body_text)
                msg = err.get("error", {}).get("message", body_text)
            except Exception:
                msg = body_text
            if e.code == 429:
                raise RuntimeError(f"Rate limit hit — please wait a moment and try again. ({msg})")
            if e.code == 401:
                raise RuntimeError("Invalid API key. Please check your GEMINI_API_KEY.")
            raise RuntimeError(f"Gemini API error {e.code}: {msg}")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            raise
    raise RuntimeError("Max retries exceeded")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest):
    action = req.action or "chat"
    prefix = ACTION_PREFIXES.get(action, "")

    user_message = req.message
    if req.code and req.code.strip():
        user_message = user_message + "\n\n```python\n" + req.code.strip() + "\n```"

    full_prompt = prefix + user_message

    history = req.history or []
    trimmed = history[-(MAX_HISTORY * 2):]
    contents = []
    for turn in trimmed:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        gemini_role = "model" if role == "model" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": content}]})
    contents.append({"role": "user", "parts": [{"text": full_prompt}]})

    try:
        reply = await asyncio.to_thread(gemini_request, contents)
        return {"reply": reply}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@app.post("/run")
async def run_code(req: RunRequest):
    if req.language and req.language.lower() != "python":
        raise HTTPException(status_code=400, detail="Only Python execution is supported")

    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", "-c", req.code,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        except asyncio.TimeoutError:
            proc.kill()
            return {"output": "", "error": "Execution timed out after 10 seconds"}

        return {
            "output": stdout.decode("utf-8", errors="replace"),
            "error": stderr.decode("utf-8", errors="replace"),
        }
    except Exception as e:
        return {"output": "", "error": str(e)}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
