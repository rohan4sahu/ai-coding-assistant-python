# AI Coding Assistant (Python)

An AI-powered Python coding assistant that combines a code editor, Python execution, and an intelligent AI assistant into a single web application. Users can write, run, debug, optimize, and understand Python code without leaving the browser.

## 🌐 Live Demo

https://ai-coding-assistant-python.onrender.com/

---

## ✨ Features

* 🤖 AI-powered coding assistant using Google Gemini 2.0 Flash
* 📝 Built-in Python code editor
* ▶️ Execute Python code directly in the browser
* ⌨️ Program input (stdin) support
* 💬 Context-aware AI chat with streaming responses
* 🔍 Explain Python code
* 🐞 Debug code and identify issues
* ⚡ Optimize code for readability and performance
* 💾 Automatic saving of editor content, chat history, and API key using localStorage
* 🎨 Clean, minimalist interface

---

## 🛠 Tech Stack

### Backend

* Python
* FastAPI
* Uvicorn

### Frontend

* HTML
* CSS
* JavaScript
* CodeMirror

### AI

* Google Gemini 2.0 Flash API

### Deployment

* Render

---

## 📂 Project Structure

```text
main.py
static/
 ├── index.html
 ├── style.css
 └── script.js
```

---

## 🚀 Running Locally

```bash
git clone https://github.com/rohan4sahu/ai-coding-assistant-python.git

cd ai-coding-assistant-python

uv sync

uvicorn main:app --reload
```

Open:

```
http://localhost:8000
```

---

## 🔑 API Key

This application requires a **Google Gemini API key**.

Enter your own Gemini API key when prompted after launching the application.

Your API key is stored locally in your browser and is **never included in the repository**.

---

## 📌 Notes

* Supports **Python** code execution.
* Interactive program input (`stdin`) is supported.
* AI responses include the current editor content as context.
* Users provide their own Gemini API key.

---

## 🧑‍💻 Development

This project was built using an AI-assisted development workflow in **Replit** and refined through iterative testing, UI improvements, and deployment.

---

## 📄 License

This project is intended for educational and personal learning purposes.
