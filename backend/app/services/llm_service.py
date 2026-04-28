import asyncio
import json
import logging
import socket
from urllib.parse import urlparse


try:
    import ollama
except ImportError:  # pragma: no cover
    ollama = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class LLMService:
    CONNECT_TIMEOUT_SECONDS = 1.0

    def __init__(self, backend: str, model: str, endpoint: str | None = None) -> None:
        self.backend = backend.lower()
        self.model = model
        self.endpoint = endpoint
        self._available = self.backend == "ollama" and ollama is not None
        self._reachability_checked = False
        logger.info(
            "LLMService initialized: backend=%s model=%s endpoint=%s ollama_package=%s",
            self.backend,
            self.model,
            self.endpoint or "(default)",
            "available" if ollama is not None else "not installed",
        )

    @property
    def is_available(self) -> bool:
        if self._available and not self._reachability_checked:
            self._available = self._ollama_reachable()
            self._reachability_checked = True
        return self._available

    async def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        if not self.is_available:
            raise RuntimeError(f"Unsupported or unavailable LLM backend: {self.backend}")

        logger.debug(
            "LLMService.generate called: model=%s max_tokens=%d prompt_length=%d",
            self.model,
            max_tokens,
            len(prompt),
        )
        options = {"num_predict": max_tokens, "temperature": 0}
        return await asyncio.to_thread(self._generate_ollama, prompt, options)

    def _generate_ollama(self, prompt: str, options: dict) -> str:
        try:
            client = ollama.Client(host=self.endpoint) if self.endpoint else ollama.Client()
            response = client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an oncology clinical decision support assistant. "
                            "Respond with ONLY a valid JSON object. No explanation, no markdown, no code fences. Start your response with { and end with }."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                options=options,
            )
        except Exception as exc:
            logger.error(
                "Ollama chat failed: model=%s endpoint=%s error=%s",
                self.model,
                self.endpoint or "(default)",
                exc,
            )
            raise RuntimeError(f"Ollama generation failed for model '{self.model}'") from exc
        content = response.get("message", {}).get("content", "")
        if isinstance(content, str):
            logger.debug(
                "Ollama generation succeeded: model=%s response_length=%d",
                self.model,
                len(content),
            )
            return content
        encoded = json.dumps(content)
        logger.debug(
            "Ollama generation succeeded (non-string content): model=%s response_length=%d",
            self.model,
            len(encoded),
        )
        return encoded

    def _ollama_reachable(self) -> bool:
        if not self.endpoint:
            logger.debug(
                "Ollama reachability check skipped: no endpoint configured, assuming reachable"
            )
            return True
        parsed = urlparse(self.endpoint)
        host = parsed.hostname
        port = parsed.port or 11434
        if not host:
            logger.warning("Failed to parse host from Ollama endpoint=%s", self.endpoint)
            return False
        logger.debug("Checking Ollama reachability: host=%s port=%d", host, port)
        try:
            with socket.create_connection((host, port), timeout=self.CONNECT_TIMEOUT_SECONDS):
                logger.info("Ollama is reachable: host=%s port=%d", host, port)
                return True
        except OSError as exc:
            logger.warning("Ollama is NOT reachable: host=%s port=%d error=%s", host, port, exc)
            return False
