from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from math import ceil
from typing import TYPE_CHECKING, Any, Dict, Generic, Protocol, Type, TypeVar

from pydantic import BaseModel

from services.agent_service import AgentService
from services.ollama_runtime import (
    is_ollama_cloud_runtime,
    ollama_model_settings_extra_body,
)
from services.task_model_output_adapter import (
    model_output_type,
    normalize_model_output,
)

if TYPE_CHECKING:
    from services.model_capability_service import ModelCapabilityService
    from services.provider_settings_service import ProviderSettingsService
    from services.runtime_metrics_service import RuntimeMetricsService
    from services.runtime_settings_service import RuntimeSettingsService


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
        use_agent_prompt: bool = True,
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
                and not is_ollama_cloud_runtime(runtime)
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
        runtime_settings_service: "RuntimeSettingsService | None" = None,
        runtime_metrics_service: "RuntimeMetricsService | None" = None,
        request_limit: int = 3,
    ) -> None:
        if request_limit < 1 or request_limit > 6:
            raise ValueError("request_limit must be between 1 and 6")
        self.provider_settings_service = provider_settings_service
        self.model_capability_service = (
            model_capability_service or _InferredCapabilityService()
        )
        self.agent_service = agent_service or AgentService()
        self.runtime_settings_service = runtime_settings_service
        self.runtime_metrics_service = runtime_metrics_service
        self.request_limit = request_limit
        self._native_grammar_rejections: set[tuple[str, str]] = set()

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
        capability_budget = int(capability["effective_safe_input_tokens"])
        stage_settings = (
            self.runtime_settings_service.stage(stage)
            if self.runtime_settings_service is not None
            else None
        )
        if stage_settings is None:
            return capability_budget
        return min(capability_budget, stage_settings.safe_input_tokens)

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
        use_agent_prompt: bool = True,
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
        runtime_key = (runtime["provider_id"], runtime["model"])
        if (
            capability["structured_output_mode"] == "native"
            and runtime_key in self._native_grammar_rejections
        ):
            capability = {
                **capability,
                "structured_output_mode": "tool",
                "structured_output_fallback": "native_grammar_rejected",
            }
        stage_settings = (
            self.runtime_settings_service.stage(stage)
            if self.runtime_settings_service is not None
            else None
        )

        configured_context = int(capability["effective_context_window"])
        configured_max_tokens = int(capability["effective_max_output_tokens"])

        context_window = (
            min(configured_context, stage_settings.num_ctx)
            if stage_settings is not None
            else configured_context
        )
        max_tokens = (
            min(configured_max_tokens, stage_settings.max_tokens)
            if stage_settings is not None
            else configured_max_tokens
        )
        temperature = (
            stage_settings.temperature if stage_settings is not None else 0.0
        )
        safe_input_tokens = (
            min(
                int(capability["effective_safe_input_tokens"]),
                stage_settings.safe_input_tokens,
            )
            if stage_settings is not None
            else int(capability["effective_safe_input_tokens"])
        )

        capability = {
            **capability,
            "effective_context_window": context_window,
            "effective_max_output_tokens": max_tokens,
            "effective_safe_input_tokens": safe_input_tokens,
            "runtime_settings_source": (
                "runtime-settings" if stage_settings is not None else "capability"
            ),
        }
        model = build_pydantic_model(runtime)

        # Ollama exposes JSON-schema constrained responses through its native
        # API and through the OpenAI-compatible ``response_format`` field.
        # Using NativeOutput avoids asking a small local model to manufacture a
        # special final-result tool call. Unknown OpenAI-compatible servers keep
        # Pydantic AI's broadly supported tool-output default.
        boundary_output_type = model_output_type(output_type)
        structured_output: Any = boundary_output_type
        if capability["structured_output_mode"] == "native":
            structured_output = NativeOutput(
                boundary_output_type,
                name=f"{stage}_result",
                description=(
                    f"Return the validated structured result for the {stage} "
                    "stage of a project coding task."
                ),
            )
        system_prompt = self._system_prompt(
            profile,
            stage,
            use_agent_prompt=use_agent_prompt,
        )
        extra_body = ollama_model_settings_extra_body(
            runtime,
            context_window,
        )
        run_arguments = {
            "usage_limits": UsageLimits(request_limit=self.request_limit),
            "model_settings": ModelSettings(
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=extra_body,
            ),
        }

        def build_agent(result_type: Any):
            return Agent(
                model,
                output_type=result_type,
                system_prompt=system_prompt,
                retries={"output": 2},
            )

        agent = build_agent(structured_output)
        started_at = (
            self.runtime_metrics_service.timer()
            if self.runtime_metrics_service is not None
            else None
        )
        try:
            result = await agent.run(prompt, **run_arguments)
        except Exception as error:
            # Some Ollama models advertise JSON-schema responses but their
            # llama.cpp grammar converter rejects schemas used by real task
            # contracts before the model can generate a token. Granite 4.1 is
            # one known example. Retry only this provider-level grammar failure
            # with Pydantic AI's final-result tool contract; unrelated provider
            # and validation errors must keep their original behavior.
            if (
                capability["structured_output_mode"] == "native"
                and runtime.get("provider", {}).get("kind") == "ollama"
                and self._is_native_grammar_error(error)
            ):
                self._native_grammar_rejections.add(runtime_key)
                capability = {
                    **capability,
                    "structured_output_mode": "tool",
                    "structured_output_fallback": "native_grammar_rejected",
                }
                try:
                    result = await build_agent(boundary_output_type).run(
                        prompt,
                        **run_arguments,
                    )
                except UnexpectedModelBehavior as fallback_error:
                    raise self._output_error(
                        fallback_error,
                        stage=stage,
                        runtime=runtime,
                    ) from fallback_error
            elif isinstance(error, UnexpectedModelBehavior):
                raise self._output_error(
                    error,
                    stage=stage,
                    runtime=runtime,
                ) from error
            else:
                raise
        normalized_output, normalization_actions = normalize_model_output(
            result.output,
            output_type,
        )
        capability = {
            **capability,
            "output_normalization": {
                "applied": bool(normalization_actions),
                "actions": normalization_actions,
            },
        }
        usage = self._usage_dict(result.usage)
        if self.runtime_metrics_service is not None and started_at is not None:
            usage["runtime_metric"] = self.runtime_metrics_service.record(
                started_at=started_at,
                agent_id=agent_id,
                stage=stage,
                runtime=runtime,
                usage=usage,
                context_window=context_window,
                max_tokens=max_tokens,
                safe_input_tokens=safe_input_tokens,
                temperature=temperature,
            )
        return ModelStageResult(
            output=normalized_output,
            usage=usage,
            model=runtime["model"],
            provider_id=runtime["provider_id"],
            capability=capability,
        )

    def _output_error(
        self,
        error: BaseException,
        *,
        stage: str,
        runtime: Dict[str, Any],
    ) -> TaskModelOutputError:
        return TaskModelOutputError(
            stage=stage,
            model=runtime["model"],
            provider_id=runtime["provider_id"],
            attempts=self.request_limit,
            detail=self._failure_detail(error),
        )

    @staticmethod
    def _is_native_grammar_error(error: BaseException) -> bool:
        """Recognize Ollama/llama.cpp grammar setup failures through wrappers."""

        current: BaseException | None = error
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            message = str(current).casefold()
            if "failed to parse grammar" in message or (
                "failed to initialize samplers" in message
                and "grammar" in message
            ):
                return True
            current = current.__cause__ or current.__context__
        return False

    @staticmethod
    def _system_prompt(
        profile: Dict[str, Any],
        stage: str,
        *,
        use_agent_prompt: bool = True,
    ) -> str:
        profile_prompt = (
            str(profile.get("system_prompt", "")).strip()
            if use_agent_prompt
            else ""
        )
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
