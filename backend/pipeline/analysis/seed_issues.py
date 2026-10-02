import json
from pathlib import Path

from backend.db.database import (
    get_connection,
    init_db,
)


PROJECT_ROOT = Path(
    __file__
).resolve().parents[3]

ISSUES_DIR = (
    PROJECT_ROOT
    / "config"
    / "issues"
)


def seed_issue(path: Path) -> None:
    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO issues (
                slug,
                title,
                question,
                source
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(slug)
            DO UPDATE SET
                title = excluded.title,
                question = excluded.question,
                source = excluded.source
            """,
            (
                data["slug"],
                data["title"],
                data["question"],
                data["source"],
            ),
        )

        for position in data["positions"]:
            connection.execute(
                """
                INSERT INTO positions (
                    id,
                    issue_slug,
                    label,
                    description
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id)
                DO UPDATE SET
                    issue_slug = excluded.issue_slug,
                    label = excluded.label,
                    description = excluded.description
                """,
                (
                    position["id"],
                    data["slug"],
                    position["label"],
                    position["description"],
                ),
            )

        connection.commit()

    print(
        f"[seeded] {data['slug']} "
        f"({len(data['positions'])} posições)"
    )


def main():
    init_db()

    files = sorted(
        ISSUES_DIR.glob("*.json")
    )

    if not files:
        raise RuntimeError(
            "Não existem ficheiros de questões "
            "em config/issues."
        )

    for path in files:
        seed_issue(path)

    print()
    print(
        f"Questões carregadas: {len(files)}"
    )


if __name__ == "__main__":
    main()