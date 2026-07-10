import type {
    ActiveWorkspaceResponse,
    BrowseWorkspaceResponse,
    DrivesResponse,
    SelectWorkspaceResponse,
} from "./types";

const API_BASE_URL =
    process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

async function parseResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
        const body = await response.json().catch(() => null);

        throw new Error(
            body?.detail ??
            body?.error ??
            `Request failed with status ${response.status}`,
        );
    }

    return response.json() as Promise<T>;
}

export async function getAvailableDrives(): Promise<DrivesResponse> {
    const response = await fetch(`${API_BASE_URL}/workspaces/drives`, {
        cache: "no-store",
    });

    return parseResponse<DrivesResponse>(response);
}

export async function getActiveWorkspace(): Promise<ActiveWorkspaceResponse> {
    const response = await fetch(`${API_BASE_URL}/workspaces/active`, {
        cache: "no-store",
    });

    return parseResponse<ActiveWorkspaceResponse>(response);
}

export async function browseWorkspace(
    path: string,
): Promise<BrowseWorkspaceResponse> {
    const response = await fetch(`${API_BASE_URL}/workspaces/browse`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ path }),
    });

    return parseResponse<BrowseWorkspaceResponse>(response);
}

export async function selectWorkspace(
    path: string,
): Promise<SelectWorkspaceResponse> {
    const response = await fetch(`${API_BASE_URL}/workspaces/select`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ path }),
    });

    return parseResponse<SelectWorkspaceResponse>(response);
}