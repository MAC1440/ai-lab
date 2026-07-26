"use client";

import { FileCode2Icon } from "lucide-react";

import { cn } from "@/lib/utils";

type DiffLineKind = "addition" | "deletion" | "context" | "meta";

type ParsedDiffLine = {
  kind: DiffLineKind;
  content: string;
  oldLineNumber: number | null;
  newLineNumber: number | null;
};

type ParsedDiffHunk = {
  header: string;
  lines: ParsedDiffLine[];
};

type ParsedUnifiedDiff = {
  oldFile: string | null;
  newFile: string | null;
  additions: number;
  deletions: number;
  hunks: ParsedDiffHunk[];
};

const HUNK_HEADER_PATTERN =
  /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$/;

function parseUnifiedDiff(diff: string): ParsedUnifiedDiff {
  const sourceLines = diff.replace(/\r\n/g, "\n").split("\n");
  const hunks: ParsedDiffHunk[] = [];

  let oldFile: string | null = null;
  let newFile: string | null = null;
  let additions = 0;
  let deletions = 0;
  let oldLineNumber = 0;
  let newLineNumber = 0;
  let currentHunk: ParsedDiffHunk | null = null;

  function ensureHunk() {
    if (!currentHunk) {
      currentHunk = {
        header: "File metadata",
        lines: [],
      };
      hunks.push(currentHunk);
    }

    return currentHunk;
  }

  for (let index = 0; index < sourceLines.length; index += 1) {
    const line = sourceLines[index];

    // A trailing newline creates one final empty array item. It is not a diff row.
    if (index === sourceLines.length - 1 && line === "") {
      continue;
    }

    if (!currentHunk && line.startsWith("--- ")) {
      oldFile = line.slice(4).trim();
      continue;
    }

    if (!currentHunk && line.startsWith("+++ ")) {
      newFile = line.slice(4).trim();
      continue;
    }

    const hunkMatch = line.match(HUNK_HEADER_PATTERN);
    if (hunkMatch) {
      oldLineNumber = Number(hunkMatch[1]);
      newLineNumber = Number(hunkMatch[3]);
      currentHunk = {
        header: line,
        lines: [],
      };
      hunks.push(currentHunk);
      continue;
    }

    const hunk = ensureHunk();

    if (line.startsWith("+")) {
      additions += 1;
      hunk.lines.push({
        kind: "addition",
        content: line.slice(1),
        oldLineNumber: null,
        newLineNumber,
      });
      newLineNumber += 1;
      continue;
    }

    if (line.startsWith("-")) {
      deletions += 1;
      hunk.lines.push({
        kind: "deletion",
        content: line.slice(1),
        oldLineNumber,
        newLineNumber: null,
      });
      oldLineNumber += 1;
      continue;
    }

    if (line.startsWith(" ")) {
      hunk.lines.push({
        kind: "context",
        content: line.slice(1),
        oldLineNumber,
        newLineNumber,
      });
      oldLineNumber += 1;
      newLineNumber += 1;
      continue;
    }

    hunk.lines.push({
      kind: "meta",
      content: line,
      oldLineNumber: null,
      newLineNumber: null,
    });
  }

  return {
    oldFile,
    newFile,
    additions,
    deletions,
    hunks,
  };
}

function lineRowClasses(kind: DiffLineKind) {
  return cn(
    "grid min-w-max grid-cols-[3.25rem_3.25rem_1.5rem_minmax(36rem,1fr)] border-b border-border/5 font-mono text-xs leading-5 last:border-b-0",
    kind === "addition" && "bg-success/10 text-success",
    kind === "deletion" && "bg-danger/10 text-danger",
    kind === "context" && "bg-surface-raised text-muted-foreground",
    kind === "meta" && "bg-surface-raised text-muted-foreground",
  );
}

function numberCellClasses(kind: DiffLineKind) {
  return cn(
    "select-none border-r border-border/5 px-2 text-right tabular-nums",
    kind === "addition" && "bg-success/10 text-success",
    kind === "deletion" && "bg-danger/10 text-danger",
    kind === "context" && "bg-surface-raised/80 text-muted-foreground",
    kind === "meta" && "bg-surface-raised text-foreground",
  );
}

function markerFor(kind: DiffLineKind) {
  if (kind === "addition") {
    return "+";
  }

  if (kind === "deletion") {
    return "−";
  }

  return "";
}

export function UnifiedDiffView({ diff }: { diff: string }) {
  if (!diff.trim()) {
    return (
      <div className="flex min-h-32 items-center justify-center border-t border-border bg-surface-raised px-4 text-sm text-muted-foreground">
        No textual diff was produced.
      </div>
    );
  }

  const parsed = parseUnifiedDiff(diff);
  const displayedFile = parsed.newFile ?? parsed.oldFile ?? "Changed file";

  return (
    <section className="overflow-hidden border-t border-border bg-surface-raised">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface-raised/90 px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
          <FileCode2Icon className="size-4 shrink-0 text-muted-foreground" />
          <span className="truncate font-mono" title={displayedFile}>
            {displayedFile}
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs font-semibold tabular-nums">
          <span className="rounded-md border border-success/30 bg-success/10 px-2 py-0.5 text-success">
            +{parsed.additions}
          </span>
          <span className="rounded-md border border-danger/30 bg-danger/10 px-2 py-0.5 text-danger">
            −{parsed.deletions}
          </span>
        </div>
      </div>

      <div className="max-h-[34rem] overflow-auto bg-surface-raised">
        {parsed.hunks.map((hunk, hunkIndex) => (
          <div key={`${hunk.header}-${hunkIndex}`}>
            <div className="sticky top-0 z-10 min-w-max border-y border-pending/30 bg-pending/10 px-4 py-1.5 font-mono text-xs text-pending backdrop-blur">
              {hunk.header}
            </div>

            {hunk.lines.map((line, lineIndex) => (
              <div
                key={`${hunkIndex}-${lineIndex}`}
                className={lineRowClasses(line.kind)}
              >
                <span className={numberCellClasses(line.kind)}>
                  {line.oldLineNumber ?? ""}
                </span>
                <span className={numberCellClasses(line.kind)}>
                  {line.newLineNumber ?? ""}
                </span>
                <span
                  className={cn(
                    "select-none text-center font-bold",
                    line.kind === "addition" && "text-success",
                    line.kind === "deletion" && "text-danger",
                  )}
                  aria-hidden="true"
                >
                  {markerFor(line.kind)}
                </span>
                <code className="whitespace-pre px-3 pr-8">
                  {line.content || " "}
                </code>
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-4 border-t border-border bg-surface-raised/80 px-4 py-2 text-[11px] text-muted-foreground">
        <span>
          <span className="font-semibold text-muted-foreground">Old</span> line
        </span>
        <span>
          <span className="font-semibold text-muted-foreground">New</span> line
        </span>
        <span className="ml-auto hidden sm:inline">
          Scroll horizontally for long lines
        </span>
      </div>
    </section>
  );
}
