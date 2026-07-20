import argparse
import json
import sys
from pathlib import Path


backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from services.unity_docs_service import UnityDocsService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean and index scraped Unity Markdown documentation"
    )
    parser.add_argument("source_directory")
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument(
        "--preview",
        help="Preview one path relative to source_directory without indexing",
    )
    args = parser.parse_args()

    service = UnityDocsService()
    if args.preview:
        print(
            json.dumps(
                service.preview(args.source_directory, args.preview),
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    for event in service.index_stream(
        args.source_directory,
        batch_size=args.batch_size,
    ):
        print(json.dumps(event, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
