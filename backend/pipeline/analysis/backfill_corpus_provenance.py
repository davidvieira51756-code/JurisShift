from backend.db.database import (
    get_connection,
    init_db,
)


ISSUE = "loan-prescription-acceleration"


CURATED_PROCESSES = {
    "525/14.0TBMGR-A.C1",
    "589/15.0T8VNF-A.G1",
    "2483/15.5T8ENT-A.E1",
    "17012/17.8YIPRT.C1",
    "8636/16.1T8LRS-A.L1-7",
}


GAP_FILL_PROCESSES = {
    "2483/15.5T8ENT-A.E1.S1",
    "805/18.6T8OVR-A.P1.S1",
    "7214/18.5T8STB-A.E1.S1",
}


def main():
    init_db()

    with get_connection() as connection:
        cases = connection.execute(
            """
            SELECT DISTINCT
                c.id,
                c.process_number
            FROM cases c
            JOIN stances s
              ON s.case_id = c.id
            WHERE s.issue_slug = ?
            """,
            (ISSUE,),
        ).fetchall()

        for case in cases:
            process = case["process_number"]
            process_key = process.replace(" ", "")

            if process_key in CURATED_PROCESSES:
                method = "curated"
                note = (
                    "Decisão adicionada deliberadamente "
                    "para representar a corrente jurisprudencial "
                    "do prazo ordinário."
                )

            elif process_key in GAP_FILL_PROCESSES:
                method = "gap_fill"
                note = (
                    "Decisão identificada durante a auditoria "
                    "do corpus para reduzir lacunas temporais "
                    "e de orientação jurisprudencial."
                )

            else:
                method = "search"
                note = (
                    "Decisão incluída através da recolha "
                    "principal do corpus."
                )

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
                    inclusion_method =
                        excluded.inclusion_method,
                    inclusion_note =
                        excluded.inclusion_note
                """,
                (
                    case["id"],
                    ISSUE,
                    method,
                    note,
                ),
            )

        connection.commit()

        rows = connection.execute(
            """
            SELECT
                cm.inclusion_method,
                COUNT(*) AS total
            FROM corpus_membership cm
            WHERE cm.issue_slug = ?
            GROUP BY cm.inclusion_method
            ORDER BY cm.inclusion_method
            """,
            (ISSUE,),
        ).fetchall()

        print()
        print("=== PROVENIÊNCIA DO CORPUS ===")

        for row in rows:
            print(dict(row))


if __name__ == "__main__":
    main()