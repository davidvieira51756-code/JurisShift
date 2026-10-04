import re
from dataclasses import asdict, dataclass

from backend.db.database import get_connection


MAX_RESULTS = 5


STOPWORDS = {
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "como",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "entre",
    "era",
    "foram",
    "foi",
    "há",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "ou",
    "para",
    "pela",
    "pelas",
    "pelo",
    "pelos",
    "por",
    "que",
    "qual",
    "quais",
    "se",
    "sem",
    "ser",
    "são",
    "um",
    "uma",
}


POSITION_QUERY_HINTS = {
    "loan-prescription-acceleration": {
        "loan-prescription-five-year": (
            "cinco anos",
            "5 anos",
            "quinquenal",
            "prazo de cinco",
            "mantém-se o prazo",
        ),

        "loan-prescription-twenty-year": (
            "vinte anos",
            "20 anos",
            "prazo ordinário",
            "prescrição ordinária",
        ),
    },

    "family-home-own-land": {
        "family-home-article-1726": (
            "artigo 1726",
            "1726.º",
            "1726º",
            "1726",
            "bem comum",
            "mais valiosa",
            "maior valor",
        ),

        "family-home-own-property": (
            "bem próprio",
            "permanece bem próprio",
            "coisa nova",
            "benfeitoria",
            "crédito de compensação",
            "não se aplica o artigo 1726",
            "não se aplica o 1726",
        ),
    },
}


@dataclass
class RetrievedCase:
    case_id: int
    process_number: str
    court: str | None
    decision_date: str | None
    position_id: str
    position_label: str
    quote: str
    score: float


def ensure_fts_table() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS
            rag_documents
            USING fts5(
                issue_slug UNINDEXED,
                case_id UNINDEXED,
                process_number UNINDEXED,
                court UNINDEXED,
                decision_date UNINDEXED,
                position_id UNINDEXED,
                position_label UNINDEXED,
                quote,
                content,
                tokenize='unicode61 remove_diacritics 2'
            )
            """
        )

        connection.commit()


def rebuild_issue_index(
    issue_slug: str,
) -> int:
    ensure_fts_table()

    with get_connection() as connection:
        issue = connection.execute(
            """
            SELECT
                slug
            FROM issues
            WHERE slug = ?
            """,
            (
                issue_slug,
            ),
        ).fetchone()

        if issue is None:
            raise ValueError(
                f"Questão jurídica não encontrada: {issue_slug}"
            )

        rows = connection.execute(
            """
            SELECT
                c.id AS case_id,
                c.process_number,
                c.court,
                c.decision_date,
                c.summary,

                s.position_id,

                p.label AS position_label,

                e.quote

            FROM stances s

            JOIN cases c
                ON c.id = s.case_id

            JOIN positions p
                ON p.id = s.position_id
                AND p.issue_slug = s.issue_slug

            JOIN evidence e
                ON e.stance_id = s.id
                AND e.verified = 1

            WHERE s.issue_slug = ?
              AND s.decides_issue = 1
              AND s.status = 'AUTO'
              AND s.position_id IS NOT NULL

            ORDER BY
                c.decision_date ASC,
                c.process_number ASC
            """,
            (
                issue_slug,
            ),
        ).fetchall()

        connection.execute(
            """
            DELETE FROM rag_documents
            WHERE issue_slug = ?
            """,
            (
                issue_slug,
            ),
        )

        for row in rows:
            summary = (
                row["summary"]
                or ""
            )

            quote = (
                row["quote"]
                or ""
            )

            content = "\n".join(
                part
                for part in (
                    row["position_label"],
                    row["process_number"],
                    row["court"],
                    row["decision_date"],
                    quote,
                    summary,
                )
                if part
            )

            connection.execute(
                """
                INSERT INTO rag_documents (
                    issue_slug,
                    case_id,
                    process_number,
                    court,
                    decision_date,
                    position_id,
                    position_label,
                    quote,
                    content
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    issue_slug,
                    row["case_id"],
                    row["process_number"],
                    row["court"],
                    row["decision_date"],
                    row["position_id"],
                    row["position_label"],
                    quote,
                    content,
                ),
            )

        connection.commit()

    return len(
        rows
    )


def _tokenize_query(
    question: str,
) -> list[str]:
    words = re.findall(
        r"[0-9A-Za-zÀ-ÿºª]+",
        question.casefold(),
    )

    tokens: list[str] = []

    for word in words:
        if (
            len(word) < 3
            or word in STOPWORDS
        ):
            continue

        if word not in tokens:
            tokens.append(
                word
            )

    return tokens[
        :12
    ]


def _fts_query(
    question: str,
) -> str | None:
    tokens = _tokenize_query(
        question
    )

    if not tokens:
        return None

    return " OR ".join(
        f'"{token}"'
        for token in tokens
    )


def _detect_position_intent(
    issue_slug: str,
    question: str,
) -> str | None:
    normalized = (
        question
        .casefold()
        .strip()
    )

    hints_by_position = (
        POSITION_QUERY_HINTS.get(
            issue_slug,
            {},
        )
    )

    if not hints_by_position:
        return None

    scores: dict[
        str,
        int,
    ] = {}

    for (
        position_id,
        hints,
    ) in hints_by_position.items():
        score = sum(
            1
            for hint in hints
            if (
                hint.casefold()
                in normalized
            )
        )

        scores[
            position_id
        ] = score

    best_score = max(
        scores.values(),
        default=0,
    )

    if best_score == 0:
        return None

    winners = [
        position_id
        for (
            position_id,
            score,
        ) in scores.items()
        if score == best_score
    ]

    if len(
        winners
    ) != 1:
        return None

    return winners[
        0
    ]


def _search_rows(
    issue_slug: str,
    fts_query: str,
    limit: int,
    position_id: str | None,
):
    safe_fts_query = (
        fts_query.replace(
            "'",
            "''",
        )
    )

    conditions = [
        "issue_slug = ?",
    ]

    params: list = [
        issue_slug,
    ]

    if position_id:
        conditions.append(
            "position_id = ?"
        )

        params.append(
            position_id
        )

    where_clause = (
        " AND ".join(
            conditions
        )
    )

    params.append(
        limit
    )

    with get_connection() as connection:
        return connection.execute(
            f"""
            SELECT
                case_id,
                process_number,
                court,
                decision_date,
                position_id,
                position_label,
                quote,

                bm25(
                    rag_documents
                ) AS rank

            FROM rag_documents

            WHERE rag_documents MATCH
                '{safe_fts_query}'
              AND {where_clause}

            ORDER BY
                rank ASC

            LIMIT ?
            """,
            tuple(
                params
            ),
        ).fetchall()


def search_issue(
    issue_slug: str,
    question: str,
    limit: int = MAX_RESULTS,
) -> list[RetrievedCase]:
    ensure_fts_table()

    safe_limit = max(
        1,
        min(
            limit,
            10,
        ),
    )

    fts_query = _fts_query(
        question
    )

    if not fts_query:
        return []

    target_position = (
        _detect_position_intent(
            issue_slug,
            question,
        )
    )

    with get_connection() as connection:
        issue = connection.execute(
            """
            SELECT
                slug
            FROM issues
            WHERE slug = ?
            """,
            (
                issue_slug,
            ),
        ).fetchone()

        if issue is None:
            raise ValueError(
                f"Questão jurídica não encontrada: {issue_slug}"
            )

        count = connection.execute(
            """
            SELECT
                COUNT(*) AS total
            FROM rag_documents
            WHERE issue_slug = ?
            """,
            (
                issue_slug,
            ),
        ).fetchone()

    if (
        count is None
        or count["total"] == 0
    ):
        rebuild_issue_index(
            issue_slug
        )

    rows = _search_rows(
        issue_slug=issue_slug,
        fts_query=fts_query,
        limit=safe_limit,
        position_id=target_position,
    )

    # Se a pergunta apontava claramente para
    # uma posição mas os termos lexicais não
    # encontraram nada, não vamos buscar a
    # posição contrária silenciosamente.
    #
    # Fazemos antes um fallback para decisões
    # validadas dessa mesma posição.
    if (
        not rows
        and target_position
    ):
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    case_id,
                    process_number,
                    court,
                    decision_date,
                    position_id,
                    position_label,
                    quote,
                    0.0 AS rank

                FROM rag_documents

                WHERE issue_slug = ?
                  AND position_id = ?

                ORDER BY
                    decision_date DESC,
                    case_id DESC

                LIMIT ?
                """,
                (
                    issue_slug,
                    target_position,
                    safe_limit,
                ),
            ).fetchall()

    return [
        RetrievedCase(
            case_id=row[
                "case_id"
            ],
            process_number=row[
                "process_number"
            ],
            court=row[
                "court"
            ],
            decision_date=row[
                "decision_date"
            ],
            position_id=row[
                "position_id"
            ],
            position_label=row[
                "position_label"
            ],
            quote=row[
                "quote"
            ],
            score=float(
                row[
                    "rank"
                ]
            ),
        )
        for row in rows
    ]


def search_issue_dicts(
    issue_slug: str,
    question: str,
    limit: int = MAX_RESULTS,
) -> list[dict]:
    return [
        asdict(
            result
        )
        for result in search_issue(
            issue_slug,
            question,
            limit,
        )
    ]