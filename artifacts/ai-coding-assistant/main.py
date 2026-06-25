import os
import subprocess
import asyncio
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google import genai
from google.genai import types

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set")

client = genai.Client(api_key=GEMINI_API_KEY)

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

    # Build history for multi-turn
    history = req.history or []
    trimmed = history[-(MAX_HISTORY * 2):]
    gemini_history = []
    for turn in trimmed:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        gemini_history.append(
            types.Content(role=role, parts=[types.Part(text=content)])
        )

    try:
        def _send():
            chat_session = client.chats.create(
                model="gemini-1.5-flash",
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                history=gemini_history,
            )
            response = chat_session.send_message(full_prompt)
            return response.text

        reply = await asyncio.to_thread(_send)
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
