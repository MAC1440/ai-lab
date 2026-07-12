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
    "grid min-w-max grid-cols-[3.25rem_3.25rem_1.5rem_minmax(36rem,1fr)] border-b border-white/5 font-mono text-xs leading-5 last:border-b-0",
    kind === "addition" && "bg-emerald-950/55 text-emerald-50",
    kind === "deletion" && "bg-red-950/55 text-red-50",
    kind === "context" && "bg-zinc-950 text-zinc-300",
    kind === "meta" && "bg-zinc-900 text-zinc-500",
  );
}

function numberCellClasses(kind: DiffLineKind) {
  return cn(
    "select-none border-r border-white/5 px-2 text-right tabular-nums",
    kind === "addition" && "bg-emerald-950/80 text-emerald-400",
    kind === "deletion" && "bg-red-950/80 text-red-400",
    kind === "context" && "bg-zinc-900/80 text-zinc-600",
    kind === "meta" && "bg-zinc-900 text-zinc-700",
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
      <div className="flex min-h-32 items-center justify-center border-t border-zinc-800 bg-zinc-950 px-4 text-sm text-zinc-500">
        No textual diff was produced.
      </div>
    );
  }

  const parsed = parseUnifiedDiff(diff);
  const displayedFile = parsed.newFile ?? parsed.oldFile ?? "Changed file";

  return (
    <section className="overflow-hidden border-t border-zinc-800 bg-zinc-950">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 bg-zinc-900/90 px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2 text-xs text-zinc-300">
          <FileCode2Icon className="size-4 shrink-0 text-zinc-400" />
          <span className="truncate font-mono" title={displayedFile}>
            {displayedFile}
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs font-semibold tabular-nums">
          <span className="rounded-md border border-emerald-800/70 bg-emerald-950/60 px-2 py-0.5 text-emerald-300">
            +{parsed.additions}
          </span>
          <span className="rounded-md border border-red-800/70 bg-red-950/60 px-2 py-0.5 text-red-300">
            −{parsed.deletions}
          </span>
        </div>
      </div>

      <div className="max-h-[34rem] overflow-auto bg-zinc-950">
        {parsed.hunks.map((hunk, hunkIndex) => (
          <div key={`${hunk.header}-${hunkIndex}`}>
            <div className="sticky top-0 z-10 min-w-max border-y border-sky-900/60 bg-sky-950/95 px-4 py-1.5 font-mono text-xs text-sky-300 backdrop-blur">
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
                    line.kind === "addition" && "text-emerald-400",
                    line.kind === "deletion" && "text-red-400",
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

      <div className="flex items-center gap-4 border-t border-zinc-800 bg-zinc-900/80 px-4 py-2 text-[11px] text-zinc-500">
        <span>
          <span className="font-semibold text-zinc-400">Old</span> line
        </span>
        <span>
          <span className="font-semibold text-zinc-400">New</span> line
        </span>
        <span className="ml-auto hidden sm:inline">
          Scroll horizontally for long lines
        </span>
      </div>
    </section>
  );
}
