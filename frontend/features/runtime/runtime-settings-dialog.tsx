"use client";

import {
  CpuIcon,
  GaugeIcon,
  Loader2Icon,
  RefreshCwIcon,
  SaveIcon,
  SparklesIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  autoConfigureRuntime,
  getHardwareSnapshot,
  getRuntimeSettings,
  saveRuntimeSettings,
  type HardwareSnapshot,
  type RuntimeSettings,
  type RuntimeStageSettings,
} from "./runtime-api";

const stages = ["chat", "planning", "generation", "repair"] as const;
type Stage = (typeof stages)[number];

function gib(bytes: number | null | undefined) {
  return bytes == null ? "Unknown" : `${(bytes / 1024 ** 3).toFixed(1)} GB`;
}

function StageEditor({
  stage,
  value,
  onChange,
}: {
  stage: Stage;
  value: RuntimeStageSettings;
  onChange: (next: RuntimeStageSettings) => void;
}) {
  const field = (
    key: keyof RuntimeStageSettings,
    label: string,
    step = 1,
  ) => (
    <div className="space-y-1">
      <Label htmlFor={`${stage}-${key}`}>{label}</Label>
      <Input
        id={`${stage}-${key}`}
        type="number"
        step={step}
        value={value[key]}
        onChange={(event) =>
          onChange({
            ...value,
            [key]: Number(event.target.value),
          })
        }
      />
    </div>
  );

  const available =
    value.num_ctx - value.max_tokens - value.reserve_tokens;

  return (
    <section className="rounded-xl border p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-semibold capitalize">{stage}</h3>
        <span className="text-xs text-muted-foreground">
          Safe input: {available.toLocaleString()} tokens
        </span>
      </div>
      <div className="grid gap-3 sm:grid-cols-4">
        {field("num_ctx", "Context window")}
        {field("max_tokens", "Max output")}
        {field("reserve_tokens", "Reserved")}
        {field("temperature", "Temperature", 0.05)}
      </div>
    </section>
  );
}

export function RuntimeSettingsDialog() {
  const [open, setOpen] = useState(false);
  const [hardware, setHardware] = useState<HardwareSnapshot | null>(null);
  const [settings, setSettings] = useState<RuntimeSettings | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setWorking(true);
    setError(null);
    try {
      const [hardwareResult, settingsResult] = await Promise.all([
        getHardwareSnapshot(),
        getRuntimeSettings(),
      ]);
      setHardware(hardwareResult);
      setSettings(settingsResult);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not load runtime data.",
      );
    } finally {
      setWorking(false);
    }
  }

  useEffect(() => {
    if (!open) return;

    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [open]);

  async function applyAutomatic() {
    setWorking(true);
    setError(null);
    try {
      setSettings(await autoConfigureRuntime());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Auto setup failed.");
    } finally {
      setWorking(false);
    }
  }

  async function save() {
    if (!settings) return;
    setWorking(true);
    setError(null);
    try {
      setSettings(
        await saveRuntimeSettings({ ...settings, automatic: false }),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Save failed.");
    } finally {
      setWorking(false);
    }
  }

  function updateStage(stage: Stage, value: RuntimeStageSettings) {
    setSettings((current) =>
      current ? { ...current, [stage]: value } : current,
    );
  }

  const recommendation = hardware?.recommendation;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" size="sm" variant="outline">
          <GaugeIcon className="mr-2 size-4" />
          Runtime
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] max-w-5xl overflow-y-auto">
        <DialogTitle>Hardware and model runtime</DialogTitle>
        <DialogDescription>
          Inspect local hardware, choose a practical model size and control
          context/output limits for every AI Lab stage.
        </DialogDescription>

        {working && !hardware ? (
          <div className="flex justify-center p-10">
            <Loader2Icon className="size-6 animate-spin" />
          </div>
        ) : null}

        {hardware ? (
          <>
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-xl border p-4">
                <CpuIcon className="mb-2 size-5" />
                <p className="font-medium">{hardware.platform.processor}</p>
                <p className="text-xs text-muted-foreground">
                  {hardware.cpu.logical_cores} logical cores
                </p>
              </div>
              <div className="rounded-xl border p-4">
                <p className="font-medium">System memory</p>
                <p className="text-xl font-semibold">
                  {gib(hardware.memory.total_bytes)}
                </p>
                <p className="text-xs text-muted-foreground">
                  {gib(hardware.memory.available_bytes)} currently available
                </p>
              </div>
              <div className="rounded-xl border p-4">
                <p className="font-medium">
                  {hardware.gpu?.name ?? "No NVIDIA GPU detected"}
                </p>
                <p className="text-xl font-semibold">
                  {gib(hardware.gpu?.memory_total_bytes)}
                </p>
                <p className="text-xs text-muted-foreground">
                  {hardware.gpu?.utilization_percent ?? "—"}% GPU ·{" "}
                  {hardware.gpu?.temperature_c ?? "—"}°C
                </p>
              </div>
            </div>

            {recommendation ? (
              <div className="grid gap-3 md:grid-cols-3">
                {(
                  [
                    ["Fastest", recommendation.fastest],
                    ["Balanced", recommendation.balanced],
                    ["Maximum practical", recommendation.maximum_practical],
                  ] as const
                ).map(([title, band]) => (
                  <div key={title} className="rounded-xl border p-4">
                    <p className="text-sm font-medium">{title}</p>
                    <p className="mt-1 text-2xl font-bold">
                      ≤ {band.max_parameters_billion}B
                    </p>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {band.placement}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {band.expected}
                    </p>
                  </div>
                ))}
              </div>
            ) : null}

            {hardware.installed_models.length ? (
              <div className="rounded-xl border p-4">
                <p className="mb-2 font-medium">Installed Ollama models</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {hardware.installed_models.map((model) => (
                    <div
                      key={model.name}
                      className="flex justify-between rounded-lg bg-muted/50 p-2 text-sm"
                    >
                      <span className="truncate">{model.name}</span>
                      <span className="ml-3 capitalize text-muted-foreground">
                        {model.tier.replace("_", " ")}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </>
        ) : null}

        {settings ? (
          <div className="space-y-3">
            {stages.map((stage) => (
              <StageEditor
                key={stage}
                stage={stage}
                value={settings[stage]}
                onChange={(value) => updateStage(stage, value)}
              />
            ))}
          </div>
        ) : null}

        {error ? (
          <div className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
            {error}
          </div>
        ) : null}

        <div className="flex flex-wrap justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => void load()}>
            <RefreshCwIcon className="mr-2 size-4" />
            Refresh hardware
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={working}
            onClick={() => void applyAutomatic()}
          >
            <SparklesIcon className="mr-2 size-4" />
            Auto configure
          </Button>
          <Button
            type="button"
            disabled={!settings || working}
            onClick={() => void save()}
          >
            {working ? (
              <Loader2Icon className="mr-2 size-4 animate-spin" />
            ) : (
              <SaveIcon className="mr-2 size-4" />
            )}
            Save
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
