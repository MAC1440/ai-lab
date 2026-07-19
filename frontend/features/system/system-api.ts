const API_BASE_URL =
    process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export type SystemCheck = {
    id: string;
    name: string;
    status: "pass" | "warning" | "fail";
    message: string;
    action: string | null;
};

export type SystemDiagnostics = {
    status: "ready" | "attention" | "blocked";
    generated_at: string;
    summary: { passed: number; warnings: number; failed: number };
    checks: SystemCheck[];
};

export async function getSystemDiagnostics(): Promise<SystemDiagnostics> {
    const response = await fetch(`${API_BASE_URL}/system/diagnostics`, {
        cache: "no-store",
    });
    if (!response.ok) {
        const body = (await response.json().catch(() => null)) as
            | { detail?: string }
            | null;
        throw new Error(body?.detail || `Diagnostics failed (${response.status})`);
    }
    return response.json() as Promise<SystemDiagnostics>;
}

export async function downloadSystemBackup(): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/system/backup`, {
        cache: "no-store",
    });
    if (!response.ok) throw new Error(`Backup failed (${response.status})`);
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") ?? "";
    const filename = disposition.match(/filename="?([^";]+)"?/)?.[1]
        ?? "ai-lab-backup.zip";
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}
