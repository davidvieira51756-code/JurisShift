import hashlib
import json
import os
import ssl
import time
from datetime import datetime, timezone

import httpx
import truststore
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from backend.db.database import (
    get_connection,
    init_db,
)


load_dotenv()


REQUEST_DELAY = float(
    os.getenv(
        "DGSI_REQUEST_DELAY_SECONDS",
        "1.75",
    )
)

TIMEOUT = float(
    os.getenv(
        "DGSI_TIMEOUT_SECONDS",
        "30",
    )
)

USER_AGENT = os.getenv(
    "DGSI_USER_AGENT",
    "JurisShift/0.1 research prototype",
)


CASES = [
    {
        "process_number": "525/14.0TBMGR-A.C1",
        "court": "Tribunal da Relação de Coimbra",
        "decision_date": "2016-04-26",
        "rapporteur": "Maria João Areias",
        "procedural_type": "APELAÇÃO",
        "decision": "REVOGADA",
        "voting": None,
        "descriptors": [
            "LIVRANÇA",
            "RELAÇÕES IMEDIATAS",
            "PRESCRIÇÃO",
            "CONTRATO DE MÚTUO",
            "ABUSO DE DIREITO",
            "SUPRESSIO",
        ],
        "summary": (
            "No mútuo bancário, em que o reembolso da dívida foi objeto "
            "de um plano de amortização, as prestações mensais ficam "
            "sujeitas ao prazo prescricional de cinco anos. "
            "Se, em caso de incumprimento, o mutuante considerar vencidas "
            "todas as prestações, ficando sem efeito o plano de pagamento "
            "acordado, os valores em dívida voltam a assumir a sua natureza "
            "original de capital e de juros, ficando o capital sujeito ao "
            "prazo ordinário de 20 anos."
        ),
        "source_url": (
            "https://www.dgsi.pt/jtrc.nsf/"
            "8fe0e606d8f56b22802576c0005637dc/"
            "07401ba81f16e01a80257fbc0034cb1c"
            "?OpenDocument="
        ),
    },
    {
        "process_number": "589/15.0T8VNF-A.G1",
        "court": "Tribunal da Relação de Guimarães",
        "decision_date": "2017-03-16",
        "rapporteur": "Jorge Teixeira",
        "procedural_type": "APELAÇÃO",
        "decision": "PARCIALMENTE PROCEDENTE",
        "voting": "UNANIMIDADE",
        "descriptors": [
            "MÚTUO BANCÁRIO",
            "AMORTIZAÇÃO",
            "PRESTAÇÕES PERIÓDICAS",
            "JUROS REMUNERATÓRIOS",
        ],
        "summary": (
            "No mútuo bancário, as prestações periódicas compostas por "
            "capital e juros ficam sujeitas ao prazo prescricional de "
            "cinco anos. Porém, em caso de incumprimento, se o mutuante "
            "considerar vencidas todas as prestações, ficando sem efeito "
            "o plano de pagamento acordado, os valores em dívida voltam "
            "a assumir a sua natureza original de capital e de juros, "
            "ficando o capital sujeito ao prazo ordinário de 20 anos."
        ),
        "source_url": (
            "https://www.dgsi.pt/jtrg.nsf/-/"
            "D24AF600B81A38DC8025810E0053E80D"
        ),
    },
    {
        "process_number": "2483/15.5T8ENT-A.E1",
        "court": "Tribunal da Relação de Évora",
        "decision_date": "2018-04-12",
        "rapporteur": "Mário Coelho",
        "procedural_type": "APELAÇÃO",
        "decision": None,
        "voting": "UNANIMIDADE",
        "descriptors": [
            "PRESTAÇÕES PERIÓDICAS",
            "PRAZO DE PRESCRIÇÃO",
        ],
        "summary": (
            "O prazo de prescrição de cinco anos das quotas de amortização "
            "do capital, pagáveis com os juros, é aplicável a cada uma "
            "dessas prestações, e não à dívida global. "
            "O vencimento imediato das prestações restantes imposto pelo "
            "artigo 781.º do Código Civil, tornando o capital imediatamente "
            "exigível, implica que este fique sujeito ao prazo ordinário "
            "de prescrição de 20 anos."
        ),
        "source_url": (
            "https://www.dgsi.pt/jtre.nsf/-/"
            "4B230CE7761936AE802582780031766D"
        ),
    },
    {
        "process_number": "17012/17.8YIPRT.C1",
        "court": "Tribunal da Relação de Coimbra",
        "decision_date": "2018-06-12",
        "rapporteur": "Jorge Arcanjo",
        "procedural_type": "APELAÇÃO",
        "decision": "IMPROCEDENTE",
        "voting": "UNANIMIDADE",
        "descriptors": [
            "PRESCRIÇÃO",
            "PRESCRIÇÃO DE 5 ANOS",
        ],
        "summary": (
            "Resolvido extrajudicialmente com base no incumprimento "
            "definitivo um contrato de mútuo em que as partes haviam "
            "acordado num plano de pagamento em prestações mensais e "
            "sucessivas, o crédito reclamado já não se configura como "
            "quotas de amortização, mas antes como dívida global "
            "proveniente da relação de liquidação. "
            "Não tem aplicação o prazo de cinco anos do artigo 310.º, "
            "alínea e), sendo aplicável ao capital o prazo geral de "
            "prescrição de 20 anos."
        ),
        "source_url": (
            "https://www.dgsi.pt/jtrc.nsf/-/"
            "0F2B9CA4A7DAF79A802582D0005528B8"
        ),
    },
    {
        "process_number": "8636/16.1T8LRS-A.L1-7",
        "court": "Tribunal da Relação de Lisboa",
        "decision_date": "2021-01-19",
        "rapporteur": "Isabel Salgado",
        "procedural_type": "APELAÇÃO",
        "decision": "IMPROCEDENTE",
        "voting": "UNANIMIDADE",
        "descriptors": [
            "MÚTUO BANCÁRIO",
            "PRESTAÇÕES DEVIDAS",
            "PRAZO DE PRESCRIÇÃO",
            "REVOGAÇÃO DO CONTRATO",
            "VENCIMENTO ANTECIPADO",
        ],
        "summary": (
            "No contrato de mútuo bancário liquidável em prestações "
            "sucessivas, estas ficam sujeitas ao prazo de prescrição "
            "de cinco anos. Porém, em caso de incumprimento, tendo o "
            "mutuante considerado vencidas todas as prestações e devido "
            "o pagamento do valor total remanescente, fica sem efeito "
            "o plano de pagamento acordado e o montante em dívida retoma "
            "a sua natureza original de capital e juros, sujeito ao prazo "
            "de prescrição ordinário de 20 anos previsto no artigo 309.º "
            "do Código Civil."
        ),
        "source_url": (
            "https://www.dgsi.pt/jtrl.nsf/"
            "33182fc732316039802565fa00497eec/"
            "029fdf8e71990c5880258676003e95a9"
            "?OpenDocument="
        ),
    },
]


def clean_page_text(
    html: bytes,
) -> str:
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    for tag in soup(
        [
            "script",
            "style",
            "noscript",
        ]
    ):
        tag.decompose()

    text = soup.get_text(
        "\n",
        strip=True,
    )

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    return "\n".join(
        lines
    )


def fetch_text(
    url: str,
) -> str | None:
    context = truststore.SSLContext(
        ssl.PROTOCOL_TLS_CLIENT
    )

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,"
            "application/xhtml+xml"
        ),
    }

    try:
        with httpx.Client(
            verify=context,
            timeout=TIMEOUT,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = client.get(
                url
            )

            response.raise_for_status()

            return clean_page_text(
                response.content
            )

    except Exception as exc:
        print(
            "        [warning] "
            f"Não foi possível obter texto integral: "
            f"{type(exc).__name__}: {exc}"
        )

        return None


def save_case(
    case: dict,
    full_text: str,
) -> int:
    now = datetime.now(
        timezone.utc
    ).isoformat()

    text_hash = hashlib.sha256(
        full_text.encode(
            "utf-8"
        )
    ).hexdigest()

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
                None,
                case["process_number"],
                case["court"],
                None,
                "Direito Civil",
                case["decision_date"],
                case["rapporteur"],
                json.dumps(
                    case["descriptors"],
                    ensure_ascii=False,
                ),
                case["procedural_type"],
                case["decision"],
                case["voting"],
                case["summary"],
                full_text,
                text_hash,
                case["source_url"],
                now,
            ),
        )

        row = connection.execute(
            """
            SELECT id
            FROM cases
            WHERE source_url = ?
            """,
            (
                case["source_url"],
            ),
        ).fetchone()

        connection.commit()

        return row["id"]


def main():
    init_db()

    print()
    print("=" * 70)
    print(
        "JURISSHIFT — SEED DIVERGENT CASES"
    )
    print("=" * 70)
    print(
        f"Casos: {len(CASES)}"
    )
    print()

    saved = 0

    for index, case in enumerate(
        CASES,
        start=1,
    ):
        print(
            f"[{index}/{len(CASES)}] "
            f"{case['process_number']}"
        )

        page_text = fetch_text(
            case["source_url"]
        )

        if page_text:
            full_text = page_text

            print(
                "        source=DGSI "
                f"chars={len(full_text)}"
            )

        else:
            # O acesso direto ao DGSI pode falhar
            # localmente. O sumário verificado é
            # suficiente para este subset dirigido.
            full_text = case[
                "summary"
            ]

            print(
                "        source=verified-summary "
                f"chars={len(full_text)}"
            )

        case_id = save_case(
            case,
            full_text,
        )

        print(
            f"        saved id={case_id}"
        )

        saved += 1

        if index < len(CASES):
            time.sleep(
                REQUEST_DELAY
            )

    with get_connection() as connection:
        total = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM cases
            """
        ).fetchone()["total"]

    print()
    print("=" * 70)
    print(
        f"Guardados: {saved}"
    )
    print(
        f"Total na BD: {total}"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()