"use client";

import type { Terminal as XTermTerminal } from "@xterm/xterm";
import type { FitAddon as XTermFitAddon } from "@xterm/addon-fit";
import {
  AlertTriangleIcon,
  BotIcon,
  CircleStopIcon,
  CommandIcon,
  LoaderCircleIcon,
  PowerIcon,
  RefreshCwIcon,
  RotateCcwIcon,
  ShieldAlertIcon,
  SquareTerminalIcon,
  UnplugIcon,
  XIcon,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { getActiveWorkspace } from "@/features/workspaces/workspace-api";
import { cn } from "@/lib/utils";
import {
  closeTerminal,
  createTerminalSession,
  getTerminalDiagnostics,
  interruptTerminal,
  launchClaude,
  listTerminalSessions,
  terminalWebSocketUrl,
} from "./terminal-api";
import type {
  TerminalDiagnostics,
  TerminalSession,
  TerminalSocketEvent,
} from "./types";

const DEFAULT_COLUMNS = 120;
const DEFAULT_ROWS = 32;

export function WorkspaceTerminal() {
  const containerRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<XTermTerminal | null>(null);
  const fitAddonRef = useRef<XTermFitAddon | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const pendingOutputRef = useRef<string[]>([]);
  const currentSessionIdRef = useRef<string | null>(null);

  const [workspace, setWorkspace] = useState<string | null>(null);
  const [diagnostics, setDiagnostics] = useState<TerminalDiagnostics | null>(null);
  const [session, setSession] = useState<TerminalSession | null>(null);
  const [connection, setConnection] = useState<
    "disconnected" | "connecting" | "connected"
  >("disconnected");
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const writeTerminal = useCallback((data: string) => {
    const terminal = terminalRef.current;
    if (terminal) {
      terminal.write(data);
    } else {
      pendingOutputRef.current.push(data);
    }
  }, []);

  const disconnectSocket = useCallback(() => {
    const socket = socketRef.current;
    socketRef.current = null;
    if (socket && socket.readyState <= WebSocket.OPEN) {
      socket.close();
    }
    setConnection("disconnected");
  }, []);

  const connectToSession = useCallback(
    (nextSession: TerminalSession) => {
      disconnectSocket();
      currentSessionIdRef.current = nextSession.session_id;
      setSession(nextSession);
      setConnection("connecting");
      setError(null);

      const socket = new WebSocket(terminalWebSocketUrl(nextSession.session_id));
      socketRef.current = socket;

      socket.onopen = () => {
        if (socketRef.current !== socket) return;
        setConnection("connected");
        const fitAddon = fitAddonRef.current;
        const terminal = terminalRef.current;
        if (fitAddon && terminal) {
          fitAddon.fit();
          socket.send(
            JSON.stringify({
              type: "resize",
              columns: terminal.cols,
              rows: terminal.rows,
            }),
          );
          terminal.focus();
        }
      };

      socket.onmessage = (message) => {
        let event: TerminalSocketEvent;
        try {
          event = JSON.parse(message.data) as TerminalSocketEvent;
        } catch {
          writeTerminal(String(message.data));
          return;
        }

        if (event.type === "snapshot") {
          terminalRef.current?.reset();
          setSession(event.session);
          if (event.output) writeTerminal(event.output);
          return;
        }
        if (event.type === "output") {
          writeTerminal(event.data);
          return;
        }
        if (event.type === "session_exited" || event.type === "session_closed") {
          setSession(event.session);
          if (event.error) setError(event.error);
          return;
        }
        if (event.type === "error") {
          setError(event.error);
        }
      };

      socket.onerror = () => {
        if (socketRef.current === socket) {
          setError("The terminal WebSocket could not connect to the backend.");
        }
      };

      socket.onclose = () => {
        if (socketRef.current === socket) {
          socketRef.current = null;
          setConnection("disconnected");
        }
      };
    },
    [disconnectSocket, writeTerminal],
  );

  const refreshState = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [workspaceResult, diagnosticsResult, sessionsResult] = await Promise.all([
        getActiveWorkspace(),
        getTerminalDiagnostics(),
        listTerminalSessions(),
      ]);
      setWorkspace(workspaceResult.workspace);
      setDiagnostics(diagnosticsResult);

      const matching = sessionsResult.sessions.find(
        (candidate) => candidate.workspace === workspaceResult.workspace,
      );
      if (matching && matching.session_id !== currentSessionIdRef.current) {
        connectToSession(matching);
      } else if (!matching && currentSessionIdRef.current) {
        currentSessionIdRef.current = null;
        setSession(null);
        disconnectSocket();
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Terminal state could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, [connectToSession, disconnectSocket]);

  useEffect(() => {
    let disposed = false;
    let resizeObserver: ResizeObserver | null = null;
    let inputDisposable: { dispose(): void } | null = null;

    async function mountTerminal() {
      const [{ Terminal }, { FitAddon }] = await Promise.all([
        import("@xterm/xterm"),
        import("@xterm/addon-fit"),
      ]);
      if (disposed || !containerRef.current) return;

      const terminal = new Terminal({
        cursorBlink: true,
        cursorStyle: "bar",
        fontFamily:
          '"Cascadia Code", "Cascadia Mono", Consolas, "Courier New", monospace',
        fontSize: 13,
        lineHeight: 1.2,
        scrollback: 10_000,
        allowProposedApi: false,
        convertEol: false,
        theme: {
          background: "#09090b",
          foreground: "#e4e4e7",
          cursor: "#a78bfa",
          selectionBackground: "#3f3f46",
          black: "#18181b",
          red: "#f87171",
          green: "#4ade80",
          yellow: "#facc15",
          blue: "#60a5fa",
          magenta: "#c084fc",
          cyan: "#22d3ee",
          white: "#f4f4f5",
          brightBlack: "#71717a",
          brightRed: "#fca5a5",
          brightGreen: "#86efac",
          brightYellow: "#fde047",
          brightBlue: "#93c5fd",
          brightMagenta: "#d8b4fe",
          brightCyan: "#67e8f9",
          brightWhite: "#ffffff",
        },
      });
      const fitAddon = new FitAddon();
      terminal.loadAddon(fitAddon);
      terminal.open(containerRef.current);
      terminalRef.current = terminal;
      fitAddonRef.current = fitAddon;
      fitAddon.fit();

      if (pendingOutputRef.current.length) {
        terminal.write(pendingOutputRef.current.join(""));
        pendingOutputRef.current = [];
      }

      inputDisposable = terminal.onData((data) => {
        const socket = socketRef.current;
        if (socket?.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: "input", data }));
        }
      });

      resizeObserver = new ResizeObserver(() => {
        requestAnimationFrame(() => {
          if (disposed || !terminalRef.current || !fitAddonRef.current) return;
          fitAddonRef.current.fit();
          const socket = socketRef.current;
          if (socket?.readyState === WebSocket.OPEN) {
            socket.send(
              JSON.stringify({
                type: "resize",
                columns: terminalRef.current.cols,
                rows: terminalRef.current.rows,
              }),
            );
          }
        });
      });
      resizeObserver.observe(containerRef.current);
      terminal.focus();
    }

    void mountTerminal();
    void refreshState();

    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      inputDisposable?.dispose();
      disconnectSocket();
      terminalRef.current?.dispose();
      terminalRef.current = null;
      fitAddonRef.current = null;
    };
  }, [disconnectSocket, refreshState]);

  async function runAction(name: string, operation: () => Promise<void>) {
    setAction(name);
    setError(null);
    try {
      await operation();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "The action failed.",
      );
    } finally {
      setAction(null);
    }
  }

  function currentDimensions() {
    return {
      columns: terminalRef.current?.cols ?? DEFAULT_COLUMNS,
      rows: terminalRef.current?.rows ?? DEFAULT_ROWS,
    };
  }

  const sessionRunning = session?.status === "running";
  const terminalReady =
    Boolean(workspace) &&
    Boolean(diagnostics?.supported) &&
    Boolean(diagnostics?.pywinpty_installed);

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-background">
      <div className="border-b border-border bg-surface px-4 py-4 sm:px-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <SquareTerminalIcon className="size-5 text-accent" />
              <h2 className="text-base font-semibold text-foreground">
                Workspace Terminal
              </h2>
              <StatusBadge connection={connection} status={session?.status} />
            </div>
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-muted-foreground">
              A direct PowerShell session in the selected workspace. Claude Code runs
              here exactly as it does in an external terminal and can edit files or run
              commands without AI Lab&apos;s proposal safeguards.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <ActionButton
              icon={RefreshCwIcon}
              label="Refresh"
              busy={action === "refresh" || loading}
              onClick={() => void runAction("refresh", refreshState)}
            />
            {!sessionRunning ? (
              <ActionButton
                primary
                icon={PowerIcon}
                label={session ? "Restart terminal" : "Start terminal"}
                busy={action === "start"}
                disabled={!terminalReady}
                onClick={() =>
                  void runAction("start", async () => {
                    if (session) {
                      try {
                        await closeTerminal(session.session_id);
                      } catch {
                        // An exited server-side session may already be gone.
                      }
                    }
                    const result = await createTerminalSession({
                      shell: "auto",
                      ...currentDimensions(),
                    });
                    currentSessionIdRef.current = result.session.session_id;
                    connectToSession(result.session);
                  })
                }
              />
            ) : null}
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <InfoCard
            label="Selected workspace"
            value={workspace ?? "No workspace selected"}
            healthy={Boolean(workspace)}
          />
          <InfoCard
            label="Terminal runtime"
            value={terminalRuntimeLabel(diagnostics)}
            healthy={Boolean(diagnostics?.supported && diagnostics.pywinpty_installed)}
          />
          <InfoCard
            label="Claude Code"
            value={diagnostics?.claude.available ? diagnostics.claude.path ?? "Available" : "Not found on PATH"}
            healthy={Boolean(diagnostics?.claude.available)}
          />
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3 p-3 sm:p-4">
        {error ? (
          <div className="flex items-start gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-xs text-danger">
            <AlertTriangleIcon className="mt-0.5 size-4 shrink-0" />
            <span className="min-w-0 flex-1 break-words">{error}</span>
            <button type="button" onClick={() => setError(null)} aria-label="Dismiss error">
              <XIcon className="size-4" />
            </button>
          </div>
        ) : null}

        {!workspace ? (
          <EmptyState
            icon={UnplugIcon}
            title="Select a workspace first"
            description="Use AI Lab's existing workspace picker, then return here and refresh. New terminal sessions always start in that selected directory."
          />
        ) : !diagnostics?.supported || !diagnostics?.pywinpty_installed ? (
          <EmptyState
            icon={ShieldAlertIcon}
            title="Terminal runtime is not ready"
            description={
              diagnostics?.supported
                ? "Install backend requirements so pywinpty can create the Windows ConPTY session."
                : "This drop currently enables the embedded terminal on Windows only."
            }
          />
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-surface px-3 py-2">
              <ActionButton
                primary
                icon={BotIcon}
                label="Start Claude"
                busy={action === "claude-new"}
                disabled={!sessionRunning || !diagnostics.claude.available}
                onClick={() =>
                  void runAction("claude-new", async () => {
                    if (!session) return;
                    const result = await launchClaude(session.session_id, { mode: "new" });
                    setSession(result.session);
                    terminalRef.current?.focus();
                  })
                }
              />
              <ActionButton
                icon={RotateCcwIcon}
                label="Continue Claude"
                busy={action === "claude-continue"}
                disabled={!sessionRunning || !diagnostics.claude.available}
                onClick={() =>
                  void runAction("claude-continue", async () => {
                    if (!session) return;
                    const result = await launchClaude(session.session_id, {
                      mode: "continue",
                    });
                    setSession(result.session);
                    terminalRef.current?.focus();
                  })
                }
              />
              <ActionButton
                icon={CircleStopIcon}
                label="Ctrl+C"
                busy={action === "interrupt"}
                disabled={!sessionRunning}
                onClick={() =>
                  void runAction("interrupt", async () => {
                    if (!session) return;
                    setSession(await interruptTerminal(session.session_id));
                    terminalRef.current?.focus();
                  })
                }
              />
              <ActionButton
                danger
                icon={PowerIcon}
                label="Kill terminal"
                busy={action === "close"}
                disabled={!session}
                onClick={() => {
                  if (!session) return;
                  const confirmed = window.confirm(
                    "Kill this PowerShell session and all processes running inside it?",
                  );
                  if (!confirmed) return;
                  void runAction("close", async () => {
                    await closeTerminal(session.session_id);
                    disconnectSocket();
                    currentSessionIdRef.current = null;
                    setSession(null);
                    terminalRef.current?.reset();
                  });
                }}
              />

              <div className="ml-auto hidden min-w-0 items-center gap-2 text-[11px] text-muted-foreground md:flex">
                <CommandIcon className="size-3.5" />
                <span className="max-w-[28rem] truncate">
                  {session
                    ? `${session.shell} · ${session.workspace}`
                    : "Terminal has not been started"}
                </span>
              </div>
            </div>

            <div className="relative min-h-[28rem] flex-1 overflow-hidden rounded-xl border border-zinc-800 bg-[#09090b] shadow-inner">
              {!session ? (
                <div className="absolute inset-0 z-10 flex items-center justify-center bg-[#09090b]/92 p-6 text-center">
                  <div>
                    <SquareTerminalIcon className="mx-auto size-8 text-zinc-600" />
                    <p className="mt-3 text-sm font-medium text-zinc-300">
                      Start the terminal to open PowerShell
                    </p>
                    <p className="mt-1 text-xs text-zinc-500">
                      It will launch in the currently selected workspace.
                    </p>
                  </div>
                </div>
              ) : null}
              <div
                ref={containerRef}
                className="h-full min-h-[28rem] w-full p-3"
                onClick={() => terminalRef.current?.focus()}
              />
            </div>

            <div className="flex items-start gap-2 rounded-lg border border-warning/25 bg-warning/8 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground">
              <ShieldAlertIcon className="mt-0.5 size-3.5 shrink-0 text-warning" />
              <span>
                This is an unrestricted local shell. Claude Code can directly modify,
                delete, commit, install, or execute anything permitted by your Windows
                account. AI Lab does not intercept those operations.
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function StatusBadge({
  connection,
  status,
}: {
  connection: "disconnected" | "connecting" | "connected";
  status?: TerminalSession["status"];
}) {
  const label = status === "running" ? connection : status ?? "idle";
  const healthy = status === "running" && connection === "connected";
  return (
    <span
      className={cn(
        "rounded-full border px-2 py-0.5 text-[10px] font-medium capitalize",
        healthy
          ? "border-success/30 bg-success/10 text-success"
          : connection === "connecting"
            ? "border-warning/30 bg-warning/10 text-warning"
            : "border-border bg-surface-hover text-muted-foreground",
      )}
    >
      {label}
    </span>
  );
}

function InfoCard({
  label,
  value,
  healthy,
}: {
  label: string;
  value: string;
  healthy: boolean;
}) {
  return (
    <div className="min-w-0 rounded-xl border border-border bg-surface-hover/60 px-3 py-2.5">
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "size-2 shrink-0 rounded-full",
            healthy ? "bg-success" : "bg-warning",
          )}
        />
        <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
      </div>
      <p className="mt-1 truncate font-mono text-[11px] text-foreground" title={value}>
        {value}
      </p>
    </div>
  );
}

function ActionButton({
  icon: Icon,
  label,
  onClick,
  busy = false,
  disabled = false,
  primary = false,
  danger = false,
}: {
  icon: typeof PowerIcon;
  label: string;
  onClick: () => void;
  busy?: boolean;
  disabled?: boolean;
  primary?: boolean;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || busy}
      className={cn(
        "inline-flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-45",
        primary
          ? "border-accent bg-accent text-accent-foreground hover:bg-accent-hover"
          : danger
            ? "border-danger/30 bg-danger/10 text-danger hover:bg-danger/15"
            : "border-border bg-surface text-muted-foreground hover:bg-surface-hover hover:text-foreground",
      )}
    >
      {busy ? (
        <LoaderCircleIcon className="size-3.5 animate-spin" />
      ) : (
        <Icon className="size-3.5" />
      )}
      {label}
    </button>
  );
}

function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof UnplugIcon;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-1 items-center justify-center p-8 text-center">
      <div className="max-w-lg rounded-2xl border border-border bg-surface p-8 shadow-sm">
        <Icon className="mx-auto size-9 text-muted-foreground" />
        <h3 className="mt-4 text-sm font-semibold text-foreground">{title}</h3>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          {description}
        </p>
      </div>
    </div>
  );
}

function terminalRuntimeLabel(diagnostics: TerminalDiagnostics | null): string {
  if (!diagnostics) return "Checking runtime…";
  if (!diagnostics.supported) return `Unsupported platform: ${diagnostics.platform}`;
  if (!diagnostics.pywinpty_installed) return "pywinpty is not installed";
  return diagnostics.shells.pwsh ?? diagnostics.shells.powershell ?? "PowerShell not found";
}
