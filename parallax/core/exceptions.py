"""Custom exception hierarchy for Parallax."""
from __future__ import annotations

from typing import Any, Dict, Optional


class ParallaxError(Exception):
    """Base exception for all Parallax errors."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.context = context or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({ctx_str})"
        return self.message


class LLMError(ParallaxError):
    """Base exception for LLM-related errors."""
    
    def __init__(
        self,
        message: str,
        provider: str,
        retryable: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.provider = provider
        self.retryable = retryable
        super().__init__(message, context)
        self.context["provider"] = provider
        self.context["retryable"] = retryable


class LLMTimeoutError(LLMError):
    """LLM call timed out."""
    
    def __init__(
        self,
        provider: str,
        timeout: float,
        context: Optional[Dict[str, Any]] = None,
    ):
        message = f"LLM call to {provider} timed out after {timeout}s"
        super().__init__(message, provider, retryable=True, context=context)
        self.timeout = timeout
        self.context["timeout"] = timeout


class LLMRateLimitError(LLMError):
    """Rate limit exceeded for LLM provider."""
    
    def __init__(
        self,
        provider: str,
        retry_after: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        message = f"Rate limit exceeded for {provider}"
        if retry_after:
            message += f", retry after {retry_after}s"
        super().__init__(message, provider, retryable=True, context=context)
        self.retry_after = retry_after
        if retry_after:
            self.context["retry_after"] = retry_after


class LLMAPIError(LLMError):
    """LLM API returned an error."""
    
    def __init__(
        self,
        provider: str,
        status_code: Optional[int] = None,
        error_message: Optional[str] = None,
        retryable: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ):
        message = f"LLM API error for {provider}"
        if error_message:
            message += f": {error_message}"
        super().__init__(message, provider, retryable=retryable, context=context)
        self.status_code = status_code
        self.error_message = error_message
        if status_code:
            self.context["status_code"] = status_code
        if error_message:
            self.context["error_message"] = error_message


class NavigationError(ParallaxError):
    """Error during navigation/execution."""
    
    def __init__(
        self,
        message: str,
        step_action: Optional[str] = None,
        step_target: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, context)
        self.step_action = step_action
        self.step_target = step_target
        if step_action:
            self.context["step_action"] = step_action
        if step_target:
            self.context["step_target"] = step_target


class ElementNotFoundError(NavigationError):
    """Element not found during navigation."""
    
    def __init__(
        self,
        selector: Optional[str] = None,
        role: Optional[str] = None,
        name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        message = "Element not found"
        if selector:
            message += f" (selector: {selector})"
        elif role and name:
            message += f" (role: {role}, name: {name})"
        super().__init__(message, step_action="locate", context=context)
        self.selector = selector
        self.role = role
        self.name = name
        if selector:
            self.context["selector"] = selector
        if role:
            self.context["role"] = role
        if name:
            self.context["name"] = name


class ConfigurationError(ParallaxError):
    """Configuration validation error."""
    pass


class ValidationError(ParallaxError):
    """Constitution validation error."""
    
    def __init__(
        self,
        message: str,
        agent: Optional[str] = None,
        rule_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, context)
        self.agent = agent
        self.rule_name = rule_name
        if agent:
            self.context["agent"] = agent
        if rule_name:
            self.context["rule_name"] = rule_name

