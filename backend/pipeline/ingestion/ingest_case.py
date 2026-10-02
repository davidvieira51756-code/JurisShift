import argparse

from backend.db.database import init_db
from backend.pipeline.ingestion.stj_fetcher import (
    fetch_case_html,
)
from backend.pipeline.ingestion.stj_parser import (
    parse_case,
)
from backend.repositories.case_repository import (
    get_case,
    save_case,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Descarrega, interpreta e guarda "
            "um acórdão do portal juris.stj.pt."
        )
    )

    parser.add_argument(
        "url",
        help="URL do acórdão",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignorar HTML em cache",
    )

    args = parser.parse_args()

    init_db()

    print("[1/3] A obter acórdão...")

    html = fetch_case_html(
        args.url,
        force=args.force,
    )

    print("[2/3] A interpretar acórdão...")

    case = parse_case(
        html,
        args.url,
    )

    if not case.ecli:
        raise RuntimeError(
            "O acórdão não possui ECLI. "
            "Não será guardado."
        )

    if not case.full_text:
        raise RuntimeError(
            "O acórdão não possui texto integral. "
            "Não será guardado."
        )

    print("[3/3] A guardar na base de dados...")

    case_id = save_case(case)

    saved = get_case(case_id)

    print()
    print("=" * 70)
    print("ACÓRDÃO GUARDADO")
    print("=" * 70)

    print(f"ID:            {saved['id']}")
    print(f"ECLI:          {saved['ecli']}")
    print(f"Processo:      {saved['process_number']}")
    print(f"Data:          {saved['decision_date']}")
    print(f"Relator:       {saved['rapporteur']}")
    print(f"Secção:        {saved['section']}")

    print(
        f"Descritores:   "
        f"{len(saved['descriptors'])}"
    )

    print(
        f"Texto integral:"
        f" {len(saved['full_text'] or ''):,} caracteres"
    )

    print()
    print(f"Saved case #{case_id}")


if __name__ == "__main__":
    main()