from __future__ import annotations

import json
import re
from typing import Any


def parse_json_payload_from_text(content: str) -> Any:
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
    if fenced:
        return json.loads(fenced.group(1))

    decoder = json.JSONDecoder()
    stripped = content.strip()
    try:
        return decoder.decode(stripped)
    except json.JSONDecodeError:
        pass

    for index, char in enumerate(content):
        if char not in "{[":
            continue
        try:
            payload, _ = decoder.raw_decode(content[index:])
        except json.JSONDecodeError:
            continue
        return payload

    raise json.JSONDecodeError("No JSON object or array found", content, 0)
