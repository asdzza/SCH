#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from typing import Any

import anthropic


def _extract_text_from_response(message: Any) -> tuple[str, str]:
    """Extract main text and thinking content from response.

    Returns (text_content, thinking_content).
    """
    text_parts = []
    thinking_parts = []
    for block in getattr(message, "content", []) or []:
        btype = getattr(block, "type", None)
        if btype == "text":
            text = getattr(block, "text", "")
            if text:
                text_parts.append(text)
        elif btype == "thinking":
            thinking = getattr(block, "thinking", "") or ""
            if thinking:
                thinking_parts.append(thinking)
    text = "\n".join(text_parts).strip()
    thinking = "\n".join(thinking_parts).strip()
    return text, thinking


def _extract_json_snippet(raw: str) -> str | None:
    raw = raw.strip()
    if not raw:
        return None

    # Direct JSON object/array.
    if raw.startswith("{") and raw.endswith("}"):
        return raw
    if raw.startswith("[") and raw.endswith("]"):
        return raw

    # Markdown fenced JSON.
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        if candidate:
            return candidate

    # Largest object snippet.
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start : end + 1]
    return None


def _read_json_file(path: str | None) -> dict:
    if not path:
        return {}
    p = os.path.expanduser(path)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Anthropic-compatible JSON LLM adapter")
    parser.add_argument("--model", default=os.getenv("MINIMAX_MODEL", "MiniMax-M2.7"))
    parser.add_argument("--max-tokens", type=int, default=int(os.getenv("LLM_MAX_TOKENS", "2500")))
    parser.add_argument("--temperature", type=float, default=float(os.getenv("LLM_TEMPERATURE", "0.2")))
    parser.add_argument("--api-key", default=None, help="API key. Highest priority if provided.")
    parser.add_argument("--base-url", default=None, help="Custom Anthropic-compatible endpoint.")
    parser.add_argument(
        "--secrets-file",
        default=os.getenv("LLM_SECRETS_FILE", None),
        help="Path to local JSON secrets file, e.g. ~/.llm_secrets.json",
    )
    parser.add_argument(
        "--system",
        default=os.getenv(
            "LLM_SYSTEM_PROMPT",
            "You are a JSON-only optimizer assistant. Always return valid JSON and no markdown.",
        ),
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=int(os.getenv("LLM_MAX_RETRIES", "3")),
        help="Maximum number of retries on API overload or transient errors.",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=float(os.getenv("LLM_RETRY_DELAY", "2.0")),
        help="Base delay in seconds between retries. Actual delay uses exponential backoff with jitter.",
    )
    args = parser.parse_args()

    prompt = sys.stdin.read().strip()
    if not prompt:
        print("{}")
        return

    secrets = _read_json_file(args.secrets_file)

    api_key = (
        args.api_key
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("MINIMAX_API_KEY")
        or secrets.get("ANTHROPIC_API_KEY")
        or secrets.get("MINIMAX_API_KEY")
    )
    if not api_key:
        sys.stderr.write(
            "API key not found. Set via --api-key, env ANTHROPIC_API_KEY/MINIMAX_API_KEY, "
            "or secrets file key ANTHROPIC_API_KEY/MINIMAX_API_KEY.\n"
        )
        sys.exit(2)

    base_url = (
        args.base_url
        or os.getenv("ANTHROPIC_BASE_URL")
        or os.getenv("MINIMAX_BASE_URL")
        or secrets.get("ANTHROPIC_BASE_URL")
        or secrets.get("MINIMAX_BASE_URL")
    )
    if base_url:
        client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
    else:
        client = anthropic.Anthropic(api_key=api_key)

    # Retry loop for transient errors (overload, rate limit, server errors)
    last_error: str = ""
    for attempt in range(args.max_retries):
        try:
            message = client.messages.create(
                model=args.model,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                system=args.system,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt,
                            }
                        ],
                    }
                ],
            )
        except Exception as e:
            last_error = str(e)
            # Check if error is retryable (overload 529, rate limit 429, server 5xx)
            retryable = False
            err_lower = last_error.lower()
            if "529" in last_error or "overloaded_error" in err_lower:
                retryable = True
                reason = "API overload"
            elif "429" in last_error or "rate_limit" in err_lower:
                retryable = True
                reason = "rate limit"
            elif any(code in last_error for code in ["500", "502", "503", "504"]):
                retryable = True
                reason = "server error"
            elif attempt < args.max_retries - 1:
                # Exponential backoff with jitter: delay * 2^(attempt) ± random
                base_delay = args.retry_delay * (2 ** attempt)
                jitter = base_delay * 0.5 * random.random()
                delay = base_delay + jitter
                sys.stderr.write(
                    f"[RETRY] {reason} on attempt {attempt + 1}/{args.max_retries}. "
                    f"Retrying in {delay:.1f}s... Error: {last_error[:200]}\n"
                )
                sys.stderr.flush()
                time.sleep(delay)
                continue
            else:
                sys.stderr.write(f"API call failed after {args.max_retries} attempts: {last_error}\n")
                sys.exit(2)
        else:
            break  # Success

    raw_text, thinking = _extract_text_from_response(message)

    # Log thinking content to stderr for debugging capture
    if thinking:
        sys.stderr.write(f"[MODEL THINKING]\n{thinking}\n[/MODEL THINKING]\n")
        sys.stderr.flush()

    snippet = _extract_json_snippet(raw_text)
    if not snippet:
        sys.stderr.write(f"Model output does not contain JSON. Raw: {raw_text[:500]}\n")
        sys.exit(2)

    try:
        obj = json.loads(snippet)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"Invalid JSON from model: {e}\n")
        sys.exit(2)

    print(json.dumps(obj, ensure_ascii=False))


if __name__ == "__main__":
    main()
