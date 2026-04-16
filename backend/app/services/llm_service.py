import asyncio
import json
import socket
from urllib.parse import urlparse


try:
    import ollama
except ImportError:  # pragma: no cover
    ollama = None  # type: ignore[assignment]


class LLMService:
    CONNECT_TIMEOUT_SECONDS = 1.0

    def __init__(self, backend: str, model: str, endpoint: str | None = None) -> None:
        self.backend = backend.lower()
        self.model = model
        self.endpoint = endpoint
        self._available = self.backend == "ollama" and ollama is not None
        self._reachability_checked = False

    @property
    def is_available(self) -> bool:
        if self._available and not self._reachability_checked:
            self._available = self._ollama_reachable()
            self._reachability_checked = True
        return self._available

    async def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        if not self.is_available:
            raise RuntimeError(f"Unsupported or unavailable LLM backend: {self.backend}")

        options = {"num_predict": max_tokens, "temperature": 0}
        return await asyncio.to_thread(self._generate_ollama, prompt, options)

    def _generate_ollama(self, prompt: str, options: dict) -> str:
        kwargs: dict[str, object] = {}
        if self.endpoint:
            kwargs["host"] = self.endpoint

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an oncology clinical decision support assistant. "
                            "Return only valid JSON with the requested schema."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                options=options,
                **kwargs,
            )
        except Exception as exc:
            raise RuntimeError(f"Ollama generation failed for model '{self.model}'") from exc
        content = response.get("message", {}).get("content", "")
        if isinstance(content, str):
            return content
        return json.dumps(content)

    def _ollama_reachable(self) -> bool:
        if not self.endpoint:
            return True
        parsed = urlparse(self.endpoint)
        host = parsed.hostname
        port = parsed.port or 11434
        if not host:
            return False
        try:
            with socket.create_connection((host, port), timeout=self.CONNECT_TIMEOUT_SECONDS):
                return True
        except OSError:
            return False
