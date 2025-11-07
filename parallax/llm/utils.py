"""Utility functions for LLM providers."""
from __future__ import annotations

import json
import re
from typing import Any, Dict


def extract_json_from_content(content: str) -> Dict[str, Any]:
    """
    Extract JSON from LLM response content.
    
    Handles JSON wrapped in markdown code blocks or plain JSON text.
    Raises ValueError if no valid JSON can be extracted.
    
    Args:
        content: Raw content string from LLM response
        
    Returns:
        Parsed JSON dictionary
        
    Raises:
        ValueError: If no valid JSON can be extracted
        json.JSONDecodeError: If JSON parsing fails
    """
    if not content or not isinstance(content, str):
        raise ValueError("Content must be a non-empty string")
    
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if json_match:
        content = json_match.group(1).strip()
    
    # Try to find JSON object boundaries
    start = content.find("{")
    end = content.rfind("}") + 1
    
    if start >= 0 and end > start:
        content = content[start:end]
    elif start < 0:
        # Try to find array boundaries
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            content = content[start:end]
        else:
            raise ValueError("No JSON object or array found in content")
    
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}") from e

