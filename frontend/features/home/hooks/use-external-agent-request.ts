"use client";

import { useCallback, useEffect, useRef } from "react";

import type { AgentToolPolicy } from "@/features/agents/agent-api";
import {
  PROJECT_TASK_RUN_EVENT,
  type ProjectTaskRunDetail,
} from "@/features/project-tasks";
import {
  VERIFICATION_FIX_REQUEST_EVENT,
  type VerificationFixRequestDetail,
} from "@/features/verification";

export type ExternalAgentRequest = {
  prompt: string;
  toolPolicy: AgentToolPolicy;
  repairTaskId: string | null;
  projectTaskId: string | null;
  freshContext: boolean;
  recommendedAgentId: string;
  recommendationReason: string;
};

type PendingRequestRuntime = Pick<
  ExternalAgentRequest,
  "toolPolicy" | "repairTaskId" | "projectTaskId" | "freshContext"
>;

const DEFAULT_RUNTIME: PendingRequestRuntime = {
  toolPolicy: "auto",
  repairTaskId: null,
  projectTaskId: null,
  freshContext: false,
};

export function useExternalAgentRequest(
  onLoad: (request: ExternalAgentRequest) => void,
) {
  const pendingRef = useRef<PendingRequestRuntime>(DEFAULT_RUNTIME);

  useEffect(() => {
    function loadVerificationRequest(event: Event) {
      const detail = (event as CustomEvent<VerificationFixRequestDetail>).detail;
      if (!detail?.prompt) return;
      pendingRef.current = {
        toolPolicy: detail.toolPolicy,
        repairTaskId: detail.repairTaskId,
        projectTaskId: detail.projectTaskId,
        freshContext: detail.freshContext,
      };
      onLoad({
        ...pendingRef.current,
        prompt: detail.prompt,
        recommendedAgentId: detail.recommendedAgentId,
        recommendationReason:
          "Selected for the failed verification's project type.",
      });
    }

    function loadProjectTaskRequest(event: Event) {
      const detail = (event as CustomEvent<ProjectTaskRunDetail>).detail;
      if (!detail?.prompt) return;
      pendingRef.current = {
        toolPolicy: detail.toolPolicy,
        repairTaskId: detail.repairTaskId,
        projectTaskId: detail.projectTaskId,
        freshContext: detail.freshContext,
      };
      onLoad({
        ...pendingRef.current,
        prompt: detail.prompt,
        recommendedAgentId: detail.recommendedAgentId,
        recommendationReason: "Selected for the persisted project task.",
      });
    }

    window.addEventListener(
      VERIFICATION_FIX_REQUEST_EVENT,
      loadVerificationRequest,
    );
    window.addEventListener(PROJECT_TASK_RUN_EVENT, loadProjectTaskRequest);
    return () => {
      window.removeEventListener(
        VERIFICATION_FIX_REQUEST_EVENT,
        loadVerificationRequest,
      );
      window.removeEventListener(PROJECT_TASK_RUN_EVENT, loadProjectTaskRequest);
    };
  }, [onLoad]);

  const consume = useCallback((): PendingRequestRuntime => {
    const pending = pendingRef.current;
    pendingRef.current = DEFAULT_RUNTIME;
    return pending;
  }, []);

  const reset = useCallback(() => {
    pendingRef.current = DEFAULT_RUNTIME;
  }, []);

  return { consume, reset };
}
