"""Reject tracked reports/datasets while permitting application code and required models."""

import subprocess
from pathlib import PurePosixPath


def forbidden(name):
    path = PurePosixPath(name)
    parts = {part.lower() for part in path.parts}
    return (
        bool(parts & {"docs", "reports", "data", "datasets", "outputs"})
        or path.suffix.lower()
        in {
            ".csv",
            ".tsv",
            ".xlsx",
            ".xls",
            ".parquet",
            ".arrow",
            ".pdf",
            ".pptx",
            ".db",
            ".sqlite",
            ".sqlite3",
        }
        or path.name.lower() in {"provenance.md", "evaluation.json"}
        or path.name.endswith(("_REPORT.md", "_SUMMARY.md"))
    )


def main():
    names = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    rejected = [name for name in names if name and forbidden(name)]
    if rejected:
        raise SystemExit(
            "Reports/datasets must stay local; remove these from Git tracking:\n"
            + "\n".join(rejected)
        )
    print(
        "Source policy verified: no tracked reports or datasets; required model artifacts are permitted."
    )


if __name__ == "__main__":
    main()
