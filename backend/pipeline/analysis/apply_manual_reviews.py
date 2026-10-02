import re

from backend.db.database import (
    get_connection,
    init_db,
)


ISSUE_SLUG = "loan-prescription-acceleration"
FIVE_YEAR = "loan-prescription-five-year"


MANUAL_REVIEWS = [
    {
        "process_number": "7214/18.5T8STB-A.E1.S1",
        "source": "summary",
        "start": (
            "O crédito emergente de um contrato de mútuo bancário"
        ),
        "end": (
            "não altera o seu enquadramento em termos da prescrição."
        ),
    },
    {
        "process_number": "1708/20.0T8GMR.G1.S1",
        "source": "summary",
        "start": (
            "Aos contratos de mútuo ou financiamento"
        ),
        "end": (
            "ainda que se verifique o vencimento "
            "antecipado de todas as prestações."
        ),
    },
    {
        "process_number": "554/20.5T8AGH.L1.S1",
        "source": "full_text",
        "start": (
            "Ou seja, ocorrendo o vencimento antecipado"
        ),
        "end": (
            "na data em que ocorreu o vencimento antecipado"
        ),
    },
    {
        "process_number": "4871/22.1T8SNT-A.L1.S1",
        "source": "full_text",
        "start": (
            "o prazo de prescrição aplicável ao caso "
            "é o de cinco anos"
        ),
        "end": (
            "em relação a todas as quotas assim vencidas"
        ),
    },
    {
        "process_number": "275/23.7T80ER-8.L1.S1",
        "source": "summary",
        "start": (
            "Da interpretação conjugada da jurisprudência "
            "fixada pelo AUJ n.º 6/2022"
        ),
        "end": (
            "previsto no artigo 310.º alínea e) "
            "do Código Civil."
        ),
    },
]


def normalize_whitespace(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def normalize_with_map(
    source: str,
) -> tuple[str, list[int]]:
    chars: list[str] = []
    indexes: list[int] = []

    in_whitespace = False

    for index, char in enumerate(source):
        if char.isspace():
            if not in_whitespace:
                chars.append(" ")
                indexes.append(index)

            in_whitespace = True

        else:
            chars.append(char)
            indexes.append(index)
            in_whitespace = False

    return (
        "".join(chars),
        indexes,
    )


def extract_quote(
    source: str,
    start_anchor: str,
    end_anchor: str,
) -> tuple[str, int, int]:
    normalized_source, index_map = (
        normalize_with_map(source)
    )

    normalized_start = normalize_whitespace(
        start_anchor
    )

    normalized_end = normalize_whitespace(
        end_anchor
    )

    start = normalized_source.find(
        normalized_start
    )

    if start < 0:
        raise RuntimeError(
            "Início da evidência não encontrado: "
            f"{start_anchor}"
        )

    end_start = normalized_source.find(
        normalized_end,
        start,
    )

    if end_start < 0:
        raise RuntimeError(
            "Fim da evidência não encontrado: "
            f"{end_anchor}"
        )

    normalized_end_index = (
        end_start
        + len(normalized_end)
        - 1
    )

    original_start = index_map[
        start
    ]

    original_end = (
        index_map[
            normalized_end_index
        ]
        + 1
    )

    quote = source[
        original_start:original_end
    ]

    return (
        quote,
        original_start,
        original_end,
    )


def apply_review(
    connection,
    review: dict,
) -> None:
    row = connection.execute(
        """
        SELECT
            c.id AS case_id,
            c.process_number,
            c.summary,
            c.full_text,
            s.id AS stance_id

        FROM cases c

        JOIN stances s
          ON s.case_id = c.id

        WHERE REPLACE(
            c.process_number,
            ' ',
            ''
        ) = REPLACE(
            ?,
            ' ',
            ''
        )
          AND s.issue_slug = ?
        """,
        (
            review["process_number"],
            ISSUE_SLUG,
        ),
    ).fetchone()

    if row is None:
        raise RuntimeError(
            "Caso não encontrado: "
            f"{review['process_number']}"
        )

    source_name = review[
        "source"
    ]

    source_text = row[
        source_name
    ] or ""

    if not source_text:
        raise RuntimeError(
            "Fonte vazia para "
            f"{row['process_number']}: "
            f"{source_name}"
        )

    quote, start_offset, end_offset = (
        extract_quote(
            source_text,
            review["start"],
            review["end"],
        )
    )

    connection.execute(
        """
        UPDATE stances

        SET
            position_id = ?,
            decides_issue = 1,
            status = 'AUTO'

        WHERE id = ?
        """,
        (
            FIVE_YEAR,
            row["stance_id"],
        ),
    )

    # Remove evidência anterior para que
    # o script possa ser executado várias
    # vezes sem criar duplicados.
    connection.execute(
        """
        DELETE FROM evidence
        WHERE stance_id = ?
        """,
        (
            row["stance_id"],
        ),
    )

    role = (
        "manual_review_summary"
        if source_name == "summary"
        else "manual_review_holding"
    )

    connection.execute(
        """
        INSERT INTO evidence (
            stance_id,
            role,
            start_offset,
            end_offset,
            quote,
            verified
        )
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (
            row["stance_id"],
            role,
            start_offset,
            end_offset,
            quote,
        ),
    )

    print(
        f"[OK] {row['process_number']}"
    )

    print(
        f"     role={role}"
    )

    print(
        "     position="
        f"{FIVE_YEAR}"
    )

    print(
        "     evidence="
        f"{normalize_whitespace(quote)}"
    )


def print_stats(
    connection,
) -> None:
    print()
    print("=" * 70)
    print("ESTATÍSTICAS FINAIS")
    print("=" * 70)

    rows = connection.execute(
        """
        SELECT
            COALESCE(
                position_id,
                'NO_POSITION'
            ) AS position,
            COUNT(*) AS total

        FROM stances

        WHERE issue_slug = ?

        GROUP BY position_id

        ORDER BY total DESC
        """,
        (
            ISSUE_SLUG,
        ),
    ).fetchall()

    print("\nPOSIÇÕES")

    for row in rows:
        print(
            dict(row)
        )

    rows = connection.execute(
        """
        SELECT
            status,
            COUNT(*) AS total

        FROM stances

        WHERE issue_slug = ?

        GROUP BY status

        ORDER BY status
        """,
        (
            ISSUE_SLUG,
        ),
    ).fetchall()

    print("\nSTATUS")

    for row in rows:
        print(
            dict(row)
        )

    evidence = connection.execute(
        """
        SELECT
            COUNT(
                DISTINCT e.stance_id
            ) AS total

        FROM evidence e

        JOIN stances s
          ON s.id = e.stance_id

        WHERE s.issue_slug = ?
          AND e.verified = 1
        """,
        (
            ISSUE_SLUG,
        ),
    ).fetchone()

    print(
        "\nEVIDÊNCIA VERIFICADA:",
        evidence["total"],
    )

    rows = connection.execute(
        """
        SELECT
            c.process_number,
            c.decision_date,
            s.position_id,
            s.status

        FROM stances s

        JOIN cases c
          ON c.id = s.case_id

        WHERE s.issue_slug = ?
          AND s.status = 'REVIEW'

        ORDER BY c.decision_date
        """,
        (
            ISSUE_SLUG,
        ),
    ).fetchall()

    print("\nCASOS AINDA EM REVIEW")

    if not rows:
        print("Nenhum.")

    for row in rows:
        print(
            dict(row)
        )


def main():
    init_db()

    print()
    print("=" * 70)
    print(
        "JURISSHIFT — MANUAL REVIEW"
    )
    print("=" * 70)

    with get_connection() as connection:
        try:
            for review in MANUAL_REVIEWS:
                apply_review(
                    connection,
                    review,
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        print_stats(
            connection
        )


if __name__ == "__main__":
    main()