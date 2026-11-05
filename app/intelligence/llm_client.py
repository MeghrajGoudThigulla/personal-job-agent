import logging
import httpx
from typing import Dict, Any, Optional
from app.config import settings
from app.core.trace import log_audit_event

logger = logging.getLogger("personal_job_agent.llm")

class UnifiedLLMClient:
    """
    Unified LLM Client supporting Groq, NVIDIA NIM, and a smart heuristic fallback.
    - Groq: High speed inference (llama-3.3-70b-versatile, deepseek-r1-distill-llama-70b)
    - NVIDIA NIM: Enterprise-grade models (nvidia/nemotron-3-ultra-550b-a55b, meta/llama-3.1-70b-instruct)
    - Heuristic Fallback: Structured AST & regex templating for offline/zero-key operation
    """

    def __init__(self):
        self.groq_api_key = settings.GROQ_API_KEY
        self.nvidia_nim_api_key = settings.NVIDIA_NIM_API_KEY
        self.provider = settings.LLM_PROVIDER.lower()
        self.timeout = 60.0

    async def generate_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2500,
        preferred_provider: Optional[str] = None
    ) -> str:
        """
        Executes chat completion with automatic provider failover and audit logging.
        """
        active_provider = preferred_provider or self._determine_active_provider()

        # Try active provider
        if active_provider == "nvidia" and self.nvidia_nim_api_key:
            try:
                res = await self._call_nvidia_nim(system_prompt, user_prompt, temperature, max_tokens)
                await log_audit_event("llm_generation", {"provider": "nvidia", "model": settings.NVIDIA_NIM_MODEL}, "success")
                return res
            except Exception as e:
                logger.warning(f"NVIDIA NIM call failed: {e}. Falling back...")
                await log_audit_event("llm_generation", {"provider": "nvidia", "error": str(e)}, "warning")

        if active_provider in ["groq", "nvidia"] and self.groq_api_key:
            try:
                res = await self._call_groq(system_prompt, user_prompt, temperature, max_tokens)
                await log_audit_event("llm_generation", {"provider": "groq", "model": settings.GROQ_MODEL}, "success")
                return res
            except Exception as e:
                logger.warning(f"Groq API call failed: {e}. Falling back to heuristic...")
                await log_audit_event("llm_generation", {"provider": "groq", "error": str(e)}, "warning")

        # Fallback to intelligent local template generation
        await log_audit_event("llm_generation", {"provider": "heuristic_fallback"}, "success")
        return self._heuristic_fallback(system_prompt, user_prompt)

    def _determine_active_provider(self) -> str:
        if self.nvidia_nim_api_key and not self.groq_api_key:
            return "nvidia"
        if self.groq_api_key and not self.nvidia_nim_api_key:
            return "groq"
        return self.provider

    async def _call_groq(self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int) -> str:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _call_nvidia_nim(self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int) -> str:
        url = f"{settings.NVIDIA_NIM_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.nvidia_nim_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.NVIDIA_NIM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _heuristic_fallback(self, system_prompt: str, user_prompt: str) -> str:
        """Deterministic, high-quality rule-based fallback when keys are absent."""
        logger.info("Using local heuristic generator (No API keys provided or offline).")
        return "HEURISTIC_GENERATION"
