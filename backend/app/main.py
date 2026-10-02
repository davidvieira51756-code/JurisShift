from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.db.database import (
    get_connection,
    init_db,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="JurisShift API",
    version="0.1.0",
    description=(
        "API de exploração da evolução "
        "e divergência jurisprudencial."
    ),
    lifespan=lifespan,
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
                COUNT(DISTINCT s.case_id) AS analyzed_cases,
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
            "analyzed_cases": row["analyzed_cases"] or 0,
            "deciding_cases": row["deciding_cases"] or 0,
            "review_cases": row["review_cases"] or 0,
        }
        for row in issues
    ]


@app.get("/api/issues/{issue_slug}")
def get_issue(issue_slug: str):
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
            (issue_slug,),
        ).fetchone()

        if issue is None:
            raise HTTPException(
                status_code=404,
                detail="Questão jurídica não encontrada.",
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
            (issue_slug,),
        ).fetchall()

        stats = connection.execute(
            """
            SELECT
                COUNT(*) AS analyzed_cases,

                SUM(
                    CASE
                        WHEN decides_issue = 1
                        THEN 1
                        ELSE 0
                    END
                ) AS deciding_cases,

                SUM(
                    CASE
                        WHEN decides_issue = 0
                        THEN 1
                        ELSE 0
                    END
                ) AS non_deciding_cases,

                SUM(
                    CASE
                        WHEN status = 'AUTO'
                        THEN 1
                        ELSE 0
                    END
                ) AS auto_cases,

                SUM(
                    CASE
                        WHEN status = 'REVIEW'
                        THEN 1
                        ELSE 0
                    END
                ) AS review_cases,

                COUNT(
                    DISTINCT CASE
                        WHEN decides_issue = 1
                        THEN position_id
                    END
                ) AS represented_positions
            FROM stances
            WHERE issue_slug = ?
            """,
            (issue_slug,),
        ).fetchone()

        verified_evidence = connection.execute(
            """
            SELECT COUNT(DISTINCT e.stance_id) AS total
            FROM evidence e
            JOIN stances s
                ON s.id = e.stance_id
            WHERE s.issue_slug = ?
              AND e.verified = 1
            """,
            (issue_slug,),
        ).fetchone()

    represented_positions = (
        stats["represented_positions"]
        if stats
        else 0
    )

    return {
        "slug": issue["slug"],
        "title": issue["title"],
        "question": issue["question"],
        "source": issue["source"],

        "landmark": {
            "label": issue["source"],
            "year": 2022,
        },

        "stats": {
            "analyzed_cases": stats["analyzed_cases"] or 0,
            "deciding_cases": stats["deciding_cases"] or 0,
            "non_deciding_cases": (
                stats["non_deciding_cases"] or 0
            ),
            "auto_cases": stats["auto_cases"] or 0,
            "review_cases": stats["review_cases"] or 0,
            "verified_evidence_cases": (
                verified_evidence["total"] or 0
            ),
            "represented_positions": (
                represented_positions or 0
            ),
            "divergence_detected": (
                represented_positions >= 2
            ),
        },

        "positions": [
            {
                "id": row["id"],
                "label": row["label"],
                "description": row["description"],
                "case_count": row["case_count"] or 0,
            }
            for row in positions
        ],
    }


@app.get("/api/issues/{issue_slug}/timeline")
def get_timeline(issue_slug: str):
    with get_connection() as connection:
        exists = connection.execute(
            """
            SELECT 1
            FROM issues
            WHERE slug = ?
            """,
            (issue_slug,),
        ).fetchone()

        if exists is None:
            raise HTTPException(
                status_code=404,
                detail="Questão jurídica não encontrada.",
            )

        positions = connection.execute(
            """
            SELECT id
            FROM positions
            WHERE issue_slug = ?
            ORDER BY id
            """,
            (issue_slug,),
        ).fetchall()

        rows = connection.execute(
            """
            SELECT
                substr(c.decision_date, 1, 4) AS year,
                s.position_id,
                COUNT(*) AS total
            FROM stances s
            JOIN cases c
                ON c.id = s.case_id
            WHERE s.issue_slug = ?
              AND s.decides_issue = 1
              AND s.position_id IS NOT NULL
              AND c.decision_date IS NOT NULL
            GROUP BY
                substr(c.decision_date, 1, 4),
                s.position_id
            ORDER BY
                year,
                s.position_id
            """,
            (issue_slug,),
        ).fetchall()

    position_ids = [
        row["id"]
        for row in positions
    ]

    years: dict[int, dict] = {}

    for row in rows:
        try:
            year = int(
                row["year"]
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        if year not in years:
            years[year] = {
                "year": year,
                "total_decisions": 0,
                "positions": {
                    position_id: 0
                    for position_id
                    in position_ids
                },
            }

        years[year]["positions"][
            row["position_id"]
        ] = row["total"]

        years[year]["total_decisions"] += (
            row["total"]
        )

    return {
        "landmark": {
            "label": "AUJ 6/2022",
            "year": 2022,
        },
        "years": [
            years[year]
            for year in sorted(years)
        ],
    }


@app.get("/api/issues/{issue_slug}/cases")
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
            (issue_slug,),
        ).fetchone()

        if exists is None:
            raise HTTPException(
                status_code=404,
                detail="Questão jurídica não encontrada.",
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
                int(decides_issue)
            )

        where_clause = " AND ".join(
            conditions
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

                p.label AS position_label,

                (
                    SELECT e.quote
                    FROM evidence e
                    WHERE e.stance_id = s.id
                      AND e.verified = 1
                    ORDER BY e.id
                    LIMIT 1
                ) AS evidence_quote,

                (
                    SELECT e.role
                    FROM evidence e
                    WHERE e.stance_id = s.id
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
            tuple(params),
        ).fetchall()

    return {
        "total": len(rows),
        "cases": [
            {
                "id": row["id"],
                "ecli": row["ecli"],
                "process_number": (
                    row["process_number"]
                ),
                "court": row["court"],
                "section": row["section"],
                "area": row["area"],
                "decision_date": (
                    row["decision_date"]
                ),
                "rapporteur": row["rapporteur"],
                "procedural_type": (
                    row["procedural_type"]
                ),
                "decision": row["decision"],
                "voting": row["voting"],
                "summary": row["summary"],
                "source_url": row["source_url"],

                "stance": {
                    "decides_issue": bool(
                        row["decides_issue"]
                    ),
                    "position_id": (
                        row["position_id"]
                    ),
                    "position_label": (
                        row["position_label"]
                    ),
                    "status": row["status"],
                    "model": (
                        row["extraction_model"]
                    ),
                    "prompt_version": (
                        row["prompt_version"]
                    ),
                },

                "evidence": (
                    {
                        "quote": (
                            row["evidence_quote"]
                        ),
                        "role": (
                            row["evidence_role"]
                        ),
                        "verified": True,
                    }
                    if row["evidence_quote"]
                    else None
                ),
            }
            for row in rows
        ],
    }