import subprocess
import sys

from backend.db.database import (
    get_connection,
    init_db,
)


ISSUE_SLUG = "family-home-own-land"


CASES = [
    {
        "process_number": "2737/07.4TBCSC-D.L1.S1",
        "url": (
            "https://juris.stj.pt/ecli/"
            "ECLI%3APT%3ASTJ%3A2010%3A"
            "2737.07.4TBCSC.D.L1.S1.47"
        ),
        "inclusion_method": "auj_precedent",
        "inclusion_note": (
            "Precedente do STJ identificado no AUJ 9/2025 "
            "como representativo da orientação que aplica "
            "o artigo 1726.º do Código Civil."
        ),
    },
    {
        "process_number": "5967/17.7T8CBR.S1",
        "url": (
            "https://juris.stj.pt/ecli/"
            "ECLI%3APT%3ASTJ%3A2019%3A"
            "5967.17.7T8CBR.S1.11"
        ),
        "inclusion_method": "auj_precedent",
        "inclusion_note": (
            "Precedente do STJ identificado no AUJ 9/2025 "
            "como representativo da orientação que rejeita "
            "a aplicação do artigo 1726.º e mantém o imóvel "
            "no património próprio."
        ),
    },
    {
        "process_number": "2124/15.0T8LRA.C1.S1",
        "url": (
            "https://juris.stj.pt/ecli/"
            "ECLI%3APT%3ASTJ%3A2021%3A"
            "2124.15.0T8LRA.C1.S1.60"
        ),
        "inclusion_method": "auj_precedent",
        "inclusion_note": (
            "Precedente do STJ identificado no AUJ 9/2025 "
            "como representativo da orientação das "
            "benfeitorias e compensação ao património comum."
        ),
    },
    {
        "process_number": "32/22.8T8BRG-A.G1.S1",
        "url": (
            "https://juris.stj.pt/ecli/"
            "ECLI%3APT%3ASTJ%3A2022%3A"
            "32.22.8T8BRG.A.G1.S1.29"
        ),
        "inclusion_method": "auj_precedent",
        "inclusion_note": (
            "Precedente do STJ identificado no AUJ 9/2025 "
            "como representativo da orientação que aplica "
            "o artigo 1726.º do Código Civil."
        ),
    },
    {
        "process_number": "1530/20.3T8VNF.G1.S1",
        "url": (
            "https://juris.stj.pt/ecli/"
            "ECLI%3APT%3ASTJ%3A2022%3A"
            "1530.20.3T8VNF.G1.S1.B6"
        ),
        "inclusion_method": "auj_precedent",
        "inclusion_note": (
            "Precedente do STJ identificado no AUJ 9/2025 "
            "como representativo da orientação que trata "
            "a construção como benfeitoria e reconhece "
            "crédito compensatório ao património comum."
        ),
    },
    {
        "process_number": "985/20.0T8VCD-B.P1.S1",
        "url": (
            "https://juris.stj.pt/"
            "985%2F20.0T8VCD-B.P1.S1/"
            "68_N_vUrCy3RzbC7W-Av_JGWWdk"
        ),
        "inclusion_method": "landmark",
        "inclusion_note": (
            "Julgamento ampliado que originou o AUJ 9/2025 "
            "e uniformizou a jurisprudência."
        ),
    },
    {
        "process_number": "159/23.9T8AGH.L1.S1",
        "url": (
            "https://juris.stj.pt/"
            "159%2F23.9T8AGH.L1.S1/"
            "cmCu4nBNkZvPRDGKo0DmcA6sUsA"
        ),
        "inclusion_method": "post_auj",
        "inclusion_note": (
            "Decisão posterior ao julgamento ampliado que "
            "segue expressamente a orientação uniformizada."
        ),
    },
    {
        "process_number": "53/24.6T8STS-A.P1.S1",
        "url": (
            "https://juris.stj.pt/"
            "53%2F24.6T8STS-A.P1.S1/"
            "qsSQhL02jxWnNigSUfuAZiAdZz0"
        ),
        "inclusion_method": "post_auj",
        "inclusion_note": (
            "Decisão posterior à publicação do AUJ 9/2025 "
            "que aplica a orientação uniformizada."
        ),
    },
    {
        "process_number": "599/20.5T8PVZ.P1.S1",
        "url": (
            "https://juris.stj.pt/"
            "599%2F20.5T8PVZ.P1.S1/"
            "ig9RdgxKYtE445n56J_UTpacuNk"
        ),
        "inclusion_method": "post_auj",
        "inclusion_note": (
            "Decisão posterior ao AUJ 9/2025 que aplica "
            "a qualificação do imóvel como bem próprio "
            "com crédito de compensação."
        ),
    },
]


def normalize_process(
    value: str,
) -> str:
    return (
        value
        .replace(" ", "")
        .strip()
        .casefold()
    )


def find_case_id(
    process_number: str,
) -> int | None:
    wanted = normalize_process(
        process_number
    )

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                process_number
            FROM cases
            """
        ).fetchall()

    for row in rows:
        current = normalize_process(
            row["process_number"]
            or ""
        )

        if current == wanted:
            return row["id"]

    return None


def register_membership(
    *,
    case_id: int,
    inclusion_method: str,
    inclusion_note: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO corpus_membership (
                case_id,
                issue_slug,
                inclusion_method,
                inclusion_note
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(case_id, issue_slug)
            DO UPDATE SET
                inclusion_method = excluded.inclusion_method,
                inclusion_note = excluded.inclusion_note
            """,
            (
                case_id,
                ISSUE_SLUG,
                inclusion_method,
                inclusion_note,
            ),
        )

        connection.commit()


def ingest_case(
    item: dict,
) -> bool:
    process_number = item[
        "process_number"
    ]

    print()
    print("=" * 70)

    print(
        f"A ingerir: "
        f"{process_number}"
    )

    print("=" * 70)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            (
                "backend.pipeline."
                "ingestion.ingest_case"
            ),
            item["url"],
        ],
        check=False,
    )

    if result.returncode != 0:
        print(
            f"[ERRO] ingestão falhou: "
            f"{process_number}"
        )

        return False

    case_id = find_case_id(
        process_number
    )

    if case_id is None:
        print(
            "[ERRO] A ingestão terminou, "
            "mas o processo não foi encontrado "
            "na base de dados."
        )

        return False

    register_membership(
        case_id=case_id,
        inclusion_method=(
            item[
                "inclusion_method"
            ]
        ),
        inclusion_note=(
            item[
                "inclusion_note"
            ]
        ),
    )

    print(
        f"[OK] case_id={case_id} "
        f"adicionado ao corpus "
        f"{ISSUE_SLUG}"
    )

    return True


def main():
    init_db()

    successful = 0
    failed = 0

    print()
    print("=" * 70)

    print(
        "JURISSHIFT — "
        "INGESTÃO ISSUE 2"
    )

    print("=" * 70)

    print(
        f"Issue: {ISSUE_SLUG}"
    )

    print(
        f"Casos alvo: {len(CASES)}"
    )

    for item in CASES:
        if ingest_case(
            item
        ):
            successful += 1
        else:
            failed += 1

    print()
    print("=" * 70)

    print(
        f"Ingeridos/registados: "
        f"{successful}"
    )

    print(
        f"Falharam:             "
        f"{failed}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()