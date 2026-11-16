import pytest
from unittest.mock import AsyncMock, patch
from app.intelligence.llm_client import UnifiedLLMClient
from app.config import settings

@pytest.mark.asyncio
async def test_llm_auto_failover_groq_to_nvidia():
    client = UnifiedLLMClient()
    settings.GROQ_API_KEY = "test_groq_key"
    settings.NVIDIA_NIM_API_KEY = "test_nvidia_key"
    settings.LLM_PROVIDER = "auto"

    # Simulate Groq throwing an exception (e.g. Rate Limit 429)
    with patch.object(client, "_call_groq", side_effect=Exception("Rate limit 429")):
        with patch.object(client, "_call_nvidia_nim", new_callable=AsyncMock) as mock_nvidia:
            mock_nvidia.return_value = "Tailored via NVIDIA NIM fallback"
            res = await client.generate_completion("system prompt", "user prompt")

            assert res == "Tailored via NVIDIA NIM fallback"
            assert mock_nvidia.called

@pytest.mark.asyncio
async def test_llm_auto_failover_nvidia_to_groq():
    client = UnifiedLLMClient()
    settings.GROQ_API_KEY = "test_groq_key"
    settings.NVIDIA_NIM_API_KEY = "test_nvidia_key"
    settings.LLM_PROVIDER = "nvidia"

    # Simulate NVIDIA throwing an exception
    with patch.object(client, "_call_nvidia_nim", side_effect=Exception("NVIDIA 503 Service Unavailable")):
        with patch.object(client, "_call_groq", new_callable=AsyncMock) as mock_groq:
            mock_groq.return_value = "Tailored via Groq fallback"
            res = await client.generate_completion("system prompt", "user prompt")

            assert res == "Tailored via Groq fallback"
            assert mock_groq.called

@pytest.mark.asyncio
async def test_llm_all_fail_triggers_heuristic():
    client = UnifiedLLMClient()
    settings.GROQ_API_KEY = "test_groq_key"
    settings.NVIDIA_NIM_API_KEY = "test_nvidia_key"

    with patch.object(client, "_call_groq", side_effect=Exception("Network error")):
        with patch.object(client, "_call_nvidia_nim", side_effect=Exception("Quota exceeded")):
            res = await client.generate_completion("system prompt", "user prompt")
            assert res == "HEURISTIC_GENERATION"


@pytest.mark.asyncio
async def test_llm_multi_provider_routing():
    client = UnifiedLLMClient()

    # 1. Test OpenAI routing
    settings.OPENAI_API_KEY = "test_openai_key"
    with patch.object(client, "_call_openai", new_callable=AsyncMock) as mock_openai:
        mock_openai.return_value = "Response from OpenAI"
        res = await client.generate(prompt="Hello", preferred_provider="openai")
        assert res["text"] == "Response from OpenAI"
        assert res["provider"] == "openai"
        assert mock_openai.called

    # 2. Test Anthropic routing
    settings.ANTHROPIC_API_KEY = "test_anthropic_key"
    with patch.object(client, "_call_anthropic", new_callable=AsyncMock) as mock_anthropic:
        mock_anthropic.return_value = "Response from Claude"
        res = await client.generate(prompt="Hello", preferred_provider="anthropic")
        assert res["text"] == "Response from Claude"
        assert res["provider"] == "anthropic"
        assert mock_anthropic.called

    # 3. Test Ollama routing
    settings.OLLAMA_BASE_URL = "http://localhost:11434"
    with patch.object(client, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = "Response from local Ollama"
        res = await client.generate(prompt="Hello", preferred_provider="ollama")

        assert res["text"] == "Response from local Ollama"
        assert res["provider"] == "ollama"
        assert mock_ollama.called

