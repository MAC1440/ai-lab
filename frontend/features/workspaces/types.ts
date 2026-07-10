export type WorkspaceItem = {
    name: string;
    path: string;
    type: "folder" | "file";
};

export type ActiveWorkspaceResponse = {
    workspace: string | null;
};

export type DrivesResponse = {
    drives: string[];
};

export type BrowseWorkspaceResponse = {
    path: string;
    items: WorkspaceItem[];
};

export type SelectWorkspaceResponse = {
    workspace: string;
};