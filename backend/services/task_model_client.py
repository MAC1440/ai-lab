from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import TYPE_CHECKING, Any, Dict, Generic, Protocol, Type, TypeVar

from pydantic import BaseModel

from services.agent_service import AgentService

if TYPE_CHECKING:
    from services.provider_settings_service import ProviderSettingsService


OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True)
class ModelStageResult(Generic[OutputT]):
    output: OutputT
    usage: Dict[str, Any]
    model: str
    provider_id: str


class TaskModelClient(Protocol):
    def prompt_budget(self, *, agent_id: str, stage: str) -> int: ...

    async def generate(
        self,
        *,
        agent_id: str,
        stage: str,
        prompt: str,
        output_type: Type[OutputT],
    ) -> ModelStageResult[OutputT]: ...


class PydanticTaskModelClient:
    """Run one tool-free, structured model call for one bounded task stage."""

    def __init__(
        self,
        *,
        provider_settings_service: "ProviderSettingsService",
        agent_service: AgentService | None = None,
        request_limit: int = 3,
    ) -> None:
        if request_limit < 1 or request_limit > 6:
            raise ValueError("request_limit must be between 1 and 6")
        self.provider_settings_service = provider_settings_service
        self.agent_service = agent_service or AgentService()
        self.request_limit = request_limit

    def prompt_budget(self, *, agent_id: str, stage: str) -> int:
        profile = self.agent_service.get_agent(agent_id)
        runtime = self.provider_settings_service.runtime_config(
            agent_id,
            profile.get("model", "granite4.1:3b"),
        )
        generation = runtime.get("generation", {})
        context_window = int(generation.get("context_window", 8192))
        configured_output = int(generation.get("max_tokens", 2048))
        output_reserve = (
            min(configured_output, 4096)
            if stage == "planning"
            else configured_output
        )
        # Code commonly averages closer to three characters per token than
        # prose. Reserve an additional 768 tokens for instructions and output
        # schema overhead; never silently truncate a source file.
        safe_input_tokens = max(1024, context_window - output_reserve - 768)
        return safe_input_tokens * 3

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
        from pydantic_ai import Agent, ModelSettings, UsageLimits

        from services.pydantic_model import build_pydantic_model

        profile = self.agent_service.get_agent(agent_id)
        runtime = self.provider_settings_service.runtime_config(
            agent_id,
            profile.get("model", "granite4.1:3b"),
        )
        generation = runtime.get("generation", {})
        configured_temperature = float(generation.get("temperature", 0.1))
        configured_max_tokens = int(generation.get("max_tokens", 2048))
        max_tokens = (
            min(configured_max_tokens, 4096)
            if stage == "planning"
            else configured_max_tokens
        )
        model = build_pydantic_model(runtime)
        agent = Agent(
            model,
            output_type=output_type,
            system_prompt=self._system_prompt(profile, stage),
            retries={"output": 2},
        )
        result = await agent.run(
            prompt,
            usage_limits=UsageLimits(request_limit=self.request_limit),
            model_settings=ModelSettings(
                temperature=min(configured_temperature, 0.2),
                max_tokens=max_tokens,
            ),
        )
        return ModelStageResult(
            output=result.output,
            usage=self._usage_dict(result.usage),
            model=runtime["model"],
            provider_id=runtime["provider_id"],
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
