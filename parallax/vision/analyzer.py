"""Vision-based analysis for completion detection and state significance."""
from __future__ import annotations

import base64
from typing import Any, Dict, Optional

from parallax.core.logging import get_logger

log = get_logger("vision")


class VisionAnalyzer:
    """Vision-based analysis using vision LLMs."""
    
    def __init__(self, provider: str = "openai"):
        self.provider = provider
        self._client = None
    
    def _get_client(self):
        """Get vision LLM client."""
        if self._client is not None:
            return self._client
        
        if self.provider == "openai":
            try:
                import os
                from openai import AsyncOpenAI
                # Check if API key is available
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    return None
                self._client = AsyncOpenAI(api_key=api_key)
                return self._client
            except (ImportError, Exception) as e:
                log.warning("openai_not_available", message=f"OpenAI not available: {e}")
                return None
        
        elif self.provider == "anthropic":
            try:
                import anthropic
                import os
                # Check if API key is available
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    return None
                self._client = anthropic.Anthropic(api_key=api_key)
                return self._client
            except (ImportError, Exception) as e:
                log.warning("anthropic_not_available", message=f"Anthropic not available: {e}")
                return None
        
        return None
    
    async def analyze_completion(
        self,
        screenshot_bytes: bytes,
        task_context: str,
        workflow_states: list,
    ) -> Dict[str, Any]:
        """
        Analyze screenshot to determine if workflow is complete.
        
        Returns:
            {
                'is_complete': bool,
                'confidence': float,
                'reasoning': str,
                'indicators': list[str]
            }
        """
        # Try to get client, but fall back to heuristic if unavailable
        try:
            client = self._get_client()
        except Exception:
            client = None
        
        if not client:
            # Fallback to heuristic-based detection
            return await self._heuristic_completion(screenshot_bytes, task_context, workflow_states)
        
        try:
            # Convert screenshot to base64
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
            
            # Prepare prompt
            prompt = f"""Analyze this screenshot to determine if the workflow task is complete.

Task: {task_context}

Previous states captured: {len(workflow_states)}

Look for completion indicators:
1. Success messages (e.g., "Success", "Created", "Saved", "Done")
2. Confirmation dialogs
3. Success toasts/notifications
4. Final state indicators (e.g., item appears in list, modal closes)
5. Error messages (indicates failure, not completion)

Return JSON format:
{{
    "is_complete": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "explanation",
    "indicators": ["list", "of", "indicators", "found"]
}}"""
            
            if self.provider == "openai":
                response = await self._analyze_openai(client, screenshot_b64, prompt)
            elif self.provider == "anthropic":
                response = await self._analyze_anthropic(client, screenshot_b64, prompt)
            else:
                return await self._heuristic_completion(screenshot_bytes, task_context, workflow_states)
            
            return response
        
        except Exception as e:
            log.warning("vision_analysis_failed", error=str(e), provider=self.provider)
            return await self._heuristic_completion(screenshot_bytes, task_context, workflow_states)
    
    async def _analyze_openai(self, client, screenshot_b64: str, prompt: str) -> Dict[str, Any]:
        """Analyze using OpenAI vision model (async)."""
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Cost-effective vision model. GPT-5 requires temperature=1 which is less deterministic.
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_b64}"
                            }
                        },
                        {"type": "text", "text": prompt}
                    ]
                }
            ],
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        import json
        content = response.choices[0].message.content
        result = json.loads(content)
        return result
    
    async def _analyze_anthropic(self, client, screenshot_b64: str, prompt: str) -> Dict[str, Any]:
        """Analyze using Anthropic vision model."""
        # Anthropic client is sync, but we can call it in async context
        import asyncio
        
        def _call_anthropic():
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_b64
                            }
                        },
                        {"type": "text", "text": prompt}
                    ]
                }]
            )
            return message
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        message = await loop.run_in_executor(None, _call_anthropic)
        
        import json
        content = message.content[0].text
        # Extract JSON from markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        result = json.loads(content)
        return result
    
    async def _heuristic_completion(
        self,
        screenshot_bytes: bytes,
        task_context: str,
        workflow_states: list,
    ) -> Dict[str, Any]:
        """Heuristic-based completion detection (fallback)."""
        # Look for success indicators in screenshot using OCR/text detection
        # For MVP, use simple heuristics
        
        # If we have multiple states and last one shows stability, might be complete
        is_complete = len(workflow_states) >= 3  # Simple heuristic
        
        return {
            "is_complete": is_complete,
            "confidence": 0.5,
            "reasoning": "Heuristic-based: Multiple states captured, assuming potential completion",
            "indicators": ["multiple_states"],
            "method": "heuristic",
        }
    
    async def analyze_significance(
        self,
        screenshot_bytes: bytes,
        task_context: str,
        current_state: Dict[str, Any],
        previous_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze screenshot to determine state significance.
        
        Returns:
            {
                'significance': 'critical' | 'supporting' | 'optional',
                'confidence': float,
                'reasoning': str,
                'key_elements': list[str]
            }
        """
        # Try to get client, but fall back to heuristic if unavailable
        try:
            client = self._get_client()
        except Exception:
            client = None
        
        if not client:
            # Fallback to heuristic-based detection
            return await self._heuristic_significance(screenshot_bytes, current_state, previous_state)
        
        try:
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
            
            prompt = f"""Analyze this screenshot to determine the significance of this UI state.

Task: {task_context}

Current state:
- URL: {current_state.get('url', 'N/A')}
- Has modal: {current_state.get('has_modal', False)}
- Has toast: {current_state.get('has_toast', False)}
- Form valid: {current_state.get('form_validity', 'N/A')}

Categorize significance:
- **Critical**: Major workflow milestones (e.g., modal opens, form submitted, success state)
- **Supporting**: Important intermediate states (e.g., form filled, navigation occurred)
- **Optional**: Minor transitions or loading states

Return JSON format:
{{
    "significance": "critical" | "supporting" | "optional",
    "confidence": 0.0-1.0,
    "reasoning": "explanation",
    "key_elements": ["list", "of", "key", "elements"]
}}"""
            
            if self.provider == "openai":
                response = await self._analyze_openai(client, screenshot_b64, prompt)
            elif self.provider == "anthropic":
                response = await self._analyze_anthropic(client, screenshot_b64, prompt)
            else:
                return await self._heuristic_significance(screenshot_bytes, current_state, previous_state)
            
            return response
        
        except Exception as e:
            log.warning("vision_significance_failed", error=str(e))
            return await self._heuristic_significance(screenshot_bytes, current_state, previous_state)
    
    async def _heuristic_significance(
        self,
        screenshot_bytes: bytes,
        current_state: Dict[str, Any],
        previous_state: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Heuristic-based significance detection (fallback)."""
        # Determine significance based on state metadata
        has_modal = current_state.get("has_modal", False)
        has_toast = current_state.get("has_toast", False)
        form_validity = current_state.get("form_validity")
        
        if has_modal or has_toast:
            significance = "critical"
            confidence = 0.8
            reasoning = "Modal or toast detected - critical workflow state"
        elif form_validity is True:
            significance = "supporting"
            confidence = 0.6
            reasoning = "Form valid - supporting state"
        else:
            significance = "optional"
            confidence = 0.5
            reasoning = "Standard navigation state"
        
        return {
            "significance": significance,
            "confidence": confidence,
            "reasoning": reasoning,
            "key_elements": ["heuristic_based"],
            "method": "heuristic",
        }
    
    async def find_element_vision(
        self,
        screenshot_bytes: bytes,
        description: str,
        action_type: str = "click",
    ) -> Dict[str, Any]:
        """
        Find element using vision analysis (fallback when selectors fail).
        
        Returns:
            {
                'element_found': bool,
                'x': int,
                'y': int,
                'confidence': float,
                'reasoning': str
            }
        """
        # Try to get client, but fall back if unavailable
        try:
            client = self._get_client()
        except Exception:
            client = None
        
        if not client:
            # No vision fallback available
            return {
                "element_found": False,
                "x": 0,
                "y": 0,
                "confidence": 0.0,
                "reasoning": "Vision client not available",
            }
        
        try:
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
            
            prompt = f"""Analyze this screenshot and locate the element described below.

Element description: {description}
Action to perform: {action_type}

Instructions:
1. Identify the element that best matches the description
2. Provide the x,y coordinates of the element's center (relative to viewport)
3. Explain your reasoning
4. Rate your confidence (0-1)

Return JSON format:
{{
    "element_found": true/false,
    "x": 500,
    "y": 300,
    "confidence": 0.95,
    "reasoning": "Located blue 'New Project' button in top-right",
    "alternative_elements": []
}}"""
            
            if self.provider == "openai":
                response = await self._analyze_openai(client, screenshot_b64, prompt)
            elif self.provider == "anthropic":
                response = await self._analyze_anthropic(client, screenshot_b64, prompt)
            else:
                return {
                    "element_found": False,
                    "x": 0,
                    "y": 0,
                    "confidence": 0.0,
                    "reasoning": "Vision provider not available",
                }
            
            return response
        
        except Exception as e:
            log.warning("vision_element_location_failed", error=str(e))
            return {
                "element_found": False,
                "x": 0,
                "y": 0,
                "confidence": 0.0,
                "reasoning": f"Vision analysis failed: {str(e)}",
            }

