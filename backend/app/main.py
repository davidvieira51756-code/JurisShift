import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

from backend.db.database import get_connection, init_db
from backend.rag.chat import answer_issue_question

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="JurisShift API",
    version="0.1.0",
    description="API de exploração da evolução e divergência jurisprudencial.",
    lifespan=lifespan,
)

class ChatRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=1500,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _is_sentence_end(character: str) -> bool:
    return character in ".!?:;"


def _snap_context_start(
    text: str,
    preferred_start: int,
    evidence_start: int,
    tolerance: int = 220,
) -> int:
    if preferred_start <= 0:
        return 0

    earliest = max(
        0,
        preferred_start - tolerance,
    )

    latest = min(
        evidence_start,
        preferred_start + tolerance,
    )

    candidates: list[int] = []

    for separator in (
        "\n\n",
        "\r\n\r\n",
        "\n",
    ):
        index = text.rfind(
            separator,
            earliest,
            latest,
        )

        if index != -1:
            candidates.append(
                index + len(separator)
            )

    for index in range(
        latest - 1,
        earliest - 1,
        -1,
    ):
        if _is_sentence_end(
            text[index]
        ):
            candidates.append(
                index + 1
            )
            break

    if not candidates:
        return preferred_start

    return min(
        candidates,
        key=lambda candidate: abs(
            candidate - preferred_start
        ),
    )


def _snap_context_end(
    text: str,
    evidence_end: int,
    preferred_end: int,
    tolerance: int = 220,
) -> int:
    if preferred_end >= len(text):
        return len(text)

    earliest = max(
        evidence_end,
        preferred_end - tolerance,
    )

    latest = min(
        len(text),
        preferred_end + tolerance,
    )

    candidates: list[int] = []

    for separator in (
        "\n\n",
        "\r\n\r\n",
        "\n",
    ):
        index = text.find(
            separator,
            earliest,
            latest,
        )

        if index != -1:
            candidates.append(
                index
            )

    for index in range(
        earliest,
        latest,
    ):
        if _is_sentence_end(
            text[index]
        ):
            candidates.append(
                index + 1
            )
            break

    if not candidates:
        return preferred_end

    return min(
        candidates,
        key=lambda candidate: abs(
            candidate - preferred_end
        ),
    )


def _get_evidence_context(
    *,
    summary: str | None,
    full_text: str | None,
    role: str | None,
    start_offset: int | None,
    end_offset: int | None,
    quote: str | None,
    radius: int = 500,
) -> dict | None:
    if not quote:
        return None

    source_name = (
        "summary"
        if (
            role
            and "summary"
            in role.casefold()
        )
        else "full_text"
    )

    source_text = (
        summary
        if source_name == "summary"
        else full_text
    )

    source_text = (
        source_text
        or ""
    )

    if (
        start_offset is None
        or end_offset is None
        or start_offset < 0
        or end_offset < start_offset
        or start_offset > len(source_text)
    ):
        return {
            "source": source_name,
            "before": "",
            "quote": quote,
            "after": "",
        }

    safe_end = min(
        end_offset,
        len(source_text),
    )

    before_start = (
        _snap_context_start(
            source_text,
            max(
                0,
                start_offset - radius,
            ),
            start_offset,
        )
    )

    after_end = (
        _snap_context_end(
            source_text,
            safe_end,
            min(
                len(source_text),
                safe_end + radius,
            ),
        )
    )

    return {
        "source": source_name,
        "before": source_text[
            before_start:start_offset
        ].strip(),
        "quote": (
            source_text[
                start_offset:safe_end
            ].strip()
            or quote
        ),
        "after": source_text[
            safe_end:after_end
        ].strip(),
    }


def _get_landmark(
    source: str | None,
) -> dict:
    if not source:
        return {
            "label": None,
            "year": None,
        }

    match = re.search(
        r"n\.?\s*º?\s*(\d+)\s*/\s*(\d{4})",
        source,
        flags=re.IGNORECASE,
    )

    if match is None:
        return {
            "label": source,
            "year": None,
        }

    number = match.group(1)

    year = int(
        match.group(2)
    )

    return {
        "label": (
            f"AUJ {number}/{year}"
        ),
        "year": year,
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "jurisshift",
    }


@app.get("/api/issues")
def list_issues():
    with get_connection() as connection:
        issues = connection.execute(
            """
            SELECT
                i.slug,
                i.title,
                i.question,
                i.source,

                COUNT(
                    DISTINCT s.case_id
                ) AS analyzed_cases,

                SUM(
                    CASE
                        WHEN s.decides_issue = 1
                        THEN 1
                        ELSE 0
                    END
                ) AS deciding_cases,

                SUM(
                    CASE
                        WHEN s.status = 'REVIEW'
                        THEN 1
                        ELSE 0
                    END
                ) AS review_cases

            FROM issues i

            LEFT JOIN stances s
                ON s.issue_slug = i.slug

            GROUP BY
                i.slug,
                i.title,
                i.question,
                i.source

            ORDER BY i.title
            """
        ).fetchall()

    return [
        {
            "slug": row["slug"],
            "title": row["title"],
            "question": row["question"],
            "source": row["source"],
            "analyzed_cases": (
                row["analyzed_cases"]
                or 0
            ),
            "deciding_cases": (
                row["deciding_cases"]
                or 0
            ),
            "review_cases": (
                row["review_cases"]
                or 0
            ),
        }
        for row in issues
    ]


@app.get(
    "/api/issues/{issue_slug}"
)
def get_issue(
    issue_slug: str,
):
    with get_connection() as connection:
        issue = connection.execute(
            """
            SELECT
                slug,
                title,
                question,
                source

            FROM issues

            WHERE slug = ?
            """,
            (
                issue_slug,
            ),
        ).fetchone()

        if issue is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Questão jurídica "
                    "não encontrada."
                ),
            )

        positions = connection.execute(
            """
            SELECT
                p.id,
                p.label,
                p.description,

                COUNT(
                    CASE
                        WHEN s.decides_issue = 1
                         AND s.status = 'AUTO'
                         AND EXISTS (
                             SELECT 1
                             FROM evidence ev
                             WHERE ev.stance_id = s.id
                               AND ev.verified = 1
                         )
                        THEN 1
                    END
                ) AS case_count

            FROM positions p

            LEFT JOIN stances s
                ON s.position_id = p.id
                AND s.issue_slug = p.issue_slug

            WHERE p.issue_slug = ?

            GROUP BY
                p.id,
                p.label,
                p.description

            ORDER BY p.id
            """,
            (
                issue_slug,
            ),
        ).fetchall()

        stats = connection.execute(
            """
            SELECT
                COUNT(*) AS analyzed_cases,

                SUM(
                    CASE
                        WHEN s.decides_issue = 1
                        THEN 1
                        ELSE 0
                    END
                ) AS deciding_cases,

                SUM(
                    CASE
                        WHEN s.decides_issue = 0
                        THEN 1
                        ELSE 0
                    END
                ) AS non_deciding_cases,

                SUM(
                    CASE
                        WHEN s.status = 'AUTO'
                        THEN 1
                        ELSE 0
                    END
                ) AS auto_cases,

                SUM(
                    CASE
                        WHEN s.status = 'REVIEW'
                        THEN 1
                        ELSE 0
                    END
                ) AS review_cases,

                SUM(
                    CASE
                        WHEN s.decides_issue = 1
                         AND s.status = 'AUTO'
                         AND s.position_id IS NOT NULL
                         AND EXISTS (
                             SELECT 1
                             FROM evidence ev
                             WHERE ev.stance_id = s.id
                               AND ev.verified = 1
                         )
                        THEN 1
                        ELSE 0
                    END
                ) AS validated_deciding_cases,

                COUNT(
                    DISTINCT CASE
                        WHEN s.decides_issue = 1
                         AND s.status = 'AUTO'
                         AND s.position_id IS NOT NULL
                         AND EXISTS (
                             SELECT 1
                             FROM evidence ev
                             WHERE ev.stance_id = s.id
                               AND ev.verified = 1
                         )
                        THEN s.position_id
                    END
                ) AS represented_positions

            FROM stances s

            WHERE s.issue_slug = ?
            """,
            (
                issue_slug,
            ),
        ).fetchone()

        verified_evidence = (
            connection.execute(
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
                    issue_slug,
                ),
            ).fetchone()
        )

        position_ranges = (
            connection.execute(
                """
                SELECT
                    s.position_id,
                    p.label,

                    MIN(
                        c.decision_date
                    ) AS first_date,

                    MAX(
                        c.decision_date
                    ) AS last_date,

                    COUNT(*) AS total

                FROM stances s

                JOIN cases c
                    ON c.id = s.case_id

                JOIN positions p
                    ON p.id = s.position_id
                    AND p.issue_slug = s.issue_slug

                WHERE s.issue_slug = ?
                  AND s.decides_issue = 1
                  AND s.status = 'AUTO'
                  AND s.position_id IS NOT NULL
                  AND c.decision_date IS NOT NULL
                  AND EXISTS (
                      SELECT 1
                      FROM evidence ev
                      WHERE ev.stance_id = s.id
                        AND ev.verified = 1
                  )

                GROUP BY
                    s.position_id,
                    p.label

                ORDER BY
                    first_date,
                    s.position_id
                """,
                (
                    issue_slug,
                ),
            ).fetchall()
        )

    represented_positions = (
        stats[
            "represented_positions"
        ]
        if stats
        else 0
    )

    ranges = [
        {
            "position_id": (
                row[
                    "position_id"
                ]
            ),
            "label": (
                row[
                    "label"
                ]
            ),
            "first_date": (
                row[
                    "first_date"
                ]
            ),
            "last_date": (
                row[
                    "last_date"
                ]
            ),
            "total": (
                row[
                    "total"
                ]
            ),
        }
        for row
        in position_ranges
    ]

    overlaps = []

    for index, first in enumerate(
        ranges
    ):
        for second in ranges[
            index + 1:
        ]:
            overlap_start = max(
                first[
                    "first_date"
                ],
                second[
                    "first_date"
                ],
            )

            overlap_end = min(
                first[
                    "last_date"
                ],
                second[
                    "last_date"
                ],
            )

            if (
                overlap_start
                <= overlap_end
            ):
                overlaps.append(
                    {
                        "position_a": (
                            first[
                                "position_id"
                            ]
                        ),
                        "position_b": (
                            second[
                                "position_id"
                            ]
                        ),
                        "start_date": (
                            overlap_start
                        ),
                        "end_date": (
                            overlap_end
                        ),
                    }
                )

    return {
        "slug": (
            issue[
                "slug"
            ]
        ),
        "title": (
            issue[
                "title"
            ]
        ),
        "question": (
            issue[
                "question"
            ]
        ),
        "source": (
            issue[
                "source"
            ]
        ),

        "landmark": (
            _get_landmark(
                issue[
                    "source"
                ]
            )
        ),

        "stats": {
            "analyzed_cases": (
                stats[
                    "analyzed_cases"
                ]
                or 0
            ),
            "deciding_cases": (
                stats[
                    "deciding_cases"
                ]
                or 0
            ),
            "non_deciding_cases": (
                stats[
                    "non_deciding_cases"
                ]
                or 0
            ),
            "auto_cases": (
                stats[
                    "auto_cases"
                ]
                or 0
            ),
            "review_cases": (
                stats[
                    "review_cases"
                ]
                or 0
            ),
            "verified_evidence_cases": (
                verified_evidence[
                    "total"
                ]
                or 0
            ),
            "represented_positions": (
                represented_positions
                or 0
            ),
            "validated_deciding_cases": (
                stats[
                    "validated_deciding_cases"
                ]
                or 0
            ),
            "divergence_detected": (
                represented_positions
                >= 2
            ),
        },

        "positions": [
            {
                "id": (
                    row[
                        "id"
                    ]
                ),
                "label": (
                    row[
                        "label"
                    ]
                ),
                "description": (
                    row[
                        "description"
                    ]
                ),
                "case_count": (
                    row[
                        "case_count"
                    ]
                    or 0
                ),
            }
            for row
            in positions
        ],

        "divergence_analysis": {
            "detected": (
                represented_positions
                >= 2
            ),
            "validated_decisions": (
                stats[
                    "validated_deciding_cases"
                ]
                or 0
            ),
            "position_ranges": (
                ranges
            ),
            "overlaps": (
                overlaps
            ),
            "scope_note": (
                "Resultado calculado "
                "apenas a partir de "
                "decisões AUTO com "
                "evidência verificada "
                "no corpus analisado."
            ),
        },
    }


@app.get(
    "/api/issues/"
    "{issue_slug}/timeline"
)
def get_timeline(
    issue_slug: str,
):
    with get_connection() as connection:
        issue = connection.execute(
            """
            SELECT
                slug,
                source

            FROM issues

            WHERE slug = ?
            """,
            (
                issue_slug,
            ),
        ).fetchone()

        if issue is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Questão jurídica "
                    "não encontrada."
                ),
            )

        positions = connection.execute(
            """
            SELECT
                id

            FROM positions

            WHERE issue_slug = ?

            ORDER BY id
            """,
            (
                issue_slug,
            ),
        ).fetchall()

        rows = connection.execute(
            """
            SELECT
                substr(
                    c.decision_date,
                    1,
                    4
                ) AS year,

                s.position_id,

                COUNT(*) AS total

            FROM stances s

            JOIN cases c
                ON c.id = s.case_id

            WHERE s.issue_slug = ?
              AND s.decides_issue = 1
              AND s.status = 'AUTO'
              AND s.position_id IS NOT NULL
              AND c.decision_date IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM evidence ev
                  WHERE ev.stance_id = s.id
                    AND ev.verified = 1
              )

            GROUP BY
                substr(
                    c.decision_date,
                    1,
                    4
                ),
                s.position_id

            ORDER BY
                year,
                s.position_id
            """,
            (
                issue_slug,
            ),
        ).fetchall()

    position_ids = [
        row[
            "id"
        ]
        for row
        in positions
    ]

    years: dict[
        int,
        dict,
    ] = {}

    for row in rows:
        try:
            year = int(
                row[
                    "year"
                ]
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if year not in years:
            years[
                year
            ] = {
                "year": (
                    year
                ),
                "total_decisions": 0,
                "positions": {
                    position_id: 0
                    for position_id
                    in position_ids
                },
            }

        years[
            year
        ][
            "positions"
        ][
            row[
                "position_id"
            ]
        ] = row[
            "total"
        ]

        years[
            year
        ][
            "total_decisions"
        ] += row[
            "total"
        ]

    return {
        "landmark": (
            _get_landmark(
                issue[
                    "source"
                ]
            )
        ),

        "years": [
            years[
                year
            ]
            for year
            in sorted(
                years
            )
        ],
    }


@app.get(
    "/api/issues/"
    "{issue_slug}/cases"
)
def get_cases(
    issue_slug: str,
    position_id: str | None = Query(
        default=None
    ),
    status: str | None = Query(
        default=None
    ),
    decides_issue: bool | None = Query(
        default=None
    ),
):
    with get_connection() as connection:
        exists = connection.execute(
            """
            SELECT 1

            FROM issues

            WHERE slug = ?
            """,
            (
                issue_slug,
            ),
        ).fetchone()

        if exists is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Questão jurídica "
                    "não encontrada."
                ),
            )

        conditions = [
            "s.issue_slug = ?"
        ]

        params: list = [
            issue_slug
        ]

        if position_id is not None:
            conditions.append(
                "s.position_id = ?"
            )

            params.append(
                position_id
            )

        if status is not None:
            conditions.append(
                "s.status = ?"
            )

            params.append(
                status.upper()
            )

        if decides_issue is not None:
            conditions.append(
                "s.decides_issue = ?"
            )

            params.append(
                int(
                    decides_issue
                )
            )

        where_clause = (
            " AND ".join(
                conditions
            )
        )

        rows = connection.execute(
            f"""
            SELECT
                c.id,
                c.ecli,
                c.process_number,
                c.court,
                c.section,
                c.area,
                c.decision_date,
                c.rapporteur,
                c.procedural_type,
                c.decision,
                c.voting,
                c.summary,
                c.source_url,

                s.position_id,
                s.decides_issue,
                s.status,
                s.extraction_model,
                s.prompt_version,

                p.label
                    AS position_label,

                (
                    SELECT e.quote

                    FROM evidence e

                    WHERE
                        e.stance_id = s.id
                        AND e.verified = 1

                    ORDER BY e.id

                    LIMIT 1
                ) AS evidence_quote,

                (
                    SELECT e.role

                    FROM evidence e

                    WHERE
                        e.stance_id = s.id
                        AND e.verified = 1

                    ORDER BY e.id

                    LIMIT 1
                ) AS evidence_role

            FROM stances s

            JOIN cases c
                ON c.id = s.case_id

            LEFT JOIN positions p
                ON p.id = s.position_id
                AND p.issue_slug = s.issue_slug

            WHERE {where_clause}

            ORDER BY
                c.decision_date ASC,
                c.process_number ASC
            """,
            tuple(
                params
            ),
        ).fetchall()

    return {
        "total": (
            len(
                rows
            )
        ),

        "cases": [
            {
                "id": (
                    row[
                        "id"
                    ]
                ),
                "ecli": (
                    row[
                        "ecli"
                    ]
                ),
                "process_number": (
                    row[
                        "process_number"
                    ]
                ),
                "court": (
                    row[
                        "court"
                    ]
                ),
                "section": (
                    row[
                        "section"
                    ]
                ),
                "area": (
                    row[
                        "area"
                    ]
                ),
                "decision_date": (
                    row[
                        "decision_date"
                    ]
                ),
                "rapporteur": (
                    row[
                        "rapporteur"
                    ]
                ),
                "procedural_type": (
                    row[
                        "procedural_type"
                    ]
                ),
                "decision": (
                    row[
                        "decision"
                    ]
                ),
                "voting": (
                    row[
                        "voting"
                    ]
                ),
                "summary": (
                    row[
                        "summary"
                    ]
                ),
                "source_url": (
                    row[
                        "source_url"
                    ]
                ),

                "stance": {
                    "decides_issue": (
                        bool(
                            row[
                                "decides_issue"
                            ]
                        )
                    ),
                    "position_id": (
                        row[
                            "position_id"
                        ]
                    ),
                    "position_label": (
                        row[
                            "position_label"
                        ]
                    ),
                    "status": (
                        row[
                            "status"
                        ]
                    ),
                    "model": (
                        row[
                            "extraction_model"
                        ]
                    ),
                    "prompt_version": (
                        row[
                            "prompt_version"
                        ]
                    ),
                },

                "evidence": (
                    {
                        "quote": (
                            row[
                                "evidence_quote"
                            ]
                        ),
                        "role": (
                            row[
                                "evidence_role"
                            ]
                        ),
                        "verified": True,
                    }
                    if row[
                        "evidence_quote"
                    ]
                    else None
                ),
            }
            for row
            in rows
        ],
    }


@app.get(
    "/api/issues/"
    "{issue_slug}/cases/"
    "{case_id}"
)
def get_case_detail(
    issue_slug: str,
    case_id: int,
):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                c.id,
                c.ecli,
                c.process_number,
                c.court,
                c.section,
                c.area,
                c.decision_date,
                c.rapporteur,
                c.procedural_type,
                c.decision,
                c.voting,
                c.summary,
                c.full_text,
                c.source_url,

                i.slug AS issue_slug,
                i.title AS issue_title,
                i.question AS issue_question,
                i.source AS issue_source,

                s.decides_issue,
                s.status,
                s.extraction_model,
                s.prompt_version,

                p.id AS position_id,
                p.label AS position_label,
                p.description
                    AS position_description,

                e.id AS evidence_id,
                e.quote AS evidence_quote,
                e.role AS evidence_role,

                e.start_offset
                    AS evidence_start_offset,

                e.end_offset
                    AS evidence_end_offset,

                e.verified
                    AS evidence_verified

            FROM cases c

            JOIN stances s
                ON s.case_id = c.id

            JOIN issues i
                ON i.slug = s.issue_slug

            LEFT JOIN positions p
                ON p.id = s.position_id
                AND p.issue_slug = s.issue_slug

            LEFT JOIN evidence e
                ON e.stance_id = s.id
                AND e.verified = 1

            WHERE c.id = ?
              AND s.issue_slug = ?

            ORDER BY
                e.id ASC
            """,
            (
                case_id,
                issue_slug,
            ),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Acórdão não "
                "encontrado."
            ),
        )

    evidence_context = (
        _get_evidence_context(
            summary=(
                row[
                    "summary"
                ]
            ),
            full_text=(
                row[
                    "full_text"
                ]
            ),
            role=(
                row[
                    "evidence_role"
                ]
            ),
            start_offset=(
                row[
                    "evidence_start_offset"
                ]
            ),
            end_offset=(
                row[
                    "evidence_end_offset"
                ]
            ),
            quote=(
                row[
                    "evidence_quote"
                ]
            ),
        )
    )

    return {
        "id": (
            row[
                "id"
            ]
        ),
        "ecli": (
            row[
                "ecli"
            ]
        ),
        "process_number": (
            row[
                "process_number"
            ]
        ),
        "court": (
            row[
                "court"
            ]
        ),
        "section": (
            row[
                "section"
            ]
        ),
        "area": (
            row[
                "area"
            ]
        ),
        "decision_date": (
            row[
                "decision_date"
            ]
        ),
        "rapporteur": (
            row[
                "rapporteur"
            ]
        ),
        "procedural_type": (
            row[
                "procedural_type"
            ]
        ),
        "decision": (
            row[
                "decision"
            ]
        ),
        "voting": (
            row[
                "voting"
            ]
        ),
        "source_url": (
            row[
                "source_url"
            ]
        ),

        "issue": (
            {
                "slug": (
                    row[
                        "issue_slug"
                    ]
                ),
                "title": (
                    row[
                        "issue_title"
                    ]
                ),
                "question": (
                    row[
                        "issue_question"
                    ]
                ),
                "source": (
                    row[
                        "issue_source"
                    ]
                ),
            }
            if row[
                "issue_slug"
            ]
            else None
        ),

        "position": (
            {
                "id": (
                    row[
                        "position_id"
                    ]
                ),
                "label": (
                    row[
                        "position_label"
                    ]
                ),
                "description": (
                    row[
                        "position_description"
                    ]
                ),
            }
            if row[
                "position_id"
            ]
            else None
        ),

        "decides_issue": (
            bool(
                row[
                    "decides_issue"
                ]
            )
            if row[
                "decides_issue"
            ]
            is not None
            else False
        ),

        "status": (
            row[
                "status"
            ]
        ),

        "model": (
            row[
                "extraction_model"
            ]
        ),

        "prompt_version": (
            row[
                "prompt_version"
            ]
        ),

        "evidence": (
            {
                "id": (
                    row[
                        "evidence_id"
                    ]
                ),
                "quote": (
                    row[
                        "evidence_quote"
                    ]
                ),
                "role": (
                    row[
                        "evidence_role"
                    ]
                ),
                "verified": (
                    bool(
                        row[
                            "evidence_verified"
                        ]
                    )
                ),
                "context": (
                    evidence_context
                ),
            }
            if row[
                "evidence_id"
            ]
            else None
        ),
    }
    
@app.post(
    "/api/issues/{issue_slug}/chat"
)
def chat_issue(
    issue_slug: str,
    payload: ChatRequest,
):
    question = (
        payload.question
        .strip()
    )

    if not question:
        raise HTTPException(
            status_code=400,
            detail=(
                "A pergunta não pode "
                "estar vazia."
            ),
        )

    with get_connection() as connection:
        issue = connection.execute(
            """
            SELECT slug
            FROM issues
            WHERE slug = ?
            """,
            (
                issue_slug,
            ),
        ).fetchone()

    if issue is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Questão jurídica "
                "não encontrada."
            ),
        )

    try:
        return answer_issue_question(
            issue_slug,
            question,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Não foi possível gerar "
                "a resposta do assistente."
            ),
        ) from exc