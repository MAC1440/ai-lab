from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


TaskStage = Literal["chat", "planning", "generation", "repair"]


class RuntimeStageSettings(BaseModel):
    """User-editable generation limits for one model stage."""

    num_ctx: int = Field(default=4096, ge=1024, le=131072)
    max_tokens: int = Field(default=1024, ge=64, le=32768)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    reserve_tokens: int = Field(default=512, ge=128, le=8192)

    @model_validator(mode="after")
    def validate_budget(self) -> "RuntimeStageSettings":
        if self.max_tokens + self.reserve_tokens >= self.num_ctx:
            raise ValueError(
                "max_tokens + reserve_tokens must be smaller than num_ctx"
            )
        return self

    @property
    def safe_input_tokens(self) -> int:
        return max(128, self.num_ctx - self.max_tokens - self.reserve_tokens)


class RuntimeSettingsDocument(BaseModel):
    version: int = 1
    automatic: bool = True
    chat: RuntimeStageSettings = Field(
        default_factory=lambda: RuntimeStageSettings(
            num_ctx=4096,
            max_tokens=1024,
            temperature=0.2,
            reserve_tokens=512,
        )
    )
    planning: RuntimeStageSettings = Field(
        default_factory=lambda: RuntimeStageSettings(
            num_ctx=4096,
            max_tokens=1024,
            temperature=0.0,
            reserve_tokens=768,
        )
    )
    generation: RuntimeStageSettings = Field(
        default_factory=lambda: RuntimeStageSettings(
            num_ctx=8192,
            max_tokens=3072,
            temperature=0.0,
            reserve_tokens=768,
        )
    )
    repair: RuntimeStageSettings = Field(
        default_factory=lambda: RuntimeStageSettings(
            num_ctx=6144,
            max_tokens=2048,
            temperature=0.0,
            reserve_tokens=768,
        )
    )


class RuntimeSettingsService:
    """Persist stage-specific context and generation settings."""

    def __init__(self, settings_path: str | Path) -> None:
        self.settings_path = Path(settings_path)
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.settings_path.exists():
            self.save(RuntimeSettingsDocument())

    def get(self) -> RuntimeSettingsDocument:
        with self._lock:
            try:
                raw = json.loads(self.settings_path.read_text(encoding="utf-8"))
                return RuntimeSettingsDocument.model_validate(raw)
            except (OSError, json.JSONDecodeError, ValueError):
                document = RuntimeSettingsDocument()
                self.save(document)
                return document

    def save(
        self,
        document: RuntimeSettingsDocument,
    ) -> RuntimeSettingsDocument:
        with self._lock:
            temporary = self.settings_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(document.model_dump(), indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.settings_path)
        return document

    def stage(self, stage: TaskStage) -> RuntimeStageSettings:
        return getattr(self.get(), stage)

    def apply_recommendation(
        self,
        recommended_context: int,
    ) -> RuntimeSettingsDocument:
        """
        Build conservative defaults from the hardware recommendation.

        Generation receives the largest budget because complete-file changes
        commonly need more output than planning or repair.
        """
        context = max(2048, min(32768, int(recommended_context)))
        document = RuntimeSettingsDocument(
            automatic=True,
            chat=RuntimeStageSettings(
                num_ctx=context,
                max_tokens=max(512, min(2048, context // 4)),
                temperature=0.2,
                reserve_tokens=max(512, min(1024, context // 8)),
            ),
            planning=RuntimeStageSettings(
                num_ctx=context,
                max_tokens=max(512, min(1536, context // 5)),
                temperature=0.0,
                reserve_tokens=max(512, min(1024, context // 8)),
            ),
            generation=RuntimeStageSettings(
                num_ctx=context,
                max_tokens=max(1024, min(4096, context * 3 // 8)),
                temperature=0.0,
                reserve_tokens=max(512, min(1024, context // 8)),
            ),
            repair=RuntimeStageSettings(
                num_ctx=context,
                max_tokens=max(768, min(3072, context // 3)),
                temperature=0.0,
                reserve_tokens=max(512, min(1024, context // 8)),
            ),
        )
        return self.save(document)
