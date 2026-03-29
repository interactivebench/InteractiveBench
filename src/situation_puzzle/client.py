from __future__ import annotations
from openai import OpenAI
import time
import random
class LLMClient:

    def __init__(self, provider: str, openrouter_api_key: str = None, openrouter_base_url: str = None,
                 custom_api_key: str = None, custom_base_url: str = None):
        self.provider = provider

        self.client = None
        if provider == "openrouter":
            if OpenAI is None:
                raise RuntimeError("provider=openrouter requires 'openai' package. pip install openai")
            if not openrouter_api_key:
                raise RuntimeError("OPENROUTER_API_KEY is missing.")
            self.client = OpenAI(
                base_url=openrouter_base_url or "https://openrouter.ai/api/v1",
                api_key=openrouter_api_key,
            )
        elif provider == "custom":
            if OpenAI is None:
                raise RuntimeError("provider=custom requires 'openai' package. pip install openai")
            if not custom_api_key:
                raise RuntimeError("CUSTOM_API_KEY is missing for custom provider.")
            if not custom_base_url:
                raise RuntimeError("CUSTOM_BASE_URL is missing for custom provider.")
            self.client = OpenAI(
                base_url=custom_base_url,
                api_key=custom_api_key,
            )
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def chat(self, model: str, msg, temperature: float = 0.0, max_tokens: int = 1000) -> str:
        if self.provider in ["openrouter", "custom"]:
            # kimi models only support temperature=1.0
            if 'kimi' in model.lower():
                temperature = 1.0
            return self._chat_openrouter(model, msg, temperature=temperature, max_tokens=max_tokens)
        raise ValueError(f"Unknown provider: {self.provider}")


    def _chat_openrouter(self, model, messages, temperature=0.0, max_tokens=256):
        max_retries = 8
        base_sleep = 1.0  # seconds
        last_err = None
        for attempt in range(max_retries + 1):
            try:
                r = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                )
                choices = getattr(r, "choices", None)
                if not choices:
                    # 有些异常不会 raise，但会返回 choices=None/[]
                    last_err = RuntimeError("empty_choices")
                    raise last_err

                msg = getattr(choices[0], "message", None)
                content = getattr(msg, "content", None) if msg is not None else None
                content = (content or "").strip()

                if not content:
                    last_err = RuntimeError("empty_content")
                    raise last_err

                return content

            except Exception as e:
                last_err = e
                if attempt >= max_retries:
                    break

                # 最简单的 backoff：1s,2s,3s... + jitter
                sleep_s = base_sleep * (attempt + 1) + random.random()
                time.sleep(sleep_s)

        # 重试耗尽：这里才抛出
        raise RuntimeError(f"API call failed after retries: {last_err}")

