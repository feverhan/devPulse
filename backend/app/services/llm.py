from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx


class LLMError(RuntimeError):
    pass


@dataclass
class LLMConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.3
    timeout: float = 300.0

    @property
    def normalized_base(self) -> str:
        base = (self.base_url or "").strip().rstrip("/")
        if not base:
            return ""
        if re.search(r"/v\d+$", base):
            return base
        if re.search(r"/(openai|api)$", base):
            return f"{base}/v1"
        return f"{base}/v1"

    @property
    def ready(self) -> bool:
        return bool(self.normalized_base and self.model)


async def chat(
    messages: list[dict[str, str]],
    config: LLMConfig,
    timeout: float | None = None,
) -> str:
    if not config.ready:
        raise LLMError("未配置大模型地址或模型名称")
    url = f"{config.normalized_base}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if (config.api_key or "").strip():
        headers["Authorization"] = f"Bearer {config.api_key.strip()}"
    payload: dict[str, object] = {
        "model": config.model,
        "messages": messages,
        "stream": False,
    }
    if config.temperature is not None:
        payload["temperature"] = config.temperature

    try:
        async with httpx.AsyncClient(timeout=timeout or config.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise LLMError("大模型请求超时") from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"无法连接大模型服务：{exc}") from exc

    if resp.status_code >= 400:
        detail = resp.text[:400]
        raise LLMError(f"大模型返回错误 HTTP {resp.status_code}：{detail}")

    try:
        data = resp.json()
    except ValueError as exc:
        raise LLMError("大模型返回内容不是合法 JSON") from exc

    choices = data.get("choices") or []
    if not choices:
        raise LLMError("大模型未返回任何结果")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
        content = "".join(parts)
    text = (content or "").strip()
    if not text:
        raise LLMError("大模型返回内容为空")
    return text


async def chat_stream(
    messages: list[dict[str, str]],
    config: LLMConfig,
    timeout: float | None = None,
) -> AsyncIterator[str]:
    """流式调用大模型，逐段返回正文。

    模型不支持流式时会抛出 LLMError，由调用方回退到一次性请求。
    """
    if not config.ready:
        raise LLMError("未配置大模型地址或模型名称")
    url = f"{config.normalized_base}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if (config.api_key or "").strip():
        headers["Authorization"] = f"Bearer {config.api_key.strip()}"
    payload: dict[str, object] = {
        "model": config.model,
        "messages": messages,
        "stream": True,
    }
    if config.temperature is not None:
        payload["temperature"] = config.temperature

    try:
        async with httpx.AsyncClient(timeout=timeout or config.timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code >= 400:
                    detail = (await resp.aread()).decode("utf-8", "ignore")[:400]
                    raise LLMError(f"大模型返回错误 HTTP {resp.status_code}：{detail}")
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if not data or data == "[DONE]":
                        if data == "[DONE]":
                            break
                        continue
                    try:
                        chunk = json.loads(data)
                    except ValueError:
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    piece = delta.get("content") or ""
                    if isinstance(piece, list):
                        piece = "".join(
                            str(item.get("text") or "") for item in piece if isinstance(item, dict)
                        )
                    if piece:
                        yield piece
    except httpx.TimeoutException as exc:
        raise LLMError("大模型请求超时") from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"无法连接大模型服务：{exc}") from exc


async def test_connection(config: LLMConfig) -> str:
    reply = await chat(
        [{"role": "user", "content": "只回复两个字：正常"}],
        config,
    )
    return reply