import argparse

from backend.db.database import init_db
from backend.rag.retrieval import rebuild_issue_index


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "issue_slug",
    )

    args = parser.parse_args()

    init_db()

    total = rebuild_issue_index(
        args.issue_slug
    )

    print(
        f"Indexados {total} documentos "
        f"para {args.issue_slug}."
    )


if __name__ == "__main__":
    main()