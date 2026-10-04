import argparse
import json
from pathlib import Path

from backend.db.database import get_connection, init_db


CONFIG_DIR = Path("config/issues")


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Config não encontrado: {path}"
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def sync_issue(config: dict) -> None:
    slug = config["slug"]

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
                slug,
                config["title"],
                config["question"],
                config["source"],
            ),
        )

        configured_position_ids = []

        for position in config["positions"]:
            configured_position_ids.append(
                position["id"]
            )

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
                    slug,
                    position["label"],
                    position["description"],
                ),
            )

        connection.commit()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "config",
        help=(
            "Nome do ficheiro JSON dentro de "
            "config/issues ou caminho completo."
        ),
    )

    args = parser.parse_args()

    init_db()

    supplied_path = Path(
        args.config
    )

    if supplied_path.exists():
        path = supplied_path
    else:
        path = (
            CONFIG_DIR
            / args.config
        )

    config = load_config(
        path
    )

    sync_issue(
        config
    )

    print(
        f"Issue sincronizada: "
        f"{config['slug']}"
    )

    print(
        f"Posições: "
        f"{len(config['positions'])}"
    )


if __name__ == "__main__":
    main()