from __future__ import annotations

from typing import Optional

from parallax.agents.constitutions import INTERPRETER_CONSTITUTION
from parallax.agents.strategy_generator import StrategyGenerator
from parallax.core.constitution import FailureStore
from parallax.core.logging import get_logger
from parallax.core.metrics import llm_tokens
from parallax.core.schemas import ExecutionPlan, PlanStep


log = get_logger("interpreter")


class Interpreter:
    """
    Agent A1: Interpreter - Converts natural language tasks into execution plans.
    
    The Interpreter agent uses an LLM provider to generate step-by-step execution
    plans from natural language task descriptions. It validates plans against a
    constitution system to ensure quality and correctness.
    
    Args:
        provider: LLM provider for generating plans (OpenAI, Anthropic, or Local)
        failure_store: Optional store for tracking constitution failures
    
    Example:
        >>> from parallax.llm.openai_provider import OpenAIPlanner
        >>> from parallax.core.constitution import FailureStore
        >>> 
        >>> provider = OpenAIPlanner()
        >>> interpreter = Interpreter(provider)
        >>> plan = await interpreter.plan("Create a project in Linear")
        >>> print(f"Generated {len(plan.steps)} steps")
    """
    
    def __init__(
        self,
        provider: "PlannerProvider",
        failure_store: Optional[FailureStore] = None,
        strategy_generator: Optional[StrategyGenerator] = None,
    ) -> None:
        self.provider = provider
        self.failure_store = failure_store
        self.strategy_generator = strategy_generator
        self.constitution = INTERPRETER_CONSTITUTION

    async def plan(self, task: str, context: Optional[dict] = None) -> ExecutionPlan:
        """
        Generate an execution plan from a natural language task.
        
        Converts a task description into a structured execution plan with ordered
        steps. Validates the plan against the Interpreter constitution to ensure
        it has valid structure, non-empty steps, and valid actions.
        
        Args:
            task: Natural language description of the task (e.g., "Create a project in Linear")
            context: Optional context dictionary with additional information (e.g., {"start_url": "https://linear.app"})
        
        Returns:
            ExecutionPlan with ordered steps for the Navigator to execute
        
        Raises:
            ConstitutionViolation: If the plan fails critical validation rules
        
        Example:
            >>> plan = await interpreter.plan("Filter issues by status", {"start_url": "https://linear.app"})
            >>> for step in plan.steps:
            ...     print(f"{step.action}: {step.selector or step.name}")
        """
        context = context or {}
        
        # Enhance context with strategies if available
        if self.strategy_generator:
            failure_patterns = self.strategy_generator.analyze_failures(limit=20)
            if failure_patterns:
                context = {
                    **context,
                    "failure_patterns": failure_patterns,
                    "use_strategies": True,
                }
        
        plan = await self.provider.generate_plan(task, context)
        
        # Estimate tokens (rough: 1 token ≈ 4 chars)
        tokens_estimate = len(task) // 4 + len(str(plan)) // 4
        llm_tokens.observe(tokens_estimate)
        
        # Validate plan against constitution
        validation_context = {**context, "task": task}
        report = self.constitution.validate(task, plan, validation_context)
        
        if not report.passed:
            log.error(
                "constitution_failed",
                agent="A1_Interpreter",
                failures=[f.rule_name for f in report.failures],
            )
            if self.failure_store:
                self.failure_store.save_failure(report)
            # For critical failures, raise exception
            self.constitution.must_pass(task, plan, validation_context)
        elif report.warnings:
            log.warning(
                "constitution_warnings",
                agent="A1_Interpreter",
                warnings=[w.rule_name for w in report.warnings],
            )
            if self.failure_store:
                self.failure_store.save_failure(report)
        
        return plan


class PlannerProvider:
    """
    Base class for LLM-based plan generation providers.
    
    Implementations should provide concrete implementations of `generate_plan`
    that use specific LLM providers (OpenAI, Anthropic, Local) to generate
    execution plans from natural language tasks.
    """
    
    async def generate_plan(self, task: str, context: dict) -> ExecutionPlan:  # pragma: no cover
        """
        Generate an execution plan from a task description.
        
        Args:
            task: Natural language task description
            context: Context dictionary with additional information
        
        Returns:
            ExecutionPlan with ordered steps
        
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError


