import argparse

from backend.pipeline.ingestion.stj_discovery import (
    discover_cases,
)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "descriptor",
        help="Descritor a pesquisar no portal STJ",
    )

    args = parser.parse_args()

    cases = discover_cases(
        args.descriptor
    )

    print()
    print("=" * 70)
    print("JURISSHIFT — DISCOVERY")
    print("=" * 70)

    for index, case in enumerate(
        cases,
        start=1,
    ):
        print()
        print(
            f"{index}. "
            f"{case['process_number'] or 'Sem processo'}"
        )

        print(
            f"   Data: "
            f"{case['date']}"
        )

        print(
            f"   Relator: "
            f"{case['rapporteur']}"
        )

        print(
            f"   {case['url']}"
        )

    print()
    print("=" * 70)
    print(
        f"TOTAL: {len(cases)} acórdãos"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()