import logging
import os
import time

import groq

logger = logging.getLogger(__name__)


def call_ai(payload: dict) -> str:
    prompt = payload.get("prompt", "Tell me something interesting.")
    model = payload.get("model", "llama3-8b-8192")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY not set — using mock response for %s", model)
        time.sleep(2)
        return f"Mock response for: {prompt}"

    client = groq.Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return completion.choices[0].message.content
