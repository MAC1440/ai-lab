from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from math import ceil
from typing import TYPE_CHECKING, Any, Dict, Generic, Protocol, Type, TypeVar

from pydantic import BaseModel

from services.agent_service import AgentService

if TYPE_CHECKING:
    from services.model_capability_service import ModelCapabilityService
    from services.provider_settings_service import ProviderSettingsService


OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True)
class ModelStageResult(Generic[OutputT]):
    output: OutputT
    usage: Dict[str, Any]
    model: str
    provider_id: str
    capability: Dict[str, Any]


class TaskModelOutputError(RuntimeError):
    """Raised when a task model cannot satisfy a structured stage contract."""

    def __init__(
        self,
        *,
        stage: str,
        model: str,
        provider_id: str,
        attempts: int,
        detail: str = "",
    ) -> None:
        self.stage = stage
        self.model = model
        self.provider_id = provider_id
        self.attempts = attempts
        self.detail = detail
        message = (
            f"The {stage} stage could not produce valid structured output "
            f"with model '{model}' after {attempts} request(s)."
        )
        if detail:
            message += f" Last validation detail: {detail}"
        message += (
            " Use a model with reliable JSON-schema output or simplify the "
            "task before retrying."
        )
        super().__init__(message)


class TaskModelClient(Protocol):
    def prompt_budget(self, *, agent_id: str, stage: str) -> int: ...

    def estimate_tokens(
        self,
        *,
        agent_id: str,
        stage: str,
        text: str,
    ) -> int: ...

    async def generate(
        self,
        *,
        agent_id: str,
        stage: str,
        prompt: str,
        output_type: Type[OutputT],
    ) -> ModelStageResult[OutputT]: ...


class _InferredCapabilityService:
    """Compatibility adapter for older dependency modules during migration."""

    @staticmethod
    def resolve_runtime(runtime: Dict[str, Any]) -> Dict[str, Any]:
        generation = runtime.get("generation", {})
        context = int(generation.get("context_window", 8192))
        output = int(generation.get("max_tokens", 2048))
        return {
            "provider_id": runtime["provider_id"],
            "model": runtime["model"],
            "structured_output_mode": (
                "native"
                if runtime.get("provider", {}).get("kind") == "ollama"
                else "tool"
            ),
            "effective_context_window": context,
            "effective_max_output_tokens": output,
            "effective_safe_input_tokens": max(512, context - output - 768),
            "estimated_characters_per_token": 3.0,
            "profile_source": "inferred",
        }

    def require_structured_stage(
        self,
        runtime: Dict[str, Any],
        stage: str,
    ) -> Dict[str, Any]:
        del stage
        return self.resolve_runtime(runtime)


class PydanticTaskModelClient:
    """Run one tool-free, structured model call for one bounded task stage."""

    def __init__(
        self,
        *,
        provider_settings_service: "ProviderSettingsService",
        model_capability_service: "ModelCapabilityService | None" = None,
        agent_service: AgentService | None = None,
        request_limit: int = 3,
    ) -> None:
        if request_limit < 1 or request_limit > 6:
            raise ValueError("request_limit must be between 1 and 6")
        self.provider_settings_service = provider_settings_service
        self.model_capability_service = (
            model_capability_service or _InferredCapabilityService()
        )
        self.agent_service = agent_service or AgentService()
        self.request_limit = request_limit

    def prompt_budget(self, *, agent_id: str, stage: str) -> int:
        profile = self.agent_service.get_agent(agent_id)
        runtime = self.provider_settings_service.runtime_config(
            agent_id,
            profile.get("model", "granite4.1:3b"),
            stage=stage,
        )
        capability = self.model_capability_service.require_structured_stage(
            runtime,
            stage,
        )
        return int(capability["effective_safe_input_tokens"])

    def estimate_tokens(
        self,
        *,
        agent_id: str,
        stage: str,
        text: str,
    ) -> int:
        profile = self.agent_service.get_agent(agent_id)
        runtime = self.provider_settings_service.runtime_config(
            agent_id,
            profile.get("model", "granite4.1:3b"),
            stage=stage,
        )
        capability = self.model_capability_service.resolve_runtime(runtime)
        characters_per_token = float(
            capability.get("estimated_characters_per_token", 3.0)
        )
        return max(1, ceil(len(text) / characters_per_token))

    async def generate(
        self,
        *,
        agent_id: str,
        stage: str,
        prompt: str,
        output_type: Type[OutputT],
    ) -> ModelStageResult[OutputT]:
        # Keep Pydantic AI imports lazy so contract/orchestration tests do not
        # require loading model-provider integrations.
        from pydantic_ai import (
            Agent,
            ModelSettings,
            NativeOutput,
            UnexpectedModelBehavior,
            UsageLimits,
        )

        from services.pydantic_model import build_pydantic_model

        profile = self.agent_service.get_agent(agent_id)
        runtime = self.provider_settings_service.runtime_config(
            agent_id,
            profile.get("model", "granite4.1:3b"),
            stage=stage,
        )
        capability = self.model_capability_service.require_structured_stage(
            runtime,
            stage,
        )
        configured_max_tokens = int(
            capability["effective_max_output_tokens"]
        )
        max_tokens = (
            min(configured_max_tokens, 4096)
            if stage == "planning"
            else configured_max_tokens
        )
        model = build_pydantic_model(runtime)

        # Ollama exposes JSON-schema constrained responses through its native
        # API and through the OpenAI-compatible ``response_format`` field.
        # Using NativeOutput avoids asking a small local model to manufacture a
        # special final-result tool call. Unknown OpenAI-compatible servers keep
        # Pydantic AI's broadly supported tool-output default.
        structured_output: Any = output_type
        if capability["structured_output_mode"] == "native":
            structured_output = NativeOutput(
                output_type,
                name=f"{stage}_result",
                description=(
                    f"Return the validated structured result for the {stage} "
                    "stage of a project coding task."
                ),
            )
        agent = Agent(
            model,
            output_type=structured_output,
            system_prompt=self._system_prompt(profile, stage),
            retries={"output": 2},
        )
        try:
            result = await agent.run(
                prompt,
                usage_limits=UsageLimits(request_limit=self.request_limit),
                model_settings=ModelSettings(
                    # Structured planning and code generation benefit from
                    # deterministic sampling. User chat keeps its own setting.
                    temperature=0.0,
                    max_tokens=max_tokens,
                ),
            )
        except UnexpectedModelBehavior as error:
            raise TaskModelOutputError(
                stage=stage,
                model=runtime["model"],
                provider_id=runtime["provider_id"],
                attempts=self.request_limit,
                detail=self._failure_detail(error),
            ) from error
        return ModelStageResult(
            output=result.output,
            usage=self._usage_dict(result.usage),
            model=runtime["model"],
            provider_id=runtime["provider_id"],
            capability=capability,
        )

    @staticmethod
    def _system_prompt(profile: Dict[str, Any], stage: str) -> str:
        profile_prompt = str(profile.get("system_prompt", "")).strip()
        if stage == "planning":
            stage_prompt = (
                "You are the planning stage of a production coding workflow. "
                "Return only the requested structured plan. Do not write source "
                "code, call tools, or add files that are not required by the goal."
            )
        elif stage == "generation":
            stage_prompt = (
                "You are the generation stage of a production coding workflow. "
                "Return only the requested structured change set. Follow the "
                "approved plan exactly and provide complete contents for every "
                "create or update operation. Do not call tools."
            )
        elif stage == "repair":
            stage_prompt = (
                "You are the repair stage of a production coding workflow. "
                "Return only the requested structured change set. Use the "
                "verification failure and current affected files to make the "
                "smallest complete-file correction. Do not call tools or touch "
                "unlisted files."
            )
        else:
            raise ValueError(f"Unknown task model stage: {stage}")
        return f"{profile_prompt}\n\n{stage_prompt}".strip()

    @staticmethod
    def _usage_dict(usage: Any) -> Dict[str, Any]:
        if is_dataclass(usage):
            return asdict(usage)
        if hasattr(usage, "model_dump"):
            return dict(usage.model_dump())
        result: Dict[str, Any] = {}
        for name in ("requests", "input_tokens", "output_tokens", "tool_calls"):
            value = getattr(usage, name, None)
            if value is not None:
                result[name] = value
        return result

    @staticmethod
    def _failure_detail(error: BaseException) -> str:
        """Return a bounded useful cause without leaking a full model response."""

        cause = error.__cause__
        detail = str(cause or error).strip()
        if not detail or detail == str(error).strip():
            return ""
        return " ".join(detail.split())[:800]
