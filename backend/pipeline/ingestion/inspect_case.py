import argparse

from backend.pipeline.ingestion.stj_fetcher import (
    fetch_case_html,
)

from backend.pipeline.ingestion.stj_parser import (
    parse_case,
)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "url",
        help="URL de um acórdão do portal juris.stj.pt",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignorar cache e descarregar novamente",
    )

    args = parser.parse_args()

    html = fetch_case_html(
        args.url,
        force=args.force,
    )

    case = parse_case(
        html,
        args.url,
    )

    print()
    print("=" * 70)
    print("JURISSHIFT — STJ PARSER")
    print("=" * 70)

    print(f"ECLI:          {case.ecli}")
    print(f"Processo:      {case.process_number}")
    print(f"Secção:        {case.section}")
    print(f"Área:          {case.area}")
    print(f"Relator:       {case.rapporteur}")
    print(f"Data:          {case.decision_date}")
    print(f"Meio:          {case.procedural_type}")
    print(f"Decisão:       {case.decision}")
    print(f"Votação:       {case.voting}")

    print()
    print(
        f"Descritores:   "
        f"{len(case.descriptors)}"
    )

    for descriptor in case.descriptors[:15]:
        print(f"  - {descriptor}")

    print()
    print(
        "Sumário:       "
        f"{len(case.summary or ''):,} caracteres"
    )

    print(
        "Texto integral:"
        f" {len(case.full_text or ''):,} caracteres"
    )

    print()

    if case.summary:
        print("--- INÍCIO DO SUMÁRIO ---")
        print(case.summary[:1000])
        print("--- FIM DA AMOSTRA ---")

    print()


if __name__ == "__main__":
    main()