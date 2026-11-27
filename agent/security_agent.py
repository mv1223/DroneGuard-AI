"""Database-grounded AI Security Analyst Agent with optional LLM synthesis."""

from __future__ import annotations

import json
from typing import Any

import httpx

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    LLM_PROVIDER,
    LOG_DIR,
    OLLAMA_BASE_URL,
    OLLAMA_LLM_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
)
from core.context_manager import ContextManager
from core.logger import get_logger
from .agent_tools import build_tools

logger = get_logger("droneguard.agent", LOG_DIR)

ANALYST_SYSTEM_PROMPT = """You are DroneGuard AI, a senior drone perimeter security analyst.
Answer the operator's question strictly using the retrieved SQLite database records provided in JSON.
Rules:
1. Never invent frames, timestamps, detections, vehicle plates, or alerts not present in the JSON.
2. Cite specific frame_ids and timestamps as evidence wherever applicable.
3. Explicitly note when identity continuity across frames is only attribute-based (e.g., color/category) rather than persistent tracking.
4. Keep the response concise, structured, and actionable."""


class SecurityAgent:
    """Context-aware Security Analyst Agent supporting offline grounded Q&A and LLM synthesis."""

    def __init__(self, repository: Any, llm_provider: str | None = None):
        self.repository = repository
        self.context = ContextManager(repository)
        self.tools = build_tools(repository)
        self.llm_provider = (llm_provider or LLM_PROVIDER or "offline").lower()
        self.last_mode = "offline-grounded"

    def _select_llm(self) -> str:
        if self.llm_provider != "auto":
            return self.llm_provider
        if OPENAI_API_KEY:
            return "openai"
        if GEMINI_API_KEY:
            return "gemini"
        return "offline"

    def _synthesize_with_llm(self, question: str, grounded_ctx: dict[str, Any], provider: str) -> str:
        evidence_payload = json.dumps(
            {
                "counts": grounded_ctx["counts"],
                "matching_frames": grounded_ctx["matching_frames"],
                "matching_events": grounded_ctx["matching_events"],
                "alerts": grounded_ctx["alerts"],
                "latest_telemetry": grounded_ctx["latest_telemetry"],
                "daily_summary": grounded_ctx["daily_summary"],
                "recent_conversation": self.context.history[-4:],
            },
            default=str,
        )
        user_msg = f"Operator Question: {question}\n\nGrounded SQLite Records:\n{evidence_payload}"

        if provider == "openai" and OPENAI_API_KEY:
            resp = httpx.post(
                f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENAI_MODEL,
                    "temperature": 0.1,
                    "messages": [
                        {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                },
                timeout=25.0,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()

        if provider == "gemini" and GEMINI_API_KEY:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
            )
            resp = httpx.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [
                        {"parts": [{"text": f"{ANALYST_SYSTEM_PROMPT}\n\n{user_msg}"}]}
                    ],
                    "generationConfig": {"temperature": 0.1},
                },
                timeout=25.0,
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        if provider == "ollama":
            resp = httpx.post(
                f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                json={
                    "model": OLLAMA_LLM_MODEL,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                },
                timeout=25.0,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()

        raise RuntimeError(f"LLM provider '{provider}' is not configured.")

    def ask(self, question: str) -> str:
        """Answer a security question using grounded SQLite retrieval (+ optional LLM)."""
        return self.ask_structured(question)["answer"]

    def ask_structured(self, question: str) -> dict[str, Any]:
        """Return answer text plus grounding metadata (mode, cited frames, history)."""
        provider = self._select_llm()
        ctx = self.context.build_grounded_context(question)

        if provider in ("openai", "gemini", "ollama"):
            try:
                text = self._synthesize_with_llm(question, ctx, provider)
                cited = [f["frame_id"] for f in ctx["matching_frames"]]
                self.context._record_turn(question, text, ctx["entities"], cited)
                self.last_mode = f"llm:{provider}"
                return {
                    "answer": text,
                    "mode": self.last_mode,
                    "cited_frame_ids": cited,
                    "history": list(self.context.history),
                }
            except Exception as exc:
                logger.warning("LLM synthesis failed (%s), falling back to offline grounded mode: %s", provider, exc)

        answer = self.context.answer_offline(question)
        self.last_mode = "offline-grounded"
        return {
            "answer": answer,
            "mode": self.last_mode,
            "cited_frame_ids": list(self.context.state.get("last_frame_ids", [])),
            "history": list(self.context.history),
        }
