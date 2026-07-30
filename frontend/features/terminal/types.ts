export type TerminalStatus = "running" | "closing" | "closed" | "exited" | "error";

export type TerminalSession = {
  session_id: string;
  workspace: string;
  shell: string;
  shell_path: string;
  status: TerminalStatus;
  agent: string | null;
  columns: number;
  rows: number;
  created_at: string;
  last_activity_at: string;
  exit_code: number | null;
};

export type TerminalDiagnostics = {
  platform: string;
  supported: boolean;
  pywinpty_installed: boolean;
  shells: {
    pwsh: string | null;
    powershell: string | null;
  };
  claude: {
    available: boolean;
    path: string | null;
  };
  loopback_only: boolean;
};

export type CreateTerminalSessionResponse = {
  session: TerminalSession;
  reused: boolean;
};

export type ListTerminalSessionsResponse = {
  sessions: TerminalSession[];
};

export type LaunchClaudeResponse = {
  session: TerminalSession;
  command: string;
};

export type TerminalSocketEvent =
  | {
      type: "snapshot";
      session: TerminalSession;
      output: string;
    }
  | {
      type: "output";
      data: string;
    }
  | {
      type: "session_exited" | "session_closed";
      session: TerminalSession;
      error?: string;
    }
  | {
      type: "error";
      error: string;
    }
  | {
      type: "pong";
    };
