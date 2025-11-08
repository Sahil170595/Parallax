"""Configuration models and validation using Pydantic."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class PlannerConfig(BaseModel):
    """LLM planner configuration."""
    max_tokens: int = Field(default=1200, ge=1, le=10000)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    timeout_ms: int = Field(default=10000, ge=1000, le=300000)


class NavigationConfig(BaseModel):
    """Navigation settings configuration."""
    action_budget: int = Field(default=30, ge=1, le=1000)
    default_wait_ms: int = Field(default=1000, ge=0, le=10000)
    self_heal_attempts: int = Field(default=1, ge=0, le=10)
    scroll_margin_px: int = Field(default=64, ge=0, le=500)


class ViewportConfig(BaseModel):
    """Viewport dimensions configuration."""
    width: int = Field(..., ge=100, le=7680)
    height: int = Field(..., ge=100, le=4320)


class RedactConfig(BaseModel):
    """Redaction settings configuration."""
    enabled: bool = Field(default=True)
    selectors: List[str] = Field(default_factory=list)


class CaptureConfig(BaseModel):
    """Screenshot capture configuration."""
    multi_viewport: bool = Field(default=True)
    desktop_viewport: ViewportConfig = Field(
        default_factory=lambda: ViewportConfig(width=1366, height=832)
    )
    tablet_viewport: ViewportConfig = Field(
        default_factory=lambda: ViewportConfig(width=834, height=1112)
    )
    mobile_viewport: ViewportConfig = Field(
        default_factory=lambda: ViewportConfig(width=390, height=844)
    )
    crop_focus_padding_px: int = Field(default=16, ge=0, le=100)
    redact: RedactConfig = Field(default_factory=RedactConfig)


class ObserverConfig(BaseModel):
    """Observer agent configuration."""
    role_diff_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    loader_timeout_ms: int = Field(default=8000, ge=1000, le=60000)
    detection_poll_ms: int = Field(default=150, ge=50, le=1000)


class OutputConfig(BaseModel):
    """Output directory configuration."""
    base_dir: str = Field(default="datasets")


class CompletionConfig(BaseModel):
    """Completion validation configuration."""
    min_targets: int = Field(default=1, ge=1, le=10)


class MetricsConfig(BaseModel):
    """Metrics configuration."""
    prometheus_port: int = Field(default=9109, ge=1024, le=65535)


class PlaywrightConfig(BaseModel):
    """Playwright browser configuration."""
    headless: bool = Field(default=True)
    project: Literal["chromium", "firefox", "webkit"] = Field(default="chromium")
    channel: Optional[str] = Field(default=None, description="Browser channel (e.g., 'chrome' to use installed Chrome instead of Chromium)")
    user_data_dir: Optional[str] = Field(default=None, description="Path to user data directory for persistent browser context (saves cookies/sessions for authentication)")


class VisionConfig(BaseModel):
    """Vision features configuration."""
    enabled: bool = Field(default=False)
    provider: Literal["openai", "anthropic"] = Field(default="openai")
    
    @field_validator('provider')
    @classmethod
    def validate_provider_has_key(cls, v):
        """Validate that API key exists for selected provider."""
        # Note: Validation will be done at runtime when vision is actually used
        # Pydantic v2 field_validator doesn't easily access other fields
        return v


class ParallaxConfig(BaseModel):
    """Main configuration model for Parallax."""
    provider: Literal["openai", "anthropic", "local", "auto"] = Field(default="auto")
    planner: PlannerConfig = Field(default_factory=PlannerConfig)
    navigation: NavigationConfig = Field(default_factory=NavigationConfig)
    capture: CaptureConfig = Field(default_factory=CaptureConfig)
    observer: ObserverConfig = Field(default_factory=ObserverConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    completion: CompletionConfig = Field(default_factory=CompletionConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    playwright: PlaywrightConfig = Field(default_factory=PlaywrightConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    
    @field_validator('provider')
    @classmethod
    def validate_provider_has_key(cls, v):
        """Validate that API key exists for selected provider."""
        if v == "openai" and not os.getenv("OPENAI_API_KEY"):
            # For 'auto', we'll check later
            if v != "auto":
                raise ValueError("OPENAI_API_KEY required for 'openai' provider")
        if v == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY required for 'anthropic' provider")
        return v
    
    @classmethod
    def from_yaml(cls, config_path: Path) -> ParallaxConfig:
        """Load configuration from YAML file."""
        import yaml
        
        if not config_path.exists():
            return cls()  # Return defaults
        
        try:
            with config_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            # If loading fails, return defaults instead of crashing
            import warnings
            warnings.warn(f"Failed to load config file {config_path}: {e}. Using defaults.")
            return cls()
        
        if not data:
            return cls()  # Empty file, return defaults
        
        # Handle legacy config format where provider might be at root
        if "provider" in data and "llm" not in data:
            data["provider"] = data.pop("provider")
        
        # Fix common config issues - flatten nested lists in selectors
        if "capture" in data and "redact" in data.get("capture", {}):
            redact_data = data["capture"]["redact"]
            if "selectors" in redact_data and isinstance(redact_data["selectors"], list):
                # Flatten any nested lists in selectors (YAML sometimes parses [attr] as a list)
                selectors = []
                for sel in redact_data["selectors"]:
                    if isinstance(sel, list):
                        # If it's a list, join it back to a string
                        selectors.append("".join(str(s) for s in sel))
                    elif isinstance(sel, str):
                        selectors.append(sel)
                redact_data["selectors"] = selectors
        
        try:
            return cls(**data)
        except Exception as e:
            # If validation fails, try to use defaults with what we can
            import warnings
            warnings.warn(f"Config validation failed: {e}. Using defaults with partial config.")
            try:
                # Try to create config with just the valid parts
                return cls(**{k: v for k, v in data.items() if k in cls.__fields__})
            except Exception:
                # If that fails too, just return defaults
                return cls()
    
    def to_dict(self) -> Dict:
        """Convert config to dictionary."""
        # Support both Pydantic v1 and v2
        if hasattr(self, 'model_dump'):
            return self.model_dump(exclude_none=True)
        return self.dict(exclude_none=True)

