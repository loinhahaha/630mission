from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict

import requests

from agent_config import load_agent_config


def _config():
    return load_agent_config()


def _auth_headers() -> Dict[str, str]:
    cfg = _config()
    ts = str(int(time.time() * 1000))
    sign = hashlib.md5(f"{cfg.auth_key}{cfg.auth_secret}{ts}".encode("utf-8")).hexdigest()
    return {
        "Content-Type": "application/json",
        "authKey": cfg.auth_key,
        "timestamp": ts,
        "sign": sign,
    }


def _fix_mojibake(s: str) -> str:
    try:
        return s.encode("latin1").decode("utf-8")
    except Exception:
        return s


def chat_sync_clean(
    text: str,
    chat_id: str | None = None,
    debug: bool = False,
    timeout: int = 60,
) -> tuple[str | None, str | None, str | None, dict[str, Any]]:
    """Call the non-stream completion API and normalize error details."""
    cfg = _config()
    url = f"{cfg.base_url}/openapi/v2/chat/completions"
    payload = {"agentId": cfg.agent_id, "chatId": chat_id, "userChatInput": text, "debug": debug}

    try:
        r = requests.post(url, headers=_auth_headers(), json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except requests.HTTPError as e:
        detail = {
            "type": "http_error",
            "status_code": getattr(e.response, "status_code", None),
            "text": getattr(e.response, "text", "")[:1000],
        }
        return None, None, None, detail
    except Exception as e:
        detail = {"type": "exception", "error": str(e)}
        return None, None, None, detail

    answer = None
    choices = data.get("choices") or []
    if choices and isinstance(choices[0], dict):
        content = choices[0].get("content")
        if isinstance(content, str) and content.strip():
            answer = content.strip()

    if answer:
        chat_id_out = data.get("chatId") or choices[0].get("chatId")
        conv_id_out = data.get("conversationId") or choices[0].get("conversationId")
        return answer, chat_id_out, conv_id_out, data

    detail = {
        "type": "sync_no_answer",
        "requestId": data.get("requestId"),
        "chatId": data.get("chatId"),
        "conversationId": data.get("conversationId"),
        "success": data.get("success"),
        "msg": data.get("msg"),
        "raw": data,
    }
    return None, data.get("chatId"), data.get("conversationId"), detail


def chat_stream_clean(
    text: str,
    chat_id: str | None = None,
    debug: bool = False,
    timeout: int = 120,
) -> tuple[str | None, str | None, str | None, dict[str, Any]]:
    cfg = _config()
    url = f"{cfg.base_url}/openapi/v2/chat/stream"
    payload = {"agentId": cfg.agent_id, "chatId": chat_id, "userChatInput": text, "debug": debug}

    parts: list[str] = []
    last_chat_id = None
    last_conv_id = None
    error_msg = None
    first_error_event = None

    try:
        with requests.post(url, headers=_auth_headers(), json=payload, stream=True, timeout=timeout) as r:
            r.raise_for_status()

            for raw in r.iter_lines(decode_unicode=False):
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace")
                if not line.startswith("data:"):
                    continue

                evt_str = line[len("data:"):].strip()
                try:
                    evt = json.loads(evt_str)
                except json.JSONDecodeError:
                    continue

                last_chat_id = evt.get("chatId", last_chat_id)
                last_conv_id = evt.get("conversationId", last_conv_id)

                status = evt.get("status")
                chunk = evt.get("content") or ""

                if status == -1:
                    error_msg = chunk or "stream error"
                    if first_error_event is None:
                        first_error_event = evt

                if status == 1 and isinstance(chunk, str) and chunk:
                    parts.append(_fix_mojibake(chunk))

                if evt.get("finish") is True:
                    break

    except requests.HTTPError as e:
        detail = {
            "type": "http_error",
            "status_code": getattr(e.response, "status_code", None),
            "text": getattr(e.response, "text", "")[:1000],
        }
        return None, None, None, detail
    except Exception as e:
        detail = {"type": "exception", "error": str(e)}
        return None, None, None, detail

    answer = "".join(parts).strip()
    if error_msg or not answer:
        detail = {
            "type": "stream_error" if error_msg else "stream_empty",
            "error_message": error_msg,
            "chatId": last_chat_id,
            "conversationId": last_conv_id,
            "first_error_event": first_error_event,
        }
        return None, last_chat_id, last_conv_id, detail

    return answer, last_chat_id, last_conv_id, {"type": "ok"}


def call_agent(chunk_text: str) -> str:
    cfg = _config()
    if not cfg.auth_key or not cfg.auth_secret or not cfg.agent_id:
        return json.dumps(
            {
                "revised_text": chunk_text,
                "notes": [{"type": "agent", "message": "未配置智能体鉴权参数，已跳过大模型润色。"}],
            },
            ensure_ascii=False,
        )

    answer, _chat_id, _conv_id, meta = chat_sync_clean(chunk_text, debug=False)
    if answer:
        return json.dumps({"revised_text": answer, "notes": []}, ensure_ascii=False)
    print("agent meta:", meta)
    return json.dumps(
        {
            "revised_text": chunk_text,
            "notes": [{"type": "agent", "message": f"大模型调用失败：{meta}"}],
        },
        ensure_ascii=False,
    )


def call_agent_and_normalize(chunk_text: str) -> Dict[str, Any]:
    raw = (call_agent(chunk_text) or "").strip()

    if raw.startswith("{") and raw.endswith("}"):
        try:
            obj = json.loads(raw)
            revised = str(obj.get("revised_text", "")).strip()
            notes = obj.get("notes", [])
            return {"revised_text": revised or chunk_text, "notes": notes}
        except Exception:
            pass

    return {
        "revised_text": raw or chunk_text,
        "notes": [{"type": "agent", "message": "输出非 JSON，已按纯文本降级处理。"}],
    }
