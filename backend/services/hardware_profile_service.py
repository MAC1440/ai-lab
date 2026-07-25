from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx


_GIB = 1024**3


@dataclass(frozen=True)
class GpuInfo:
    name: str
    memory_total_bytes: int
    memory_free_bytes: int | None
    utilization_percent: float | None
    temperature_c: float | None


class HardwareProfileService:
    """
    Read local CPU/RAM/GPU details and calculate realistic local-LLM bands.

    Recommendations are intentionally conservative. Model architecture,
    quantization, context length and runtime overhead affect actual fit.
    """

    def __init__(self, ollama_base_url: str = "http://localhost:11434") -> None:
        self.ollama_base_url = ollama_base_url.rstrip("/")

    def snapshot(self) -> dict[str, Any]:
        ram_total, ram_available = self._memory()
        gpu = self._nvidia_gpu()
        cpu_count = os.cpu_count() or 1

        recommendation = self._recommend(
            ram_total_bytes=ram_total,
            gpu_memory_bytes=gpu.memory_total_bytes if gpu else 0,
            cpu_count=cpu_count,
        )
        installed = self._installed_models()
        matched = self._classify_installed(installed, recommendation)

        return {
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "processor": platform.processor() or "Unknown CPU",
            },
            "cpu": {
                "logical_cores": cpu_count,
            },
            "memory": {
                "total_bytes": ram_total,
                "available_bytes": ram_available,
                "used_percent": (
                    round((1 - ram_available / ram_total) * 100, 1)
                    if ram_total
                    else None
                ),
            },
            "gpu": asdict(gpu) if gpu else None,
            "recommendation": recommendation,
            "installed_models": matched,
            "disclaimer": (
                "Parameter bands assume roughly Q4 quantization and one request "
                "at a time. Exact performance depends on architecture, context "
                "length, KV-cache format and background GPU/RAM usage."
            ),
        }

    def _recommend(
        self,
        *,
        ram_total_bytes: int,
        gpu_memory_bytes: int,
        cpu_count: int,
    ) -> dict[str, Any]:
        ram_gib = ram_total_bytes / _GIB
        vram_gib = gpu_memory_bytes / _GIB

        # Full-GPU bands leave room for CUDA buffers, KV cache and the display.
        usable_vram = max(0.0, vram_gib - (0.65 if vram_gib else 0.0))
        fastest_b = max(0.5, usable_vram / 0.72)

        # Balanced permits partial CPU offload but avoids filling system RAM.
        usable_ram = max(2.0, ram_gib * 0.55)
        balanced_b = min(7.0, max(fastest_b, usable_ram / 0.75))

        # Maximum practical is intentionally not "will be pleasant".
        maximum_b = min(14.0, max(balanced_b, ram_gib * 0.72))

        if vram_gib < 4:
            recommended_context = 4096
        elif vram_gib < 8:
            recommended_context = 8192
        elif vram_gib < 16:
            recommended_context = 16384
        else:
            recommended_context = 32768

        # On CPU-heavy systems, large context hurts interactivity quickly.
        if cpu_count <= 6 and vram_gib < 6:
            recommended_context = min(recommended_context, 4096)

        return {
            "quantization_assumption": "Q4_K_M or equivalent",
            "fastest": {
                "max_parameters_billion": round(min(3.0, fastest_b), 1),
                "placement": "mostly or fully GPU-resident",
                "expected": "Best interactivity; weakest model quality.",
            },
            "balanced": {
                "max_parameters_billion": round(max(1.5, balanced_b), 1),
                "placement": "partial GPU offload likely",
                "expected": "Best compromise for normal local use.",
            },
            "maximum_practical": {
                "max_parameters_billion": round(max(3.0, maximum_b), 1),
                "placement": "mostly CPU/RAM",
                "expected": "Should load, but agent loops may be slow.",
            },
            "recommended_context_window": recommended_context,
            "recommended_parallel_requests": 1,
        }

    def _installed_models(self) -> list[dict[str, Any]]:
        try:
            response = httpx.get(
                f"{self.ollama_base_url}/api/tags",
                timeout=4.0,
            )
            response.raise_for_status()
            return response.json().get("models", [])
        except (httpx.HTTPError, ValueError, TypeError):
            return []

    @staticmethod
    def _classify_installed(
        models: list[dict[str, Any]],
        recommendation: dict[str, Any],
    ) -> list[dict[str, Any]]:
        fastest = recommendation["fastest"]["max_parameters_billion"]
        balanced = recommendation["balanced"]["max_parameters_billion"]
        maximum = recommendation["maximum_practical"]["max_parameters_billion"]

        result = []
        for item in models:
            name = item.get("name") or item.get("model") or ""
            parameters = HardwareProfileService._parameter_count(name)
            size = item.get("size")
            if parameters is not None:
                if parameters <= fastest:
                    tier = "fastest"
                elif parameters <= balanced:
                    tier = "balanced"
                elif parameters <= maximum:
                    tier = "maximum_practical"
                else:
                    tier = "not_recommended"
            elif isinstance(size, int):
                # Approximate fallback for Q4-ish model files.
                size_gib = size / _GIB
                tier = (
                    "fastest" if size_gib <= fastest * 0.75
                    else "balanced" if size_gib <= balanced * 0.75
                    else "maximum_practical" if size_gib <= maximum * 0.75
                    else "not_recommended"
                )
            else:
                tier = "unknown"

            result.append(
                {
                    "name": name,
                    "size_bytes": size,
                    "parameters_billion": parameters,
                    "tier": tier,
                }
            )
        return result

    @staticmethod
    def _parameter_count(name: str) -> float | None:
        matches = re.findall(r"(?<!\d)(\d+(?:\.\d+)?)\s*[bB](?![a-zA-Z])", name)
        return float(matches[-1]) if matches else None

    @staticmethod
    def _memory() -> tuple[int, int]:
        if os.name == "nt":
            import ctypes

            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatusEx()
            status.dwLength = ctypes.sizeof(MemoryStatusEx)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                raise OSError("Could not read Windows memory status")
            return int(status.ullTotalPhys), int(status.ullAvailPhys)

        pages = os.sysconf("SC_PHYS_PAGES")
        available = os.sysconf("SC_AVPHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return int(pages * page_size), int(available * page_size)

    @staticmethod
    def _nvidia_gpu() -> GpuInfo | None:
        executable = shutil.which("nvidia-smi")
        if not executable:
            return None
        command = [
            executable,
            "--query-gpu=name,memory.total,memory.free,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits",
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=4,
                check=True,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    if os.name == "nt"
                    else 0
                ),
            )
            first = completed.stdout.strip().splitlines()[0]
            name, total, free, utilization, temperature = [
                part.strip() for part in first.split(",", 4)
            ]
            return GpuInfo(
                name=name,
                memory_total_bytes=int(float(total) * 1024**2),
                memory_free_bytes=int(float(free) * 1024**2),
                utilization_percent=float(utilization),
                temperature_c=float(temperature),
            )
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            return None
