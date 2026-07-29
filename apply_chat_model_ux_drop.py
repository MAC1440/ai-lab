from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable


TARGET_COMMIT = "72b59c24e21318815fc353caa1264e2196856c2d"

REPLACEMENT_FILES = (
    "frontend/features/home/components/chat-model-selector.tsx",
    "frontend/features/home/components/chat-header.tsx",
    "frontend/components/shell/drawer-management-section.tsx",
    "frontend/components/shell/app-sidebar.tsx",
    "frontend/components/shell/mobile-navigation.tsx",
)

PATCHERS: dict[str, Callable[[str], str]] = {}


def register(path: str):
    def decorator(function: Callable[[str], str]):
        PATCHERS[path] = function
        return function
    return decorator


def replace_once(
    text: str,
    old: str,
    new: str,
    *,
    path: str,
) -> str:
    if new in text:
        return text

    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Refusing to patch {path}: expected one matching source "
            f"block, found {count}. The repository may have changed."
        )
    return text.replace(old, new, 1)


@register("frontend/features/home/components/chat-panel.tsx")
def patch_chat_panel(text: str) -> str:
    path = "frontend/features/home/components/chat-panel.tsx"

    text = replace_once(
        text,
        '''import { ChatHeader } from "@/features/home/components/chat-header";
import { ChatComposer } from "@/features/home/components/chat-composer";
''',
        '''import { ChatHeader } from "@/features/home/components/chat-header";
import type { ChatModelSelectionStatus } from "@/features/home/components/chat-model-selector";
import { ChatComposer } from "@/features/home/components/chat-composer";
''',
        path=path,
    )

    text = replace_once(
        text,
        '''    const [settings, setSettings] =
        useState<AgentChatSettings>(defaultAgentSettings);

    const bottomRef = useRef<HTMLDivElement>(null);
''',
        '''    const [settings, setSettings] =
        useState<AgentChatSettings>(defaultAgentSettings);
    const [modelStatus, setModelStatus] =
        useState<ChatModelSelectionStatus>({
            loading: true,
            configured: false,
            providerId: null,
            providerName: null,
            model: null,
        });

    const bottomRef = useRef<HTMLDivElement>(null);
''',
        path=path,
    )

    text = replace_once(
        text,
        '''        if (agents.some((agent) => agent.id === request.recommendedAgentId)) {
            setSelectedAgentId(request.recommendedAgentId);
            setRecommendationReason(request.recommendationReason);
        }
''',
        '''        if (agents.some((agent) => agent.id === request.recommendedAgentId)) {
            setSelectedAgentId(request.recommendedAgentId);
            setModelStatus(unconfiguredModelStatus(true));
            setRecommendationReason(request.recommendationReason);
        }
''',
        path=path,
    )

    text = replace_once(
        text,
        '''            setSessionId(conversation.session_id);
            setSelectedAgentId(conversation.agent_id);
            setSettings({
''',
        '''            setSessionId(conversation.session_id);
            setSelectedAgentId(conversation.agent_id);
            setModelStatus(unconfiguredModelStatus(true));
            setSettings({
''',
        path=path,
    )

    text = replace_once(
        text,
        '''                    setSelectedAgentId(recommendation.agent_id);
                    setSessionId(null);
''',
        '''                    setSelectedAgentId(recommendation.agent_id);
                    setModelStatus(unconfiguredModelStatus(true));
                    setSessionId(null);
''',
        path=path,
    )

    text = replace_once(
        text,
        '''        if (selectedAgentUsesWorkspaceTools && !activeWorkspace) {
''',
        '''        if (modelStatus.loading || !modelStatus.configured) {
            setError(
                `Select a model for ${selectedAgent.name} before sending this request.`,
            );
            return;
        }

        if (selectedAgentUsesWorkspaceTools && !activeWorkspace) {
''',
        path=path,
    )

    text = replace_once(
        text,
        '''    function handleClear() {
        setSessionId(null);
        setMessages([]);
        setError(null);
        externalRequest.reset();
    }

    const inputDisabled =
        isSending ||
        agentsLoading ||
        !selectedAgent ||
        (selectedAgentUsesWorkspaceTools && !activeWorkspace);
''',
        '''    function handleClear() {
        setSessionId(null);
        setMessages([]);
        setError(null);
        externalRequest.reset();
    }

    async function handleModelAssignmentChanged() {
        handleClear();
        try {
            setAgents(await getAgents());
        } catch (requestError) {
            setError(
                requestError instanceof Error
                    ? requestError.message
                    : "The model was saved, but agents could not be refreshed.",
            );
        }
    }

    const inputDisabled =
        isSending ||
        agentsLoading ||
        modelStatus.loading ||
        !modelStatus.configured ||
        !selectedAgent ||
        (selectedAgentUsesWorkspaceTools && !activeWorkspace);
''',
        path=path,
    )

    text = replace_once(
        text,
        '''                    recommendationReason={recommendationReason}
                    isSending={isSending}
                    canClear={messages.length > 0}
                    onAgentChange={(agentId) => {
                        setSelectedAgentId(agentId);
                        setSessionId(null);
''',
        '''                    recommendationReason={recommendationReason}
                    modelStatus={modelStatus}
                    isSending={isSending}
                    canClear={messages.length > 0}
                    hasConversation={messages.length > 0}
                    onAgentChange={(agentId) => {
                        setSelectedAgentId(agentId);
                        setModelStatus(unconfiguredModelStatus(true));
                        setSessionId(null);
''',
        path=path,
    )

    text = replace_once(
        text,
        '''                    onSettingsOpenChange={setSettingsOpen}
                    onSettingsChange={setSettings}
                    onClear={handleClear}
                    onAgentsRefresh={async () => setAgents(await getAgents())}
                />
''',
        '''                    onSettingsOpenChange={setSettingsOpen}
                    onSettingsChange={setSettings}
                    onModelStatusChange={setModelStatus}
                    onModelAssignmentChanged={handleModelAssignmentChanged}
                    onModelError={setError}
                    onClear={handleClear}
                />
''',
        path=path,
    )

    text = replace_once(
        text,
        '''                        selectedAgentUsesWorkspaceTools && !activeWorkspace
                            ? "Select a workspace before using this agent…"
                            : selectedAgent
                                ? `Message ${selectedAgent.name}…`
                                : "Loading agents…"
''',
        '''                        modelStatus.loading
                            ? "Loading model assignment…"
                            : !modelStatus.configured
                                ? "Select a model above before chatting…"
                                : selectedAgentUsesWorkspaceTools && !activeWorkspace
                                    ? "Select a workspace before using this agent…"
                                    : selectedAgent
                                        ? `Message ${selectedAgent.name} with ${modelStatus.model}…`
                                        : "Loading agents…"
''',
        path=path,
    )

    helper = '''function unconfiguredModelStatus(
    loading: boolean,
): ChatModelSelectionStatus {
    return {
        loading,
        configured: false,
        providerId: null,
        providerName: null,
        model: null,
    };
}
'''
    if helper not in text:
        text = text.rstrip() + "\n\n" + helper

    return text


@register("frontend/features/model-settings/model-library-panel.tsx")
def patch_model_library(text: str) -> str:
    path = "frontend/features/model-settings/model-library-panel.tsx"

    text = replace_once(
        text,
        '''            const localReference =
              model.pull_name || suggestCloudReference(model.name);
            const pullTarget =
              cloudProvider && localPullProvider
                ? localPullProvider
                : undefined;
            const pullState = pullTarget
              ? pulls[pullKey(pullTarget.id, localReference)]
              : undefined;
''',
        '''            const localReference =
              model.pull_name || suggestCloudReference(model.name);
            const pullTarget =
              canPull
                ? provider
                : cloudProvider && localPullProvider
                  ? localPullProvider
                  : undefined;
            const pullReference =
              pullTarget?.id === provider.id
                ? model.name
                : localReference;
            const pullState = pullTarget
              ? pulls[pullKey(pullTarget.id, pullReference)]
              : undefined;
''',
        path=path,
    )

    text = replace_once(
        text,
        '''                pullReference={localReference}
''',
        '''                pullReference={pullReference}
''',
        path=path,
    )

    text = replace_once(
        text,
        '''      {pullTarget ? (
        <div className="mt-4 rounded-lg border border-border bg-surface p-3 dark:border-border dark:bg-surface-raised">
          <p className="text-[10px] text-muted-foreground">
            Local cloud reference
          </p>
          <p className="mt-1 break-all font-mono text-[11px] text-foreground">
            {pullReference}
          </p>
          <button
            type="button"
            onClick={() => void onPull(pullTarget, pullReference)}
            disabled={isPulling(pullState)}
            className={`${secondaryButtonClass} mt-3 w-full justify-center`}
          >
            {isPulling(pullState) ? (
              <LoaderCircleIcon className="size-3.5 animate-spin" />
            ) : (
              <CloudIcon className="size-3.5" />
            )}
            Pull through {pullTarget.name}
          </button>
          {pullState ? (
            <PullProgressCard state={pullState} compact />
          ) : null}
        </div>
      ) : null}
''',
        '''      {pullTarget ? (
        <div className="mt-4 rounded-lg border border-border bg-surface p-3 dark:border-border dark:bg-surface-raised">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="text-[10px] text-muted-foreground">
                {pullTarget.id === provider.id
                  ? availability === "cloud"
                    ? "Cloud reference on this Ollama provider"
                    : "Installed on this Ollama provider"
                  : "Create a local Ollama cloud reference"}
              </p>
              <p className="mt-1 break-all font-mono text-[11px] text-foreground">
                {pullReference}
              </p>
            </div>
            <button
              type="button"
              onClick={() => void onPull(pullTarget, pullReference)}
              disabled={isPulling(pullState)}
              className={`${secondaryButtonClass} shrink-0 justify-center`}
            >
              {isPulling(pullState) ? (
                <LoaderCircleIcon className="size-3.5 animate-spin" />
              ) : availability === "cloud" ? (
                <CloudIcon className="size-3.5" />
              ) : (
                <DownloadIcon className="size-3.5" />
              )}
              {pullTarget.id !== provider.id
                ? `Pull to ${pullTarget.name}`
                : availability === "cloud"
                  ? "Refresh cloud model"
                  : "Update model"}
            </button>
          </div>
          {pullState ? (
            <PullProgressCard state={pullState} compact />
          ) : null}
        </div>
      ) : null}
''',
        path=path,
    )

    text = text.replace(
        '''const secondaryButtonClass =
  "inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-medium text-muted-foreground transition hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-50 dark:border-border dark:text-muted-foreground dark:hover:bg-surface-raised";
''',
        '''const secondaryButtonClass =
  "inline-flex cursor-pointer items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-medium text-muted-foreground transition hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-50 dark:border-border dark:text-muted-foreground dark:hover:bg-surface-raised";
''',
    )
    text = text.replace(
        '''const primaryButtonClass =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-surface-raised px-3 py-2 text-xs font-medium text-accent-foreground transition disabled:cursor-not-allowed disabled:opacity-50 dark:bg-surface-hover dark:text-foreground";
''',
        '''const primaryButtonClass =
  "inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-surface-raised px-3 py-2 text-xs font-medium text-accent-foreground transition disabled:cursor-not-allowed disabled:opacity-50 dark:bg-surface-hover dark:text-foreground";
''',
    )

    return text


@register("frontend/app/globals.css")
def patch_global_cursors(text: str) -> str:
    addition = '''
/* Interactive controls should visually advertise clickability. */
button:not(:disabled),
a[href],
select:not(:disabled),
summary,
[role="button"]:not([aria-disabled="true"]),
[role="option"]:not([data-disabled]) {
  cursor: pointer;
}

button:disabled,
select:disabled,
[aria-disabled="true"],
[data-disabled] {
  cursor: not-allowed;
}
'''
    if addition.strip() in text:
        return text
    return text.rstrip() + "\n" + addition


def apply(project_root: Path, payload_root: Path) -> list[str]:
    missing_payloads = [
        relative
        for relative in REPLACEMENT_FILES
        if not (payload_root / relative).is_file()
    ]
    missing_targets = [
        relative
        for relative in PATCHERS
        if not (project_root / relative).is_file()
    ]

    if missing_payloads or missing_targets:
        messages: list[str] = []
        if missing_payloads:
            messages.append(
                "Missing code-drop files:\n  - "
                + "\n  - ".join(missing_payloads)
            )
        if missing_targets:
            messages.append(
                "Missing project files:\n  - "
                + "\n  - ".join(missing_targets)
            )
        raise RuntimeError("\n".join(messages))

    staged: dict[Path, str] = {}
    changed: list[str] = []

    for relative in REPLACEMENT_FILES:
        source = payload_root / relative
        target = project_root / relative
        content = source.read_text(encoding="utf-8")
        staged[target] = content
        if not target.exists() or target.read_text(encoding="utf-8") != content:
            changed.append(relative)

    for relative, patcher in PATCHERS.items():
        target = project_root / relative
        original = target.read_text(encoding="utf-8")
        updated = patcher(original)
        staged[target] = updated
        if updated != original:
            changed.append(relative)

    for target, content in staged.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".chat-model-ux.tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)

    return sorted(set(changed))


def main() -> int:
    project_root = (
        Path(sys.argv[1]).resolve()
        if len(sys.argv) > 1
        else Path.cwd().resolve()
    )
    payload_root = Path(__file__).resolve().parent

    try:
        changed = apply(project_root, payload_root)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if changed:
        print("AI Lab chat/model UX drop applied:")
        for relative in changed:
            print(f"  - {relative}")
    else:
        print("The chat/model UX drop was already applied.")

    print()
    print("Run frontend checks:")
    print("  npm run lint")
    print("  npx tsc --noEmit")
    print("  npm run build")
    print()
    print("Run backend regression checks:")
    print("  python -m pytest -q")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
