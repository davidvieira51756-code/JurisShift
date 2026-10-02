import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone

from dotenv import load_dotenv

from backend.db.database import (
    get_connection,
    init_db,
)
from backend.llm.factory import (
    get_llm_provider,
)


load_dotenv()

MODEL = os.getenv(
    "LLM_MODEL",
    "qwen3.5:2b",
)

PROMPT_VERSION = "stance-v5"

KEYWORDS = [
    "310.º",
    "310º",
    "artigo 310",
    "art. 310",
    "781.º",
    "781º",
    "artigo 781",
    "art. 781",
    "prescrição",
    "vencimento antecipado",
    "cinco anos",
    "5 anos",
    "vinte anos",
    "20 anos",
    "prazo ordinário",
    "acórdão uniformizador",
    "uniformização",
    "auj",
    "6/2022",
]


def get_issue(
    issue_slug: str,
) -> tuple[dict, list[dict]]:
    with get_connection() as connection:
        issue = connection.execute(
            """
            SELECT *
            FROM issues
            WHERE slug = ?
            """,
            (issue_slug,),
        ).fetchone()

        positions = connection.execute(
            """
            SELECT *
            FROM positions
            WHERE issue_slug = ?
            ORDER BY id
            """,
            (issue_slug,),
        ).fetchall()

    if issue is None:
        raise RuntimeError(
            f"Questão não encontrada: {issue_slug}"
        )

    return (
        dict(issue),
        [
            dict(position)
            for position in positions
        ],
    )


def get_cases(
    limit: int | None,
) -> list[dict]:
    sql = """
        SELECT
            id,
            ecli,
            process_number,
            decision_date,
            summary,
            full_text,
            source_url
        FROM cases
        ORDER BY decision_date ASC
    """

    params = ()

    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)

    with get_connection() as connection:
        rows = connection.execute(
            sql,
            params,
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def merge_windows(
    windows: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    if not windows:
        return []

    windows.sort()

    merged = [
        [
            windows[0][0],
            windows[0][1],
        ]
    ]

    for start, end in windows[1:]:
        previous = merged[-1]

        if start <= previous[1]:
            previous[1] = max(
                previous[1],
                end,
            )
        else:
            merged.append(
                [start, end]
            )

    return [
        (start, end)
        for start, end in merged
    ]


def build_excerpts(
    text: str,
    max_chars: int = 6500,
) -> str:
    if not text:
        return ""

    lowered = text.casefold()
    windows = []

    for keyword in KEYWORDS:
        for match in re.finditer(
            re.escape(
                keyword.casefold()
            ),
            lowered,
        ):
            windows.append(
                (
                    max(
                        0,
                        match.start() - 700,
                    ),
                    min(
                        len(text),
                        match.end() + 1200,
                    ),
                )
            )

    windows = merge_windows(
        windows
    )

    pieces = []
    total = 0

    for start, end in windows:
        piece = text[
            start:end
        ].strip()

        if not piece:
            continue

        remaining = (
            max_chars - total
        )

        if remaining <= 0:
            break

        piece = piece[
            :remaining
        ]

        pieces.append(
            piece
        )

        total += len(
            piece
        )

    if not pieces:
        return text[
            :max_chars
        ]

    return (
        "\n\n--- EXCERTO ---\n\n"
    ).join(
        pieces
    )


def build_prompt(
    case: dict,
    issue: dict,
    positions: list[dict],
) -> str:
    positions_text = "\n".join(
        (
            f"{position['id']}: "
            f"{position['label']}. "
            f"{position['description']}"
        )
        for position in positions
    )

    summary = (
        case["summary"]
        or "Não disponível."
    )

    # Evita gastar contexto desnecessariamente.
    summary = summary[:2500]

    excerpts = build_excerpts(
        case["full_text"]
        or ""
    )

    return f"""
Classifica este acórdão português.

QUESTÃO:
{issue["question"]}

POSIÇÕES PERMITIDAS:
{positions_text}

REGRAS:
- Usa apenas o texto fornecido.
- decides_issue=true apenas se o tribunal
  realmente decidir ESTA questão.
- Uma mera referência a prescrição,
  vencimento antecipado ou artigo 781.º
  não basta.
- Se decides_issue=false,
  position_id deve ser null.
- Se decides_issue=true,
  position_id deve ser exatamente um dos IDs
  fornecidos.
- evidence_quote deve ser uma citação literal retirada
  do SUMÁRIO ou dos EXCERTOS fornecidos.
- Prefere o SUMÁRIO quando este declarar claramente
  a posição jurídica adotada pelo tribunal.
- A evidence_quote tem de, por si só, sustentar
  a position_id escolhida.
- Para a posição dos cinco anos, a citação deve
  demonstrar que o prazo quinquenal continua
  aplicável apesar do vencimento antecipado,
  ou uma conclusão juridicamente equivalente.
- Para a posição do prazo ordinário, a citação
  deve demonstrar que após o vencimento antecipado
  passa a aplicar-se o prazo ordinário,
  nomeadamente vinte anos.
- Não uses como evidence_quote uma frase que apenas
  diga que ocorreu vencimento antecipado.
- Não reformules a evidence_quote.
- Se o texto fornecido não contiver uma citação
  capaz de demonstrar a posição, baixa a confiança
  e não inventes evidência.
- confidence é um número entre 0 e 1.
- reason deve ter no máximo 2 frases.
- A classificação deve refletir exclusivamente a posição
  adotada pelo tribunal no acórdão.
- Não uses alegações, conclusões, argumentos ou pedidos
  das partes como prova da posição do tribunal.
- Não uses como evidence_quote texto que apenas descreva
  aquilo que o recorrente, recorrido, exequente, executado
  ou outra parte defendeu.
- Prefere passagens da fundamentação jurídica do tribunal,
  do sumário ou da conclusão decisória.
- Se houver posições opostas das partes no texto,
  identifica qual delas foi efetivamente acolhida pelo tribunal.

Devolve apenas JSON com esta estrutura:

{{
  "decides_issue": true,
  "position_id": "id-ou-null",
  "confidence": 0.95,
  "evidence_quote": "texto literal ou null",
  "reason": "justificação curta"
}}

PROCESSO:
{case["process_number"]}

DATA:
{case["decision_date"]}

SUMÁRIO:
{summary}

EXCERTOS:
{excerpts}
""".strip()


def make_input_hash(
    prompt: str,
) -> str:
    raw = (
        f"{MODEL}\n"
        f"{PROMPT_VERSION}\n"
        f"{prompt}"
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def get_cached(
    input_hash: str,
) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT output_json
            FROM llm_calls
            WHERE input_hash = ?
            """,
            (input_hash,),
        ).fetchone()

    if row is None:
        return None

    return json.loads(
        row["output_json"]
    )


def store_llm_call(
    input_hash: str,
    result: dict,
    usage: dict,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO llm_calls (
                stage,
                model,
                prompt_version,
                input_hash,
                output_json,
                input_tokens,
                output_tokens,
                cost,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "stance_classification",
                MODEL,
                PROMPT_VERSION,
                input_hash,
                json.dumps(
                    result,
                    ensure_ascii=False,
                ),
                usage.get(
                    "input_tokens"
                ),
                usage.get(
                    "output_tokens"
                ),
                None,
                datetime.now(
                    timezone.utc
                ).isoformat(),
            ),
        )

        connection.commit()


PARTY_ARGUMENT_MARKERS = (
    "alega que",
    "alegou que",
    "sustenta que",
    "sustentou que",
    "defende que",
    "defendeu que",
    "conclui que",
    "concluiu que",
    "nas suas conclusões",
    "conclusões do recurso",
    "pugna por",
    "pugnou por",
    "pretende que",
    "invoca que",
    "invocou que",
    "segundo a recorrente",
    "segundo o recorrente",
)


def looks_like_party_argument(
    quote: str,
) -> bool:
    normalized = quote.casefold()

    return any(
        marker in normalized
        for marker in PARTY_ARGUMENT_MARKERS
    )


def evidence_supports_position(
    quote: str,
    position_id: str,
) -> bool:
    if looks_like_party_argument(
        quote
    ):
        return False

    normalized = quote.casefold()

    five_year_terms = (
        "cinco anos",
        "5 anos",
        "prazo quinquenal",
        "prescrição quinquenal",
    )

    twenty_year_terms = (
        "vinte anos",
        "20 anos",
        "prazo ordinário",
        "prescrição ordinária",
    )

    article_310_terms = (
        "310.º",
        "310º",
        "310.°",
        "artigo 310",
        "art. 310",
    )

    letter_e_terms = (
        "alínea e)",
        "alínea e",
        "al. e)",
        "al. e",
    )

    prescription_terms = (
        "prescrição",
        "prescricional",
    )

    acceleration_terms = (
        "vencimento antecipado",
        "vencimento imediato",
        "vencer na sua totalidade",
        "vencer na totalidade",
        "perda do benefício do prazo",
        "perda de benefício do prazo",
    )

    has_five_year = any(
        term in normalized
        for term in five_year_terms
    )

    has_twenty_year = any(
        term in normalized
        for term in twenty_year_terms
    )

    has_article_310 = any(
        term in normalized
        for term in article_310_terms
    )

    has_letter_e = any(
        term in normalized
        for term in letter_e_terms
    )

    has_prescription = any(
        term in normalized
        for term in prescription_terms
    )

    has_acceleration = any(
        term in normalized
        for term in acceleration_terms
    )

    if (
        position_id
        == "loan-prescription-five-year"
    ):
        # Uma afirmação explícita de que se aplicam
        # 20 anos contradiz esta posição.
        if (
            has_twenty_year
            and not has_five_year
        ):
            return False

        # Evidência explícita do prazo quinquenal.
        if has_five_year:
            return True

        # Referência ao artigo 310.º, alínea e).
        if (
            has_article_310
            and has_letter_e
        ):
            return True

        # Formulação juridicamente equivalente:
        # o vencimento antecipado/total não altera
        # o enquadramento prescricional.
        if (
            has_prescription
            and has_acceleration
        ):
            return True

        return False

    if (
        position_id
        == "loan-prescription-twenty-year"
    ):
        return has_twenty_year

    return False

def find_quote_with_normalized_whitespace(
    source: str,
    quote: str,
) -> tuple[int | None, int | None]:
    if not source or not quote:
        return None, None

    # Cria uma versão normalizada do texto, mas mantém
    # um mapa para as posições no texto original.
    normalized_chars = []
    original_indexes = []

    in_whitespace = False

    for index, char in enumerate(source):
        if char.isspace():
            if not in_whitespace:
                normalized_chars.append(" ")
                original_indexes.append(index)

            in_whitespace = True
        else:
            normalized_chars.append(char)
            original_indexes.append(index)
            in_whitespace = False

    normalized_source = "".join(
        normalized_chars
    ).strip()

    normalized_quote = re.sub(
        r"\s+",
        " ",
        quote,
    ).strip()

    position = normalized_source.find(
        normalized_quote
    )

    if position < 0:
        return None, None

    # O .strip() acima pode deslocar o mapa se
    # o source começar com whitespace, por isso
    # calculamos novamente sem strip no source.
    normalized_chars = []
    original_indexes = []

    in_whitespace = False

    for index, char in enumerate(source):
        if char.isspace():
            if not in_whitespace:
                normalized_chars.append(" ")
                original_indexes.append(index)

            in_whitespace = True
        else:
            normalized_chars.append(char)
            original_indexes.append(index)
            in_whitespace = False

    normalized_source = "".join(
        normalized_chars
    )

    position = normalized_source.find(
        normalized_quote
    )

    if position < 0:
        return None, None

    normalized_end = (
        position
        + len(normalized_quote)
        - 1
    )

    if (
        position >= len(original_indexes)
        or normalized_end >= len(original_indexes)
    ):
        return None, None

    start_offset = original_indexes[
        position
    ]

    end_offset = (
        original_indexes[
            normalized_end
        ]
        + 1
    )

    return (
        start_offset,
        end_offset,
    )


def find_evidence(
    case: dict,
    quote: str,
    position_id: str,
) -> tuple[
    bool,
    str | None,
    int | None,
    int | None,
]:
    summary = (
        case["summary"]
        or ""
    )

    full_text = (
        case["full_text"]
        or ""
    )

    # A citação tem primeiro de suportar
    # deterministicamente a posição atribuída.
    if not evidence_supports_position(
        quote,
        position_id,
    ):
        return (
            False,
            None,
            None,
            None,
        )

    # 1. Preferimos o sumário.
    start_offset, end_offset = (
        find_quote_with_normalized_whitespace(
            summary,
            quote,
        )
    )

    if start_offset is not None:
        return (
            True,
            "summary",
            start_offset,
            end_offset,
        )

    # 2. Se não estiver no sumário,
    # procuramos no texto integral.
    start_offset, end_offset = (
        find_quote_with_normalized_whitespace(
            full_text,
            quote,
        )
    )

    if start_offset is not None:
        return (
            True,
            "holding",
            start_offset,
            end_offset,
        )

    return (
        False,
        None,
        None,
        None,
    )


def save_classification(
    case: dict,
    issue: dict,
    positions: list[dict],
    result: dict,
) -> tuple[str, bool]:
    allowed_positions = {
        position["id"]
        for position in positions
    }

    decides_issue = bool(
        result.get(
            "decides_issue",
            False,
        )
    )

    position_id = result.get(
        "position_id"
    )

    try:
        confidence = float(
            result.get(
                "confidence",
                0,
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        confidence = 0.0

    confidence = max(
        0.0,
        min(
            1.0,
            confidence,
        ),
    )

    quote = result.get(
        "evidence_quote"
    )

    if not decides_issue:
        position_id = None
        quote = None

    if (
        decides_issue
        and position_id
        not in allowed_positions
    ):
        position_id = None

    quote_verified = False
    evidence_role = None
    start_offset = None
    end_offset = None

    if (
        decides_issue
        and position_id
        and isinstance(
            quote,
            str,
        )
        and quote.strip()
    ):
        (
            quote_verified,
            evidence_role,
            start_offset,
            end_offset,
        ) = find_evidence(
            case,
            quote,
            position_id,
        )

    if not decides_issue:
        status = (
            "AUTO"
            if confidence >= 0.80
            else "REVIEW"
        )

    elif (
        position_id
        and quote_verified
        and confidence >= 0.75
    ):
        status = "AUTO"

    else:
        status = "REVIEW"

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO stances (
                case_id,
                issue_slug,
                position_id,
                decides_issue,
                status,
                extraction_model,
                prompt_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(case_id, issue_slug)
            DO UPDATE SET
                position_id = excluded.position_id,
                decides_issue = excluded.decides_issue,
                status = excluded.status,
                extraction_model = excluded.extraction_model,
                prompt_version = excluded.prompt_version
            """,
            (
                case["id"],
                issue["slug"],
                position_id,
                int(
                    decides_issue
                ),
                status,
                MODEL,
                PROMPT_VERSION,
            ),
        )

        stance = connection.execute(
            """
            SELECT id
            FROM stances
            WHERE case_id = ?
              AND issue_slug = ?
            """,
            (
                case["id"],
                issue["slug"],
            ),
        ).fetchone()

        stance_id = stance[
            "id"
        ]

        connection.execute(
            """
            DELETE FROM evidence
            WHERE stance_id = ?
            """,
            (stance_id,),
        )

        if (
            quote_verified
            and evidence_role
            and quote
        ):
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
                    stance_id,
                    evidence_role,
                    start_offset,
                    end_offset,
                    quote,
                ),
            )

        connection.commit()

    return (
        status,
        quote_verified,
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "issue_slug",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    args = parser.parse_args()

    init_db()

    issue, positions = get_issue(
        args.issue_slug
    )

    cases = get_cases(
        args.limit
    )

    provider = get_llm_provider()

    print()
    print("=" * 70)
    print("JURISSHIFT — CLASSIFICATION")
    print("=" * 70)

    print(
        f"Questão: {issue['title']}"
    )

    print(
        f"Modelo:  {provider.model}"
    )

    print(
        f"Casos:   {len(cases)}"
    )

    print()

    success = 0
    failed = 0

    for index, case in enumerate(
        cases,
        start=1,
    ):
        print(
            f"[{index}/{len(cases)}] "
            f"{case['process_number']}"
        )

        try:
            prompt = build_prompt(
                case,
                issue,
                positions,
            )

            input_hash = (
                make_input_hash(
                    prompt
                )
            )

            result = get_cached(
                input_hash
            )

            if result is None:
                result, usage = (
                    provider.generate_json(
                        prompt
                    )
                )

                store_llm_call(
                    input_hash,
                    result,
                    usage,
                )

            else:
                print(
                    "        [cache]"
                )

            status, verified = (
                save_classification(
                    case,
                    issue,
                    positions,
                    result,
                )
            )

            print(
                f"        decide="
                f"{result.get('decides_issue')}"
            )

            print(
                f"        position="
                f"{result.get('position_id')}"
            )

            print(
                f"        confidence="
                f"{result.get('confidence')}"
            )

            print(
                f"        evidence="
                f"{'OK' if verified else '-'} "
                f"status={status}"
            )

            print(
                f"        reason="
                f"{result.get('reason')}"
            )

            success += 1

        except Exception as exc:
            failed += 1

            print(
                f"        [error] "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

    print()
    print("=" * 70)
    print(
        f"Processados: {success}"
    )
    print(
        f"Falharam:    {failed}"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()