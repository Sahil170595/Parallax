"""Agent Constitution System - Quality gates and validation for each agent."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from parallax.core.logging import get_logger

log = get_logger("constitution")


def _json_safe(value: Any) -> Any:
    """Best-effort conversion to JSON-serialisable structures."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return repr(value)


class ValidationLevel(Enum):
    """Validation severity levels."""
    CRITICAL = "critical"  # Must pass or workflow fails
    WARNING = "warning"  # Should pass, but can continue
    INFO = "info"  # Best practice, informational only


class ValidationResult(Enum):
    """Validation outcome."""
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


@dataclass
class ValidationRule:
    """A single validation rule."""
    name: str
    description: str
    level: ValidationLevel
    validator: callable  # Function that returns (passed: bool, reason: str, details: dict)
    enabled: bool = True


@dataclass
class ValidationFailure:
    """Record of a validation failure."""
    rule_name: str
    rule_description: str
    level: ValidationLevel
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent: str = ""
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConstitutionReport:
    """Complete validation report for an agent."""
    agent: str
    passed: bool
    failures: List[ValidationFailure] = field(default_factory=list)
    warnings: List[ValidationFailure] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "agent": self.agent,
            "passed": self.passed,
            "failures": [
                {
                    "rule_name": f.rule_name,
                    "rule_description": f.rule_description,
                    "level": f.level.value,
                    "reason": f.reason,
                    "details": _json_safe(f.details),
                    "timestamp": f.timestamp.isoformat(),
                    "context": _json_safe(f.context),
                }
                for f in self.failures
            ],
            "warnings": [
                {
                    "rule_name": w.rule_name,
                    "rule_description": w.rule_description,
                    "level": w.level.value,
                    "reason": w.reason,
                    "details": _json_safe(w.details),
                    "timestamp": w.timestamp.isoformat(),
                    "context": _json_safe(w.context),
                }
                for w in self.warnings
            ],
            "timestamp": self.timestamp.isoformat(),
            "context": _json_safe(self.context),
        }


class AgentConstitution:
    """Constitution validator for an agent with quality gates."""
    
    def __init__(self, agent_name: str, rules: List[ValidationRule]):
        self.agent_name = agent_name
        self.rules = [r for r in rules if r.enabled]
        self.failures: List[ValidationFailure] = []
        self.warnings: List[ValidationFailure] = []
    
    def validate(self, input_data: Any, output_data: Any, context: Dict[str, Any] = None) -> ConstitutionReport:
        """
        Validate agent output against constitution rules.
        
        Args:
            input_data: Input to the agent
            output_data: Output from the agent
            context: Additional context (e.g., page state, config)
        
        Returns:
            ConstitutionReport with validation results
        """
        context = context or {}
        self.failures = []
        self.warnings = []
        
        for rule in self.rules:
            try:
                passed, reason, details = rule.validator(input_data, output_data, context)
                details["rule_name"] = rule.name
                details["rule_description"] = rule.description
                
                if not passed:
                    failure = ValidationFailure(
                        rule_name=rule.name,
                        rule_description=rule.description,
                        level=rule.level,
                        reason=reason,
                        details=details,
                        agent=self.agent_name,
                        context=context,
                    )
                    
                    if rule.level == ValidationLevel.CRITICAL:
                        self.failures.append(failure)
                    elif rule.level == ValidationLevel.WARNING:
                        self.warnings.append(failure)
                    else:
                        # INFO level - log but don't track
                        log.info("constitution_info", rule=rule.name, reason=reason)
            
            except Exception as e:
                log.error("constitution_validator_error", rule=rule.name, error=str(e))
                # Treat validator exceptions as warnings
                failure = ValidationFailure(
                    rule_name=rule.name,
                    rule_description=rule.description,
                    level=ValidationLevel.WARNING,
                    reason=f"Validator error: {str(e)}",
                    details={"error": str(e)},
                    agent=self.agent_name,
                    context=context,
                )
                self.warnings.append(failure)
        
        # Agent passes if no critical failures
        passed = len(self.failures) == 0
        
        report = ConstitutionReport(
            agent=self.agent_name,
            passed=passed,
            failures=self.failures,
            warnings=self.warnings,
            context=context,
        )
        
        if not passed:
            log.warning(
                "constitution_failed",
                agent=self.agent_name,
                failures=len(self.failures),
                warnings=len(self.warnings),
            )
        
        return report
    
    def must_pass(self, input_data: Any, output_data: Any, context: Dict[str, Any] = None) -> bool:
        """
        Validate and raise exception if critical failures exist.
        
        Returns:
            True if passed, raises ConstitutionViolation if failed
        """
        report = self.validate(input_data, output_data, context)
        
        if not report.passed:
            failure_messages = [
                f"{f.rule_name}: {f.reason}" for f in report.failures
            ]
            raise ConstitutionViolation(
                agent=self.agent_name,
                failures=report.failures,
                message=f"Agent {self.agent_name} failed constitution validation: {', '.join(failure_messages)}",
            )
        
        return True


class ConstitutionViolation(Exception):
    """Raised when an agent fails critical constitution validation."""
    
    def __init__(self, agent: str, failures: List[ValidationFailure], message: str):
        self.agent = agent
        self.failures = failures
        super().__init__(message)


class FailureStore:
    """Store validation failures for later analysis and improvement."""
    
    def __init__(self, store_path: Path | str):
        self.store_path = Path(store_path) if isinstance(store_path, str) else store_path
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.failures_file = self.store_path / "constitution_failures.jsonl"
    
    def save_failure(self, report: ConstitutionReport) -> None:
        """Save validation failures to JSONL for later analysis."""
        if not report.failures and not report.warnings:
            return
        
        with self.failures_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(report.to_dict(), ensure_ascii=False) + "\n")
        
        log.info(
            "constitution_failure_saved",
            agent=report.agent,
            failures=len(report.failures),
            warnings=len(report.warnings),
            path=str(self.failures_file),
        )
    
    def get_failures(self, agent: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve validation failures for analysis."""
        if not self.failures_file.exists():
            return []
        
        failures = []
        with self.failures_file.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if agent is None or data.get("agent") == agent:
                        failures.append(data)
                except json.JSONDecodeError:
                    continue
        
        return failures[-limit:] if limit else failures
    
    def get_failure_statistics(self) -> Dict[str, Any]:
        """Get statistics about failures for improvement."""
        failures = self.get_failures(limit=None)
        
        if not failures:
            return {
                "total_failures": 0,
                "by_agent": {},
                "by_rule": {},
                "by_level": {},
            }
        
        stats = {
            "total_failures": len(failures),
            "by_agent": {},
            "by_rule": {},
            "by_level": {},
        }
        
        for failure in failures:
            agent = failure.get("agent", "unknown")
            stats["by_agent"][agent] = stats["by_agent"].get(agent, 0) + 1
            
            for f in failure.get("failures", []):
                rule = f.get("rule_name", "unknown")
                level = f.get("level", "unknown")
                stats["by_rule"][rule] = stats["by_rule"].get(rule, 0) + 1
                stats["by_level"][level] = stats["by_level"].get(level, 0) + 1
        
        return stats

