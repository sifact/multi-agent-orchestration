"""Build the dataset: `uv run python -m contoso_aero.data`."""

from collections import Counter

from ..config import DataSettings
from ..evaluation import build_questions, write_questions
from . import build_dataset


def main() -> None:
    settings = DataSettings()
    summary = build_dataset(settings)
    for name, count in summary.table_rows.items():
        print(f"{name:24} {count:>7} rows")
    print(f"{'knowledge documents':24} {summary.documents:>7}")
    # Questions are computed from the database just written, so they always match it.
    questions = build_questions(settings.database_path, settings.snapshot_date, settings.seed)
    write_questions(questions, settings.eval_path)
    by_category = Counter(q.category for q in questions)
    print(f"{'evaluation questions':24} {len(questions):>7} {dict(by_category)}")
    print(f"database: {settings.database_path}")


if __name__ == "__main__":
    main()
