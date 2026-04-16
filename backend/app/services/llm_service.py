import asyncio
import json


try:
    import ollama
except Exception:  # pragma: no cover
    ollama = None  # type: ignore[assignment]


class LLMService:
    def __init__(self, backend: str, model: str, endpoint: str | None = None) -> None:
        self.backend = backend.lower()
        self.model = model
        self.endpoint = endpoint
        self._available = self.backend == "ollama" and ollama is not None

    @property
    def is_available(self) -> bool:
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
        content = response.get("message", {}).get("content", "")
        if isinstance(content, str):
            return content
        return json.dumps(content)
