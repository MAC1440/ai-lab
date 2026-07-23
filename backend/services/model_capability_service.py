from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator


StructuredOutputMode = Literal["native", "tool", "unsupported"]
TaskStage = Literal["planning", "generation", "repair"]


class StageScores(BaseModel):
    planning: float = Field(default=0.5, ge=0.0, le=1.0)
    generation: float = Field(default=0.5, ge=0.0, le=1.0)
    repair: float = Field(default=0.5, ge=0.0, le=1.0)


class ModelCapabilityInput(BaseModel):
    provider_id: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=250)
    context_window: int = Field(ge=1024, le=1_000_000)
    safe_input_tokens: Optional[int] = Field(
        default=None,
        ge=512,
        le=1_000_000,
    )
    max_output_tokens: int = Field(default=4096, ge=128, le=131072)
    structured_output_mode: StructuredOutputMode = "tool"
    supports_tools: bool = True
    supports_parallel_tools: bool = False
    stage_scores: StageScores = Field(default_factory=StageScores)
    measured_tokens_per_second: Optional[float] = Field(
        default=None,
        gt=0.0,
        le=10000.0,
    )
    estimated_characters_per_token: float = Field(
        default=3.0,
        ge=1.0,
        le=8.0,
    )
    benchmarked_at: Optional[str] = None
    notes: str = Field(default="", max_length=2000)

    @field_validator("provider_id", "model")
    @classmethod
    def strip_required(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Value cannot be empty")
        return clean

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str) -> str:
        return value.strip()


class ModelCapabilityService:
    """Persist measured model limits independently from agent assignments."""

    def __init__(self, settings_path: str | Path) -> None:
        self.settings_path = Path(settings_path)
        self._lock = threading.RLock()
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_document()

    def list_profiles(self) -> list[Dict[str, Any]]:
        profiles = list(self._read()["profiles"].values())
        profiles.sort(
            key=lambda item: (
                str(item["provider_id"]).casefold(),
                str(item["model"]).casefold(),
            )
        )
        return deepcopy(profiles)

    def get_profile(self, provider_id: str, model: str) -> Dict[str, Any]:
        key = self._key(provider_id, model)
        profile = self._read()["profiles"].get(key)
        if profile is None:
            raise ValueError(
                f"No capability profile exists for {provider_id}/{model}"
            )
        return deepcopy(profile)

    def save_profile(self, data: ModelCapabilityInput) -> Dict[str, Any]:
        profile = data.model_dump()
        if profile["safe_input_tokens"] is not None:
            maximum_safe_input = (
                profile["context_window"] - profile["max_output_tokens"]
            )
            if profile["safe_input_tokens"] > maximum_safe_input:
                raise ValueError(
                    "safe_input_tokens must leave room for max_output_tokens"
                )
        profile["updated_at"] = self._utc_now()
        key = self._key(profile["provider_id"], profile["model"])
        with self._lock:
            document = self._read()
            document["profiles"][key] = profile
            self._write(document)
        return deepcopy(profile)

    def delete_profile(self, provider_id: str, model: str) -> None:
        key = self._key(provider_id, model)
        with self._lock:
            document = self._read()
            if key not in document["profiles"]:
                raise ValueError(
                    f"No capability profile exists for {provider_id}/{model}"
                )
            del document["profiles"][key]
            self._write(document)

    def record_benchmark(
        self,
        *,
        capability: Dict[str, Any],
        stage: TaskStage,
        score: float,
        measured_tokens_per_second: Optional[float],
        benchmarked_at: str,
    ) -> Dict[str, Any]:
        """Merge one measured stage result without changing model assignments."""

        if stage not in {"planning", "generation", "repair"}:
            raise ValueError(f"Unsupported benchmark stage: {stage}")
        if score < 0.0 or score > 1.0:
            raise ValueError("Benchmark score must be between 0 and 1")
        provider_id = str(capability["provider_id"])
        model = str(capability["model"])
        key = self._key(provider_id, model)
        with self._lock:
            document = self._read()
            saved = document["profiles"].get(key)
            if saved is None:
                saved = {
                    "provider_id": provider_id,
                    "model": model,
                    "context_window": int(
                        capability.get("context_window")
                        or capability["effective_context_window"]
                    ),
                    "safe_input_tokens": int(
                        capability["effective_safe_input_tokens"]
                    ),
                    "max_output_tokens": int(
                        capability.get("max_output_tokens")
                        or capability["effective_max_output_tokens"]
                    ),
                    "structured_output_mode": capability.get(
                        "structured_output_mode", "tool"
                    ),
                    "supports_tools": bool(
                        capability.get("supports_tools", True)
                    ),
                    "supports_parallel_tools": bool(
                        capability.get("supports_parallel_tools", False)
                    ),
                    "stage_scores": StageScores().model_dump(),
                    "measured_tokens_per_second": None,
                    "estimated_characters_per_token": float(
                        capability.get("estimated_characters_per_token", 3.0)
                    ),
                    "benchmarked_at": None,
                    "notes": str(capability.get("notes") or ""),
                }
            saved = deepcopy(saved)
            scores = dict(saved.get("stage_scores") or StageScores().model_dump())
            scores[stage] = round(float(score), 4)
            saved["stage_scores"] = scores
            if measured_tokens_per_second is not None:
                previous_speed = saved.get("measured_tokens_per_second")
                saved["measured_tokens_per_second"] = round(
                    (
                        float(measured_tokens_per_second)
                        if previous_speed is None
                        else (
                            float(previous_speed)
                            + float(measured_tokens_per_second)
                        )
                        / 2
                    ),
                    3,
                )
            saved["benchmarked_at"] = benchmarked_at
            saved["updated_at"] = self._utc_now()
            document["profiles"][key] = saved
            self._write(document)
        return deepcopy(saved)

    def recommend_assignments(self) -> Dict[str, Any]:
        """Rank benchmarked models per stage; never apply recommendations."""

        profiles = [
            profile
            for profile in self.list_profiles()
            if profile.get("benchmarked_at")
            and profile.get("structured_output_mode") != "unsupported"
        ]
        recommendations: Dict[str, Any] = {}
        for stage in ("planning", "generation", "repair"):
            ranked = sorted(
                profiles,
                key=lambda profile: (
                    -float(profile.get("stage_scores", {}).get(stage, 0.0)),
                    -float(profile.get("measured_tokens_per_second") or 0.0),
                    str(profile.get("model") or "").casefold(),
                ),
            )
            recommendations[stage] = (
                {
                    "provider_id": ranked[0]["provider_id"],
                    "model": ranked[0]["model"],
                    "score": ranked[0]["stage_scores"][stage],
                    "measured_tokens_per_second": ranked[0].get(
                        "measured_tokens_per_second"
                    ),
                    "benchmarked_at": ranked[0].get("benchmarked_at"),
                }
                if ranked
                else None
            )
        return {
            "recommendations": recommendations,
            "benchmarked_model_count": len(profiles),
            "applied": False,
        }

    def resolve_runtime(self, runtime: Dict[str, Any]) -> Dict[str, Any]:
        """Clamp user generation settings to tested model capabilities.

        An unprofiled model remains usable with conservative provider-derived
        defaults. This keeps existing installations working while making the
        absence of a benchmark visible to clients.
        """

        provider_id = str(runtime["provider_id"])
        model = str(runtime["model"])
        generation = runtime.get("generation", {})
        configured_context = int(generation.get("context_window", 8192))
        configured_output = int(generation.get("max_tokens", 2048))
        key = self._key(provider_id, model)
        saved = self._read()["profiles"].get(key)
        if saved is None:
            provider_kind = runtime.get("provider", {}).get("kind")
            structured_mode = (
                "native" if provider_kind == "ollama" else "tool"
            )
            profile: Dict[str, Any] = {
                "provider_id": provider_id,
                "model": model,
                "context_window": configured_context,
                "safe_input_tokens": None,
                "max_output_tokens": configured_output,
                "structured_output_mode": structured_mode,
                "supports_tools": True,
                "supports_parallel_tools": False,
                "stage_scores": StageScores().model_dump(),
                "measured_tokens_per_second": None,
                "estimated_characters_per_token": 3.0,
                "benchmarked_at": None,
                "notes": "",
                "updated_at": None,
                "profile_source": "inferred",
            }
        else:
            profile = deepcopy(saved)
            profile["profile_source"] = "saved"

        effective_context = min(
            configured_context,
            int(profile["context_window"]),
        )
        effective_output = min(
            configured_output,
            int(profile["max_output_tokens"]),
        )
        safe_input = profile.get("safe_input_tokens")
        if safe_input is None:
            safe_input = max(512, effective_context - effective_output - 768)
        else:
            safe_input = min(
                int(safe_input),
                max(512, effective_context - effective_output),
            )
        profile["effective_context_window"] = effective_context
        profile["effective_max_output_tokens"] = effective_output
        profile["effective_safe_input_tokens"] = safe_input
        return profile

    def require_structured_stage(
        self,
        runtime: Dict[str, Any],
        stage: TaskStage,
    ) -> Dict[str, Any]:
        profile = self.resolve_runtime(runtime)
        if profile["structured_output_mode"] == "unsupported":
            raise ValueError(
                f"Model '{profile['model']}' is marked as unable to produce "
                f"structured output required by the {stage} stage"
            )
        return profile

    def _ensure_document(self) -> None:
        if not self.settings_path.exists():
            self._write({"version": 1, "profiles": {}})

    def _read(self) -> Dict[str, Any]:
        with self._lock:
            try:
                document = json.loads(self.settings_path.read_text("utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise RuntimeError(
                    f"Could not read model capability settings: {error}"
                ) from error
            if not isinstance(document, dict):
                raise RuntimeError("Model capability settings must be an object")
            document.setdefault("version", 1)
            document.setdefault("profiles", {})
            if not isinstance(document["profiles"], dict):
                raise RuntimeError("Model capability profiles must be an object")
            return document

    def _write(self, document: Dict[str, Any]) -> None:
        with self._lock:
            temporary = self.settings_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.settings_path)

    @staticmethod
    def _key(provider_id: str, model: str) -> str:
        clean_provider = provider_id.strip()
        clean_model = model.strip()
        if not clean_provider or not clean_model:
            raise ValueError("provider_id and model must be non-empty")
        return f"{clean_provider}\u0000{clean_model}"

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
