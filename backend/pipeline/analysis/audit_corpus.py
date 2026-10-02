from collections import defaultdict

from backend.db.database import (
    get_connection,
    init_db,
)


ISSUE = "loan-prescription-acceleration"

FIVE_YEAR = "loan-prescription-five-year"
TWENTY_YEAR = "loan-prescription-twenty-year"


def short_position(position_id):
    if position_id == FIVE_YEAR:
        return "5 anos"

    if position_id == TWENTY_YEAR:
        return "20 anos"

    if position_id is None:
        return "SEM POSIÇÃO"

    return position_id


def main():
    init_db()

    with get_connection() as connection:
        print()
        print("=" * 90)
        print("JURISSHIFT — AUDITORIA DO CORPUS")
        print("=" * 90)

        # --------------------------------------------------
        # 1. RESUMO GERAL
        # --------------------------------------------------

        print("\n=== RESUMO GERAL ===")

        rows = connection.execute(
            """
            SELECT
                cm.inclusion_method,
                s.position_id,
                s.decides_issue,
                s.status,
                COUNT(*) AS total
            FROM corpus_membership cm

            JOIN stances s
              ON s.case_id = cm.case_id
             AND s.issue_slug = cm.issue_slug

            WHERE cm.issue_slug = ?

            GROUP BY
                cm.inclusion_method,
                s.position_id,
                s.decides_issue,
                s.status

            ORDER BY
                cm.inclusion_method,
                s.position_id,
                s.status
            """,
            (ISSUE,),
        ).fetchall()

        for row in rows:
            print(
                {
                    "origem": row["inclusion_method"],
                    "posição": short_position(
                        row["position_id"]
                    ),
                    "decide": bool(
                        row["decides_issue"]
                    ),
                    "status": row["status"],
                    "total": row["total"],
                }
            )

        # --------------------------------------------------
        # 2. TRIBUNAL × ANO × POSIÇÃO
        # --------------------------------------------------

        print(
            "\n=== TRIBUNAL × ANO × POSIÇÃO "
            "(APENAS CASOS QUE DECIDEM) ==="
        )

        rows = connection.execute(
            """
            SELECT
                substr(c.decision_date, 1, 4) AS year,
                c.court,
                s.position_id,
                cm.inclusion_method,
                s.status,
                COUNT(*) AS total

            FROM corpus_membership cm

            JOIN cases c
              ON c.id = cm.case_id

            JOIN stances s
              ON s.case_id = c.id
             AND s.issue_slug = cm.issue_slug

            WHERE cm.issue_slug = ?
              AND s.decides_issue = 1

            GROUP BY
                substr(c.decision_date, 1, 4),
                c.court,
                s.position_id,
                cm.inclusion_method,
                s.status

            ORDER BY
                year,
                c.court,
                s.position_id
            """,
            (ISSUE,),
        ).fetchall()

        for row in rows:
            print(
                f"{row['year']} | "
                f"{row['court']} | "
                f"{short_position(row['position_id'])} | "
                f"{row['inclusion_method']} | "
                f"{row['status']} | "
                f"n={row['total']}"
            )

        # --------------------------------------------------
        # 3. TIMELINE DETALHADA
        # --------------------------------------------------

        print(
            "\n=== DECISÕES POR ORDEM CRONOLÓGICA ==="
        )

        rows = connection.execute(
            """
            SELECT
                c.process_number,
                c.decision_date,
                c.court,
                s.position_id,
                s.status,
                cm.inclusion_method

            FROM corpus_membership cm

            JOIN cases c
              ON c.id = cm.case_id

            JOIN stances s
              ON s.case_id = c.id
             AND s.issue_slug = cm.issue_slug

            WHERE cm.issue_slug = ?
              AND s.decides_issue = 1

            ORDER BY
                c.decision_date,
                c.court,
                c.process_number
            """,
            (ISSUE,),
        ).fetchall()

        for row in rows:
            print(
                f"{row['decision_date']} | "
                f"{row['court']} | "
                f"{short_position(row['position_id']):10} | "
                f"{row['inclusion_method']:7} | "
                f"{row['status']:6} | "
                f"{row['process_number']}"
            )

        # --------------------------------------------------
        # 4. COMPARAÇÃO:
        #    CORPUS TOTAL VS PESQUISA ORIGINAL
        # --------------------------------------------------

        print(
            "\n=== DISTRIBUIÇÃO TEMPORAL — CORPUS TOTAL ==="
        )

        total_by_year = defaultdict(
            lambda: {
                "5 anos": 0,
                "20 anos": 0,
            }
        )

        rows = connection.execute(
            """
            SELECT
                substr(c.decision_date, 1, 4) AS year,
                s.position_id,
                COUNT(*) AS total

            FROM corpus_membership cm

            JOIN cases c
              ON c.id = cm.case_id

            JOIN stances s
              ON s.case_id = c.id
             AND s.issue_slug = cm.issue_slug

            WHERE cm.issue_slug = ?
              AND s.decides_issue = 1
              AND s.position_id IS NOT NULL

            GROUP BY
                substr(c.decision_date, 1, 4),
                s.position_id

            ORDER BY year
            """,
            (ISSUE,),
        ).fetchall()

        for row in rows:
            total_by_year[
                row["year"]
            ][
                short_position(
                    row["position_id"]
                )
            ] += row["total"]

        for year, values in total_by_year.items():
            print(
                f"{year}: "
                f"5 anos={values['5 anos']}, "
                f"20 anos={values['20 anos']}"
            )

        print(
            "\n=== DISTRIBUIÇÃO TEMPORAL — "
            "APENAS PESQUISA PRINCIPAL ==="
        )

        search_by_year = defaultdict(
            lambda: {
                "5 anos": 0,
                "20 anos": 0,
            }
        )

        rows = connection.execute(
            """
            SELECT
                substr(c.decision_date, 1, 4) AS year,
                s.position_id,
                COUNT(*) AS total

            FROM corpus_membership cm

            JOIN cases c
              ON c.id = cm.case_id

            JOIN stances s
              ON s.case_id = c.id
             AND s.issue_slug = cm.issue_slug

            WHERE cm.issue_slug = ?
              AND cm.inclusion_method = 'search'
              AND s.decides_issue = 1
              AND s.position_id IS NOT NULL

            GROUP BY
                substr(c.decision_date, 1, 4),
                s.position_id

            ORDER BY year
            """,
            (ISSUE,),
        ).fetchall()

        for row in rows:
            search_by_year[
                row["year"]
            ][
                short_position(
                    row["position_id"]
                )
            ] += row["total"]

        if not search_by_year:
            print("Nenhum resultado.")

        for year, values in search_by_year.items():
            print(
                f"{year}: "
                f"5 anos={values['5 anos']}, "
                f"20 anos={values['20 anos']}"
            )

        # --------------------------------------------------
        # 5. CASOS EM REVIEW
        # --------------------------------------------------

        print("\n=== REVIEW ===")

        rows = connection.execute(
            """
            SELECT
                c.process_number,
                c.decision_date,
                c.court,
                s.position_id,
                cm.inclusion_method

            FROM corpus_membership cm

            JOIN cases c
              ON c.id = cm.case_id

            JOIN stances s
              ON s.case_id = c.id
             AND s.issue_slug = cm.issue_slug

            WHERE cm.issue_slug = ?
              AND s.status = 'REVIEW'

            ORDER BY c.decision_date
            """,
            (ISSUE,),
        ).fetchall()

        if not rows:
            print("Nenhum caso em REVIEW.")

        for row in rows:
            print(
                f"{row['decision_date']} | "
                f"{row['court']} | "
                f"{short_position(row['position_id'])} | "
                f"{row['inclusion_method']} | "
                f"{row['process_number']}"
            )


if __name__ == "__main__":
    main()