import argparse
import os
import time

from dotenv import load_dotenv

from backend.db.database import init_db
from backend.pipeline.ingestion.stj_discovery import discover_cases
from backend.pipeline.ingestion.stj_fetcher import fetch_case_html
from backend.pipeline.ingestion.stj_parser import parse_case
from backend.repositories.case_repository import (
    count_cases,
    save_case,
)


load_dotenv()

REQUEST_DELAY = float(
    os.getenv(
        "DGSI_REQUEST_DELAY_SECONDS",
        "1.75",
    )
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Descobre e ingere acórdãos do portal "
            "de jurisprudência do STJ."
        )
    )

    parser.add_argument(
        "descriptor",
        help="Descritor a pesquisar",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limitar o número de acórdãos a ingerir",
    )

    args = parser.parse_args()

    init_db()

    print()
    print("=" * 70)
    print("JURISSHIFT — BATCH INGESTION")
    print("=" * 70)
    print(f"Descritor: {args.descriptor}")
    print()

    discovered = discover_cases(
        args.descriptor
    )

    if args.limit is not None:
        discovered = discovered[
            :args.limit
        ]

    print()
    print(
        f"Encontrados para ingestão: "
        f"{len(discovered)}"
    )
    print()

    successful = 0
    failed = 0
    skipped = 0

    failures = []

    for index, item in enumerate(
        discovered,
        start=1,
    ):
        url = item["url"]

        print()
        print("-" * 70)

        print(
            f"[{index}/{len(discovered)}] "
            f"{item['process_number']}"
        )

        try:
            html = fetch_case_html(
                url
            )

            case = parse_case(
                html,
                url,
            )

            if not case.full_text:
                print(
                    "[skip] sem texto integral"
                )

                skipped += 1
                continue

            case_id = save_case(
                case
            )

            successful += 1

            print(
                f"[saved] case #{case_id}"
            )

            print(
                f"        ECLI: "
                f"{case.ecli or 'não disponível'}"
            )

            print(
                f"        Processo: "
                f"{case.process_number or 'não disponível'}"
            )

            print(
                f"        "
                f"{len(case.full_text):,} caracteres"
            )

        except Exception as exc:
            failed += 1

            failures.append(
                {
                    "process": (
                        item["process_number"]
                    ),
                    "url": url,
                    "error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                }
            )

            print(
                f"[error] "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

        if index < len(discovered):
            time.sleep(
                REQUEST_DELAY
            )

    print()
    print("=" * 70)
    print("RESULTADO")
    print("=" * 70)

    print(f"Descobertos:   {len(discovered)}")
    print(f"Guardados:     {successful}")
    print(f"Ignorados:     {skipped}")
    print(f"Falharam:      {failed}")
    print(f"Total na BD:   {count_cases()}")

    if failures:
        print()
        print("FALHAS")

        for failure in failures:
            print()
            print(
                f"- {failure['process']}"
            )
            print(
                f"  {failure['error']}"
            )
            print(
                f"  {failure['url']}"
            )

    print()


if __name__ == "__main__":
    main()