"use client";

import { ActivityIcon, RefreshCwIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  getRuntimeMetrics,
  type RuntimeMetricsSnapshot,
} from "./runtime-api";

export function RuntimeMetricsCard() {
  const [snapshot, setSnapshot] = useState<RuntimeMetricsSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setSnapshot(await getRuntimeMetrics());
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Metrics failed.");
    }
  }

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(timer);
  }, []);

  const latest = snapshot?.latest;
  if (!latest) {
    return (
      <div className="rounded-xl border p-4 text-sm text-muted-foreground">
        <ActivityIcon className="mb-2 size-5" />
        Runtime metrics will appear after the next model stage completes.
      </div>
    );
  }

  const usedPercent = Math.min(
    100,
    Math.round((latest.context_used_tokens / latest.context_window) * 100),
  );

  return (
    <div className="space-y-3 rounded-xl border p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium">
            {latest.model} · {latest.stage}
          </p>
          <p className="text-xs text-muted-foreground">
            {latest.provider_id} · {latest.duration_seconds.toFixed(2)} seconds
          </p>
        </div>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          onClick={() => void refresh()}
        >
          <RefreshCwIcon className="size-4" />
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric
          label="Generation speed"
          value={
            latest.tokens_per_second == null
              ? "—"
              : `${latest.tokens_per_second} tok/s`
          }
        />
        <Metric label="Input" value={`${latest.input_tokens} tokens`} />
        <Metric label="Output" value={`${latest.output_tokens} tokens`} />
        <Metric
          label="Temperature"
          value={latest.temperature.toFixed(2)}
        />
      </div>

      <div>
        <div className="mb-1 flex justify-between text-xs">
          <span>Context used</span>
          <span>
            {latest.context_used_tokens.toLocaleString()} /{" "}
            {latest.context_window.toLocaleString()} tokens
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded bg-muted">
          <div
            className="h-full rounded bg-primary"
            style={{ width: `${usedPercent}%` }}
          />
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {latest.context_remaining_tokens.toLocaleString()} tokens remain in
          the configured context window. Maximum output is{" "}
          {latest.max_tokens.toLocaleString()}.
        </p>
      </div>

      {error ? <p className="text-xs text-red-600">{error}</p> : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-muted/50 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-semibold">{value}</p>
    </div>
  );
}
