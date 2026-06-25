# AI Coding Assistant

A full-stack AI-powered coding assistant with a Python/CodeMirror editor and Gemini-powered chat.

## Run & Operate

- `Start application` workflow — runs the FastAPI server at port 3000
- Command: `cd artifacts/ai-coding-assistant && uvicorn main:app --host 0.0.0.0 --port 3000 --reload`
- Required secret: `GEMINI_API_KEY` — Google Gemini API key (set in Replit Secrets)

## Stack

- Backend: Python FastAPI + uvicorn (port 3000)
- Frontend: Single HTML file with CodeMirror 5 (Dracula theme) + highlight.js
- AI: Google Gemini 1.5 Flash via `google-genai` SDK
- No npm/Node for the app itself — pure Python backend serving static HTML

## Where things live

- `artifacts/ai-coding-assistant/main.py` — FastAPI app with `/chat`, `/run`, `/health` endpoints
- `artifacts/ai-coding-assistant/static/index.html` — Full single-page frontend (editor + chat)

## Architecture decisions

- Uses `google-genai` (new SDK) instead of deprecated `google-generativeai`
- Multi-turn chat maintained client-side (history array), last 20 turns sent per request
- Python code execution via `asyncio.create_subprocess_exec` with 10s timeout
- Static files served by FastAPI's `StaticFiles` mount at root `/`
- No React, no npm — pure HTML/CSS/JS loaded from CDN

## Product

- Split-pane layout: left = CodeMirror Python editor, right = Gemini chat
- Toolbar: Explain / Debug / Write Tests / Optimize / Run ▶ / Clear
- Chat: typing indicator, code blocks with copy buttons, quick-action chips
- Code runner: executes Python in subprocess, shows stdout/stderr with status

## User preferences

_Populate as you build._

## Gotchas

- `google-genai` (new) vs `google-generativeai` (deprecated) — always use `from google import genai`
- Uvicorn hot-reload watches `artifacts/ai-coding-assistant/` directory
- Port 3000 is the webview port routed through the shared Replit proxy
