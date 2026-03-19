# PodQApath — Architecture Decision Log
[2026-03-18] Decision: FastAPI + React/Vite as parallel frontend (SCRUM-19)
Context: Need a React-based UI to replace/complement Streamlit without breaking existing app.py
Options Considered: (1) Keep Streamlit only, (2) Embed React in Streamlit via components, (3) Separate FastAPI backend + standalone React SPA
Chosen: Option 3 — FastAPI backend at port 8000, React SPA via Vite dev server at port 5173; production build served by FastAPI staticfiles
Reason: Clean separation of concerns; mcp_bridge.py reused as library without modification; no Streamlit dependency in new stack; Vite proxy eliminates CORS issues during dev; production collapses to single process
Tradeoffs: Two processes to run during dev; credentials must be in .env (no runtime input); requires npm toolchain
---
