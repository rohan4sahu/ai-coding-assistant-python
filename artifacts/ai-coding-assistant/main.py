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
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

MODEL = "gemini-2.0-flash"

# Key is loaded from env at startup but can be updated at runtime via /set-key
_api_key: str = os.environ.get("GEMINI_API_KEY", "")


def get_gemini_url() -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={_api_key}"

def get_streaming_url() -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:streamGenerateContent?key={_api_key}&alt=sse"

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static_assets")

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
    input: Optional[str] = None


class SetKeyRequest(BaseModel):
    api_key: str


@app.post("/set-key")
async def set_key(req: SetKeyRequest):
    global _api_key
    key = req.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")
    # Quick validation — Gemini keys start with AIza or are OAuth tokens
    # We do a lightweight probe to confirm the key actually works
    test_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    try:
        probe = urllib.request.urlopen(test_url, timeout=10)
        probe.read()
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        try:
            msg = json.loads(err_body).get("error", {}).get("message", err_body)
        except Exception:
            msg = err_body
        raise HTTPException(status_code=400, detail=f"Key rejected by Gemini API: {msg}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not reach Gemini API: {e}")
    _api_key = key
    return {"status": "ok"}


@app.get("/key-status")
def key_status():
    return {"configured": bool(_api_key)}


def gemini_request(contents: list, retries: int = 3) -> str:
    if not _api_key:
        raise RuntimeError("No API key configured. Please enter your Gemini API key.")
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 8192},
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        get_gemini_url(),
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


def gemini_stream(contents: list):
    """Generator that yields SSE chunks from Gemini's streaming endpoint."""
    if not _api_key:
        yield "data: [ERROR] No API key configured. Please enter your Gemini API key.\n\n"
        return
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 8192},
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        get_streaming_url(),
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            for raw_line in res:
                line = raw_line.decode("utf-8").rstrip()
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if not data_str:
                    continue
                try:
                    chunk = json.loads(data_str)
                    text = chunk["candidates"][0]["content"]["parts"][0]["text"]
                    if text:
                        yield f"data: {json.dumps(text)}\n\n"
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        try:
            error_obj = json.loads(body_text).get("error", {})
            msg = error_obj.get("message", body_text)
        except Exception:
            error_obj = {}
            msg = body_text
        msg_lower = msg.lower()
        if e.code == 429:
            # Distinguish temporary RPM limit from daily quota exhaustion
            if any(k in msg_lower for k in ("per_day", "daily", "day")):
                user_msg = (
                    "Daily Gemini API quota exhausted. Please try again after the quota "
                    "resets or use another Gemini API key/project with available quota."
                )
            else:
                user_msg = "Rate limit reached. Please wait about a minute and try again."
        elif e.code == 401:
            user_msg = "Invalid Gemini API key. Please verify your API key and try again."
        else:
            user_msg = "Gemini API returned an unexpected error. Please try again later."
        yield f"data: [ERROR] {user_msg}\n\n"
    except urllib.error.URLError:
        yield "data: [ERROR] Unable to contact Gemini API. Please check your internet connection or try again later.\n\n"
    except Exception as e:
        yield "data: [ERROR] Gemini API returned an unexpected error. Please try again later.\n\n"
    yield "data: [DONE]\n\n"


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

    return StreamingResponse(
        gemini_stream(contents),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/run")
async def run_code(req: RunRequest):
    if req.language and req.language.lower() != "python":
        raise HTTPException(status_code=400, detail="Only Python execution is supported")

    try:
        stdin_bytes = req.input.encode("utf-8") if req.input else None
        proc = await asyncio.create_subprocess_exec(
            "python3", "-c", req.code,
            stdin=subprocess.PIPE if stdin_bytes else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(input=stdin_bytes), timeout=10)
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
