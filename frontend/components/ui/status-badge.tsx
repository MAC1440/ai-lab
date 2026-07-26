import { cn } from "@/lib/utils";

export type StatusTone = "success" | "danger" | "pending" | "neutral";

const toneClasses: Record<StatusTone, string> = {
  success: "bg-success/10 text-success border-success/30",
  danger: "bg-danger/10 text-danger border-danger/30",
  pending: "bg-pending/10 text-pending border-pending/30",
  neutral:
    "bg-muted-foreground/10 text-muted-foreground border-border-strong",
};

const dotClasses: Record<StatusTone, string> = {
  success: "bg-success",
  danger: "bg-danger",
  pending: "bg-pending animate-pulse",
  neutral: "bg-muted-foreground",
};

/**
 * The app's signature status indicator — a small "gauge light" used
 * anywhere a verification, benchmark, or run reports its state.
 * Kept to one shared component so every passed/failed/running badge
 * in the app looks identical instead of ad hoc colored pills.
 */
export function StatusBadge({
  tone,
  children,
  className,
}: {
  tone: StatusTone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[11px] font-medium tracking-wide",
        toneClasses[tone],
        className,
      )}
    >
      <span
        className={cn("size-1.5 shrink-0 rounded-full", dotClasses[tone])}
        aria-hidden="true"
      />
      {children}
    </span>
  );
}
