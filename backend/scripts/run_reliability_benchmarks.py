from __future__ import annotations

import argparse
import json
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run AI Lab's isolated end-to-end reliability benchmark against "
            "an already running backend."
        )
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="AI Lab backend base URL.",
    )
    parser.add_argument(
        "--suite",
        choices=("quick", "full"),
        default="quick",
    )
    parser.add_argument("--repetitions", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument(
        "--agent",
        choices=("assigned", "coding", "unity", "web"),
        default="assigned",
        help="Use scenario-specific assignments or force one agent.",
    )
    args = parser.parse_args()

    endpoint = args.url.rstrip("/") + "/reliability-benchmarks/run/stream"
    payload = {
        "suite": args.suite,
        "repetitions": args.repetitions,
        "agent_override": args.agent,
    }
    terminal_status = "error"
    try:
        with httpx.stream(
            "POST",
            endpoint,
            json=payload,
            headers={"Accept": "application/x-ndjson"},
            timeout=None,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.strip():
                    continue
                event = json.loads(line)
                event_type = event.get("type")
                if event_type == "reliability_started":
                    print(
                        "Started "
                        f"{event['suite']} suite {event['run_id']} "
                        f"({event['scenario_count']} scenarios)"
                    )
                elif event_type == "scenario_started":
                    scenario = event["scenario"]
                    print(
                        f"[{event['sequence']:02d}] "
                        f"{scenario['name']}...",
                        end=" ",
                        flush=True,
                    )
                elif event_type == "scenario_done":
                    result = event["result"]
                    print(
                        f"{result['status'].upper()} "
                        f"({result['score'] * 100:.0f}%, "
                        f"{result['duration_ms'] / 1000:.1f}s)"
                    )
                    if result.get("error"):
                        print(f"     {result['error']}")
                elif event_type == "reliability_done":
                    run = event["run"]
                    terminal_status = str(run["status"])
                    print(
                        f"Finished: {run['passed_count']}/"
                        f"{run['scenario_count']} passed "
                        f"({run['pass_rate'] * 100:.1f}%)."
                    )
                    print(f"Run ID: {run['run_id']}")
                elif event_type == "error":
                    print(
                        f"Benchmark error: {event.get('message', 'unknown')}",
                        file=sys.stderr,
                    )
                    return 2
    except (httpx.HTTPError, json.JSONDecodeError) as error:
        print(f"Could not run reliability benchmark: {error}", file=sys.stderr)
        return 2
    return 0 if terminal_status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
