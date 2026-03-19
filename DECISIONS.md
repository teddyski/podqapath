# PodQApath — Architecture Decision Log
[2026-03-18] Decision: FastAPI + React/Vite as parallel frontend (SCRUM-19)
Context: Need a React-based UI to replace/complement Streamlit without breaking existing app.py
Options Considered: (1) Keep Streamlit only, (2) Embed React in Streamlit via components, (3) Separate FastAPI backend + standalone React SPA
Chosen: Option 3 — FastAPI backend at port 8000, React SPA via Vite dev server at port 5173; production build served by FastAPI staticfiles
Reason: Clean separation of concerns; mcp_bridge.py reused as library without modification; no Streamlit dependency in new stack; Vite proxy eliminates CORS issues during dev; production collapses to single process
Tradeoffs: Two processes to run during dev; credentials must be in .env (no runtime input); requires npm toolchain
---

[2026-03-19] Decision: Elixir/Phoenix as parallel backend for PodQApath
Context: Need a second backend implementation in Elixir/Phoenix that mirrors the FastAPI backend's API surface exactly, so the React frontend can optionally target it at port 4000.
Options Considered: (1) Extend FastAPI backend with more features; (2) Write a Node.js/Express backend; (3) Write an Elixir/Phoenix backend
Chosen: Option 3 — Elixir/Phoenix --no-ecto --no-html --no-assets --no-mailer scaffold
Reason: Phoenix is excellent for SSE streaming (used by run-tests endpoint), fault-tolerant via OTP, and Req library provides a clean HTTP client equivalent to Python's requests/httpx.
Tradeoffs: Adds a second language to the project; Elixir/OTP knowledge required for maintenance. The SSE run-tests endpoint uses Port.open instead of async generators (Python approach), which is idiomatic Elixir but different mental model.
---

[2026-03-19] Decision: Use Port.open for Playwright SSE streaming in Elixir
Context: Elixir's System.cmd/3 buffers stdout until the process exits, which would defeat real-time test result streaming.
Options Considered: (1) System.cmd with post-hoc streaming; (2) Port.open with {:line, N} option; (3) External Task with async reads
Chosen: Port.open with {:spawn_executable, pw_bin} and :line mode
Reason: Port.open delivers lines as Erlang messages in real time, allowing the controller to chunk each line to the SSE conn as it arrives, matching the Python asyncio generator behaviour.
Tradeoffs: Port requires charlist env vars (vs binary in System.cmd); exit_status must be received separately after the output loop.
---
