import hashlib
import json
from datetime import datetime, timezone

from backend.db.database import get_connection
from backend.pipeline.ingestion.stj_parser import StjCase


def _hash_text(text: str | None) -> str | None:
    if not text:
        return None

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def save_case(case: StjCase) -> int:
    descriptors_json = json.dumps(
        case.descriptors,
        ensure_ascii=False,
    )

    text_hash = _hash_text(
        case.full_text
    )

    fetched_at = datetime.now(
        timezone.utc
    ).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO cases (
                ecli,
                process_number,
                court,
                section,
                area,
                decision_date,
                rapporteur,
                descriptors_json,
                procedural_type,
                decision,
                voting,
                summary,
                full_text,
                text_hash,
                source_url,
                fetched_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            )

            ON CONFLICT(source_url)
            DO UPDATE SET
                ecli = excluded.ecli,
                process_number = excluded.process_number,
                court = excluded.court,
                section = excluded.section,
                area = excluded.area,
                decision_date = excluded.decision_date,
                rapporteur = excluded.rapporteur,
                descriptors_json = excluded.descriptors_json,
                procedural_type = excluded.procedural_type,
                decision = excluded.decision,
                voting = excluded.voting,
                summary = excluded.summary,
                full_text = excluded.full_text,
                text_hash = excluded.text_hash,
                fetched_at = excluded.fetched_at
            """,
            (
                case.ecli,
                case.process_number,
                "STJ",
                case.section,
                case.area,
                case.decision_date,
                case.rapporteur,
                descriptors_json,
                case.procedural_type,
                case.decision,
                case.voting,
                case.summary,
                case.full_text,
                text_hash,
                case.source_url,
                fetched_at,
            ),
        )

        row = connection.execute(
            """
            SELECT id
            FROM cases
            WHERE source_url = ?
            """,
            (
                case.source_url,
            ),
        ).fetchone()

        connection.commit()

        return row["id"]


def get_case(case_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM cases
            WHERE id = ?
            """,
            (
                case_id,
            ),
        ).fetchone()

    if row is None:
        return None

    result = dict(row)

    result["descriptors"] = json.loads(
        result.pop(
            "descriptors_json"
        )
        or "[]"
    )

    return result


def count_cases() -> int:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT COUNT(*)
            FROM cases
            """
        ).fetchone()[0]