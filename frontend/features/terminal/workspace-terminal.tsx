"use client";

import type { Terminal as XTermTerminal } from "@xterm/xterm";
import type { FitAddon as XTermFitAddon } from "@xterm/addon-fit";
import {
  BotIcon,
  CircleStopIcon,
  LoaderCircleIcon,
  PowerIcon,
  RefreshCwIcon,
  RotateCcwIcon,
  SquareTerminalIcon,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { getActiveWorkspace } from "@/features/workspaces/workspace-api";
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

type ConnectionState =
  | "disconnected"
  | "connecting"
  | "connected";

export function WorkspaceTerminal() {
  const containerRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<XTermTerminal | null>(null);
  const fitAddonRef = useRef<XTermFitAddon | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const currentSessionIdRef = useRef<string | null>(null);

  const [workspace, setWorkspace] = useState<string | null>(null);
  const [diagnostics, setDiagnostics] =
    useState<TerminalDiagnostics | null>(null);
  const [session, setSession] =
    useState<TerminalSession | null>(null);
  const [connection, setConnection] =
    useState<ConnectionState>("disconnected");
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const writeTerminal = useCallback((data: string) => {
    const terminal = terminalRef.current;
    if (!terminal) return;

    terminal.write(data, () => {
      terminal.scrollToBottom();
    });
  }, []);

  const disconnectSocket = useCallback(() => {
    const socket = socketRef.current;
    socketRef.current = null;

    if (
      socket &&
      socket.readyState !== WebSocket.CLOSING &&
      socket.readyState !== WebSocket.CLOSED
    ) {
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

      const terminal = terminalRef.current;
      terminal?.reset();
      terminal?.writeln(
        "\x1b[33m[AI Lab] Connecting to terminal...\x1b[0m",
      );

      const socketUrl = terminalWebSocketUrl(
        nextSession.session_id,
      );
      const socket = new WebSocket(socketUrl);
      socketRef.current = socket;

      socket.onopen = () => {
        if (socketRef.current !== socket) return;

        setConnection("connected");
        setError(null);

        const currentTerminal = terminalRef.current;
        const fitAddon = fitAddonRef.current;

        currentTerminal?.writeln(
          "\x1b[32m[AI Lab] WebSocket connected.\x1b[0m\r\n",
        );

        if (currentTerminal && fitAddon) {
          fitAddon.fit();

          socket.send(
            JSON.stringify({
              type: "resize",
              columns: currentTerminal.cols,
              rows: currentTerminal.rows,
            }),
          );

          currentTerminal.focus();
          currentTerminal.scrollToBottom();
        }
      };

      socket.onmessage = (message) => {
        let event: TerminalSocketEvent;

        try {
          event = JSON.parse(
            String(message.data),
          ) as TerminalSocketEvent;
        } catch {
          writeTerminal(String(message.data));
          return;
        }

        if (event.type === "snapshot") {
          setSession(event.session);

          if (event.output) {
            writeTerminal(event.output);
          }

          return;
        }

        if (event.type === "output") {
          writeTerminal(event.data);
          return;
        }

        if (
          event.type === "session_exited" ||
          event.type === "session_closed"
        ) {
          setSession(event.session);

          if (event.error) {
            setError(event.error);
            terminalRef.current?.writeln(
              `\r\n\x1b[31m[AI Lab] ${event.error}\x1b[0m`,
            );
          }

          return;
        }

        if (event.type === "error") {
          setError(event.error);
          terminalRef.current?.writeln(
            `\r\n\x1b[31m[AI Lab] ${event.error}\x1b[0m`,
          );
        }
      };

      socket.onerror = () => {
        if (socketRef.current !== socket) return;

        const message =
          `Terminal WebSocket failed: ${socketUrl}`;

        setError(message);
        terminalRef.current?.writeln(
          `\r\n\x1b[31m[AI Lab] ${message}\x1b[0m`,
        );
      };

      socket.onclose = (event) => {
        if (socketRef.current !== socket) return;

        socketRef.current = null;
        setConnection("disconnected");

        terminalRef.current?.writeln(
          `\r\n\x1b[33m[AI Lab] WebSocket closed (${event.code}) ${event.reason}\x1b[0m`,
        );
      };
    },
    [disconnectSocket, writeTerminal],
  );

  const refreshState = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [
        workspaceResult,
        diagnosticsResult,
        sessionsResult,
      ] = await Promise.all([
        getActiveWorkspace(),
        getTerminalDiagnostics(),
        listTerminalSessions(),
      ]);

      setWorkspace(workspaceResult.workspace);
      setDiagnostics(diagnosticsResult);

      const matching = sessionsResult.sessions.find(
        (candidate) =>
          candidate.workspace === workspaceResult.workspace &&
          candidate.status === "running",
      );

      if (
        matching &&
        matching.session_id !== currentSessionIdRef.current
      ) {
        connectToSession(matching);
      }

      if (!matching && currentSessionIdRef.current) {
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
      try {
        const [{ Terminal }, { FitAddon }] =
          await Promise.all([
            import("@xterm/xterm"),
            import("@xterm/addon-fit"),
          ]);

        if (disposed || !containerRef.current) return;

        const terminal = new Terminal({
          cursorBlink: true,
          cursorStyle: "bar",
          fontFamily:
            '"Cascadia Code", "Cascadia Mono", Consolas, monospace',
          fontSize: 14,
          lineHeight: 1.2,
          scrollback: 10_000,
          convertEol: false,
          theme: {
            background: "#09090b",
            foreground: "#e4e4e7",
            cursor: "#a78bfa",
            selectionBackground: "#3f3f46",
          },
        });

        const fitAddon = new FitAddon();
        terminal.loadAddon(fitAddon);
        terminal.open(containerRef.current);

        terminalRef.current = terminal;
        fitAddonRef.current = fitAddon;

        requestAnimationFrame(() => {
          if (disposed) return;
          fitAddon.fit();
          terminal.focus();
          terminal.writeln(
            "\x1b[36mAI Lab Workspace Terminal\x1b[0m",
          );
          terminal.writeln(
            "Start a terminal session using the button above.\r\n",
          );
        });

        inputDisposable = terminal.onData((data) => {
          const socket = socketRef.current;

          if (
            !socket ||
            socket.readyState !== WebSocket.OPEN
          ) {
            setError(
              "Terminal input cannot be sent because the WebSocket is disconnected.",
            );
            return;
          }

          socket.send(
            JSON.stringify({
              type: "input",
              data,
            }),
          );
        });

        resizeObserver = new ResizeObserver(() => {
          requestAnimationFrame(() => {
            if (
              disposed ||
              !terminalRef.current ||
              !fitAddonRef.current
            ) {
              return;
            }

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
      } catch (mountError) {
        setError(
          mountError instanceof Error
            ? `xterm failed to mount: ${mountError.message}`
            : "xterm failed to mount.",
        );
      }
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

  async function runAction(
    name: string,
    operation: () => Promise<void>,
  ) {
    setAction(name);
    setError(null);

    try {
      await operation();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The action failed.",
      );
    } finally {
      setAction(null);
    }
  }

  const sessionRunning = session?.status === "running";
  const terminalConnected =
    sessionRunning && connection === "connected";
  const terminalReady =
    Boolean(workspace) &&
    Boolean(diagnostics?.supported) &&
    Boolean(diagnostics?.pywinpty_installed);

  function dimensions() {
    return {
      columns:
        terminalRef.current?.cols ?? DEFAULT_COLUMNS,
      rows: terminalRef.current?.rows ?? DEFAULT_ROWS,
    };
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-background">
      <div className="border-b border-border bg-surface px-4 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <SquareTerminalIcon className="size-5" />
          <h1 className="mr-auto text-base font-semibold">
            Workspace Terminal
          </h1>

          <span className="rounded border border-border px-2 py-1 text-xs">
            {session?.status ?? "idle"} / {connection}
          </span>

          <Button
            label="Refresh"
            icon={RefreshCwIcon}
            busy={loading || action === "refresh"}
            onClick={() =>
              void runAction("refresh", refreshState)
            }
          />

          <Button
            label={
              sessionRunning
                ? "Restart terminal"
                : "Start terminal"
            }
            icon={PowerIcon}
            primary
            busy={action === "start"}
            disabled={!terminalReady}
            onClick={() =>
              void runAction("start", async () => {
                if (session) {
                  try {
                    await closeTerminal(session.session_id);
                  } catch {
                    // Ignore an already-closed session.
                  }
                }

                disconnectSocket();
                currentSessionIdRef.current = null;
                setSession(null);

                const result =
                  await createTerminalSession({
                    shell: "auto",
                    ...dimensions(),
                  });

                connectToSession(result.session);
              })
            }
          />
        </div>

        <div className="mt-3 grid gap-2 text-xs md:grid-cols-3">
          <Info
            label="Workspace"
            value={workspace ?? "No workspace selected"}
          />
          <Info
            label="PowerShell"
            value={
              diagnostics?.shells.pwsh ??
              diagnostics?.shells.powershell ??
              "Not found"
            }
          />
          <Info
            label="Claude Code"
            value={
              diagnostics?.claude.available
                ? diagnostics.claude.path ?? "Available"
                : "Not installed"
            }
          />
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3 p-4">
        {error ? (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
            {error}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button
            label="Start Claude"
            icon={BotIcon}
            primary
            busy={action === "claude-new"}
            disabled={
              !terminalConnected ||
              !diagnostics?.claude.available
            }
            onClick={() =>
              void runAction("claude-new", async () => {
                if (!session) return;

                const result = await launchClaude(
                  session.session_id,
                  { mode: "new" },
                );

                setSession(result.session);
                terminalRef.current?.focus();
              })
            }
          />

          <Button
            label="Continue Claude"
            icon={RotateCcwIcon}
            busy={action === "claude-continue"}
            disabled={
              !terminalConnected ||
              !diagnostics?.claude.available
            }
            onClick={() =>
              void runAction(
                "claude-continue",
                async () => {
                  if (!session) return;

                  const result = await launchClaude(
                    session.session_id,
                    { mode: "continue" },
                  );

                  setSession(result.session);
                  terminalRef.current?.focus();
                },
              )
            }
          />

          <Button
            label="Ctrl+C"
            icon={CircleStopIcon}
            busy={action === "interrupt"}
            disabled={!terminalConnected}
            onClick={() =>
              void runAction("interrupt", async () => {
                if (!session) return;
                setSession(
                  await interruptTerminal(
                    session.session_id,
                  ),
                );
                terminalRef.current?.focus();
              })
            }
          />

          <Button
            label="Reconnect"
            icon={RefreshCwIcon}
            disabled={
              !sessionRunning ||
              connection === "connected"
            }
            busy={connection === "connecting"}
            onClick={() => {
              if (session) connectToSession(session);
            }}
          />

          <Button
            label="Kill terminal"
            icon={PowerIcon}
            danger
            busy={action === "close"}
            disabled={!session}
            onClick={() =>
              void runAction("close", async () => {
                if (!session) return;

                await closeTerminal(session.session_id);
                disconnectSocket();
                currentSessionIdRef.current = null;
                setSession(null);
                terminalRef.current?.reset();
                terminalRef.current?.writeln(
                  "\x1b[33m[AI Lab] Terminal closed.\x1b[0m",
                );
              })
            }
          />
        </div>

        <div className="relative min-h-[32rem] flex-1 overflow-hidden rounded-xl border border-zinc-800 bg-[#09090b]">
          <div
            ref={containerRef}
            className="absolute inset-0 overflow-hidden p-3 [&_.xterm]:h-full [&_.xterm-viewport]:overflow-y-auto"
            tabIndex={0}
            onClick={() => terminalRef.current?.focus()}
          />
        </div>
      </div>
    </div>
  );
}

function Info({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="min-w-0 rounded-lg border border-border px-3 py-2">
      <div className="text-muted-foreground">{label}</div>
      <div
        className="truncate font-mono text-foreground"
        title={value}
      >
        {value}
      </div>
    </div>
  );
}

function Button({
  label,
  icon: Icon,
  onClick,
  busy = false,
  disabled = false,
  primary = false,
  danger = false,
}: {
  label: string;
  icon: typeof PowerIcon;
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
      className={[
        "inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium",
        "disabled:cursor-not-allowed disabled:opacity-40",
        primary
          ? "border-accent bg-accent text-accent-foreground"
          : danger
            ? "border-red-500/30 bg-red-500/10 text-red-400"
            : "border-border bg-surface text-foreground",
      ].join(" ")}
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
