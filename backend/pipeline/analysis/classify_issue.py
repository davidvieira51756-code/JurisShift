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


# O override evita que uma OPENAI_API_KEY antiga
# definida no Windows se sobreponha ao .env.
load_dotenv(override=True)


MODEL = os.getenv(
    "LLM_MODEL",
    "gpt-5.6-luna",
)

PROMPT_VERSION = "stance-v7-generic"


ISSUE_RULES = {
    "loan-prescription-acceleration": {
        "keywords": [
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
            "AUJ",
            "6/2022",
        ],
        "guidance": """
REGRAS ESPECÍFICAS DA QUESTÃO:
- Uma mera referência a prescrição, vencimento antecipado
  ou artigo 781.º não significa que o tribunal tenha decidido
  esta questão.
- Para a posição loan-prescription-five-year, a evidência deve
  mostrar que o prazo de cinco anos continua aplicável apesar
  do vencimento antecipado, ou conclusão juridicamente
  equivalente.
- Para a posição loan-prescription-twenty-year, a evidência
  deve mostrar que passa a aplicar-se o prazo ordinário,
  designadamente vinte anos.
""".strip(),
    },

    "family-home-own-land": {
        "keywords": [
            "1726.º",
            "1726º",
            "artigo 1726",
            "art. 1726",
            "comunhão de adquiridos",
            "terreno próprio",
            "prédio próprio",
            "bem próprio",
            "bens próprios",
            "bem comum",
            "bens comuns",
            "património comum",
            "construção",
            "casa",
            "moradia",
            "edificação",
            "benfeitoria",
            "benfeitorias",
            "compensação",
            "crédito",
            "coisa nova",
            "AUJ",
            "9/2025",
        ],
        "guidance": """
REGRAS ESPECÍFICAS DA QUESTÃO:
- A questão é a qualificação jurídica do imóvel construído
  com meios comuns em terreno que é bem próprio de um
  dos cônjuges.
- Não basta que o acórdão mencione partilha, benfeitorias,
  comunhão de adquiridos ou o artigo 1726.º.
- Para family-home-article-1726, o tribunal deve efetivamente
  aplicar o regime do artigo 1726.º à relação entre o terreno
  próprio e a construção realizada com meios comuns, ou chegar
  a conclusão juridicamente equivalente.
- Para family-home-own-property, o tribunal deve afastar essa
  solução e considerar que o imóvel permanece bem próprio do
  titular do terreno, reconhecendo ou admitindo a correspondente
  compensação/crédito do património comum, ou conclusão
  juridicamente equivalente.
- Um acórdão pode descrever a orientação oposta apenas para a
  citar ou rejeitar. Nesse caso, classifica segundo a posição
  que o próprio tribunal efetivamente adota.
""".strip(),
    },
}


DEFAULT_KEYWORDS = [
    "acórdão",
    "tribunal",
    "uniformização",
]


PARTY_ARGUMENT_MARKERS = (
    "a recorrente",
    "o recorrente",
    "a recorrida",
    "o recorrido",
    "a apelante",
    "o apelante",
    "a exequente",
    "o exequente",
    "a executada",
    "o executado",
    "alega que",
    "alegou que",
    "sustenta que",
    "defende que",
    "conclui que",
    "nas suas conclusões",
    "conclusões do recurso",
)


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

    if not positions:
        raise RuntimeError(
            f"A questão {issue_slug} não tem posições configuradas."
        )

    return (
        dict(issue),
        [
            dict(position)
            for position in positions
        ],
    )


def get_cases(
    issue_slug: str,
    limit: int | None,
) -> list[dict]:
    sql = """
        SELECT
            c.id,
            c.ecli,
            c.process_number,
            c.decision_date,
            c.summary,
            c.full_text,
            c.source_url

        FROM cases c

        JOIN corpus_membership cm
            ON cm.case_id = c.id

        WHERE cm.issue_slug = ?

        ORDER BY
            c.decision_date ASC,
            c.process_number ASC
    """

    params: list = [
        issue_slug
    ]

    if limit is not None:
        sql += " LIMIT ?"
        params.append(
            limit
        )

    with get_connection() as connection:
        rows = connection.execute(
            sql,
            tuple(params),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def get_issue_rules(
    issue_slug: str,
) -> dict:
    return ISSUE_RULES.get(
        issue_slug,
        {
            "keywords": DEFAULT_KEYWORDS,
            "guidance": (
                "Não existem regras específicas adicionais. "
                "Classifica exclusivamente com base na pergunta "
                "e nas posições permitidas."
            ),
        },
    )


def merge_windows(
    windows: list[
        tuple[int, int]
    ],
) -> list[
    tuple[int, int]
]:
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
    issue_slug: str,
    max_chars: int = 7500,
) -> str:
    if not text:
        return ""

    rules = get_issue_rules(
        issue_slug
    )

    keywords = rules[
        "keywords"
    ]

    lowered = (
        text.casefold()
    )

    windows: list[
        tuple[int, int]
    ] = []

    for keyword in keywords:
        keyword_normalized = (
            keyword.casefold()
        )

        for match in re.finditer(
            re.escape(
                keyword_normalized
            ),
            lowered,
        ):
            windows.append(
                (
                    max(
                        0,
                        match.start() - 800,
                    ),
                    min(
                        len(text),
                        match.end() + 1400,
                    ),
                )
            )

    windows = merge_windows(
        windows
    )

    pieces: list[str] = []
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

    summary = summary[
        :7000
    ]

    excerpts = build_excerpts(
        case["full_text"]
        or "",
        issue["slug"],
    )

    rules = get_issue_rules(
        issue["slug"]
    )

    guidance = rules[
        "guidance"
    ]

    return f"""
Classifica este acórdão português relativamente
a UMA questão jurídica específica.

QUESTÃO:
{issue["question"]}

POSIÇÕES PERMITIDAS:
{positions_text}

REGRAS GERAIS:
- Usa apenas o texto fornecido.
- decides_issue=true apenas se o tribunal realmente decidir
  a questão jurídica acima.
- A mera presença de palavras relacionadas com o tema
  não significa que o acórdão decida a questão.
- Se decides_issue=false, position_id deve ser null.
- Se decides_issue=true, position_id deve ser exatamente
  um dos IDs fornecidos.
- evidence_quote deve ser uma citação literal retirada
  do SUMÁRIO ou dos EXCERTOS fornecidos.
- Nunca reformules a evidence_quote.
- Prefere o SUMÁRIO quando este declarar claramente
  a posição efetivamente adotada pelo tribunal.
- A evidence_quote tem de, por si só e no respetivo
  contexto, sustentar a posição escolhida.
- Não uses como prova alegações, conclusões,
  argumentos ou pedidos das partes.
- Não confundas uma posição citada, descrita ou rejeitada
  com a posição efetivamente adotada pelo tribunal.
- Se o acórdão descrever duas correntes jurisprudenciais,
  identifica qual delas o tribunal acolhe no caso.
- Se não for possível determinar a posição com segurança,
  baixa a confiança e não inventes evidência.
- confidence é um número entre 0 e 1.
- reason deve ter no máximo 2 frases.

{guidance}

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


def looks_like_party_argument(
    quote: str,
) -> bool:
    normalized = (
        quote.casefold()
    )

    return any(
        marker in normalized
        for marker
        in PARTY_ARGUMENT_MARKERS
    )


def contains_any(
    text: str,
    terms: tuple[str, ...],
) -> bool:
    return any(
        term in text
        for term in terms
    )


def evidence_supports_loan_position(
    normalized: str,
    position_id: str,
) -> bool:
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
        "artigo 310",
        "art. 310",
    )

    letter_e_terms = (
        "alínea e)",
        "alínea e",
        "al. e)",
        "al. e",
    )

    has_five_year = contains_any(
        normalized,
        five_year_terms,
    )

    has_twenty_year = contains_any(
        normalized,
        twenty_year_terms,
    )

    has_article_310 = contains_any(
        normalized,
        article_310_terms,
    )

    has_letter_e = contains_any(
        normalized,
        letter_e_terms,
    )

    if (
        position_id
        == "loan-prescription-five-year"
    ):
        if (
            has_twenty_year
            and not has_five_year
        ):
            return False

        return (
            has_five_year
            or (
                has_article_310
                and has_letter_e
            )
        )

    if (
        position_id
        == "loan-prescription-twenty-year"
    ):
        return has_twenty_year

    return False


def evidence_supports_family_home_position(
    normalized: str,
    position_id: str,
) -> bool:
    article_1726_terms = (
        "1726.º",
        "1726º",
        "artigo 1726",
        "art. 1726",
    )

    property_context_terms = (
        "terreno",
        "prédio",
        "imóvel",
        "casa",
        "moradia",
        "construção",
        "edificação",
    )

    own_context_terms = (
        "terreno próprio",
        "bem próprio",
        "bens próprios",
        "imóvel pertencente a um só",
        "propriedade exclusiva de apenas um",
        "propriedade de um deles",
        "próprio do cônjuge",
        "próprio da ré",
        "próprio do réu",
    )

    common_result_terms = (
        "é bem comum",
        "bem comum de ambos",
        "constitui bem comum",
        "deve ser considerado bem comum",
        "deve ser tratada como bem comum",
        "integra o património comum",
    )

    compensation_terms = (
        "compensação",
        "crédito",
        "recompensa",
        "direito de crédito",
    )

    improvement_terms = (
        "benfeitoria",
        "benfeitorias",
    )

    apply_terms = (
        "aplica-se",
        "é aplicável",
        "aplicável",
        "aplicação do artigo 1726",
        "regime do artigo 1726",
        "nos termos do artigo 1726",
    )

    reject_terms = (
        "não se aplica",
        "não é aplicável",
        "não tem aplicação",
        "inaplicável",
        "afastada a aplicação",
        "afastar a aplicação",
    )

    value_terms = (
        "mais valiosa",
        "parte mais valiosa",
        "maior valor",
        "valor superior",
        "maior contribuição",
        "contribuição de maior valor",
        "mais valiosa das duas prestações",
    )

    new_thing_terms = (
        "coisa nova",
        "nova coisa",
    )

    has_article = contains_any(
        normalized,
        article_1726_terms,
    )

    has_property_context = contains_any(
        normalized,
        property_context_terms,
    )

    has_own_context = contains_any(
        normalized,
        own_context_terms,
    )

    has_common_result = contains_any(
        normalized,
        common_result_terms,
    )

    has_compensation = contains_any(
        normalized,
        compensation_terms,
    )

    has_improvement = contains_any(
        normalized,
        improvement_terms,
    )

    has_apply = contains_any(
        normalized,
        apply_terms,
    )

    has_reject = contains_any(
        normalized,
        reject_terms,
    )

    has_value_rule = contains_any(
        normalized,
        value_terms,
    )

    has_new_thing = contains_any(
        normalized,
        new_thing_terms,
    )

    if (
        position_id
        == "family-home-article-1726"
    ):
        if has_reject:
            return False

        return (
            (
                has_article
                and has_apply
            )
            or (
                has_property_context
                and has_value_rule
                and has_common_result
            )
        )

    if (
        position_id
        == "family-home-own-property"
    ):
        return (
            (
                has_own_context
                and has_improvement
            )
            or (
                has_own_context
                and has_compensation
            )
            or (
                has_property_context
                and has_new_thing
                and has_compensation
            )
            or (
                has_article
                and has_reject
            )
        )

    return False


def evidence_supports_position(
    quote: str,
    issue_slug: str,
    position_id: str,
) -> bool:
    if looks_like_party_argument(
        quote
    ):
        return False

    normalized = (
        quote.casefold()
    )

    if (
        issue_slug
        == "loan-prescription-acceleration"
    ):
        return (
            evidence_supports_loan_position(
                normalized,
                position_id,
            )
        )

    if (
        issue_slug
        == "family-home-own-land"
    ):
        return (
            evidence_supports_family_home_position(
                normalized,
                position_id,
            )
        )

    # Para futuras issues desconhecidas,
    # não promovemos evidência automaticamente.
    # Fica REVIEW até existir uma regra determinística.
    return False


def find_quote_with_normalized_whitespace(
    source: str,
    quote: str,
) -> tuple[
    int | None,
    int | None,
]:
    if (
        not source
        or not quote
    ):
        return (
            None,
            None,
        )

    punctuation_map = {
        "“": '"',
        "”": '"',
        "„": '"',
        "«": '"',
        "»": '"',
        "‘": "'",
        "’": "'",
        "–": "-",
        "—": "-",
        "-": "-",
    }

    def normalize_with_map(
        text: str,
    ) -> tuple[
        str,
        list[int],
    ]:
        chars: list[str] = []
        indexes: list[int] = []

        in_whitespace = False

        for index, char in enumerate(
            text
        ):
            if char.isspace():
                if not in_whitespace:
                    chars.append(" ")
                    indexes.append(index)

                in_whitespace = True
                continue

            in_whitespace = False

            normalized_char = (
                punctuation_map.get(
                    char,
                    char,
                )
            )

            chars.append(
                normalized_char
            )

            indexes.append(
                index
            )

        return (
            "".join(chars),
            indexes,
        )

    normalized_source, original_indexes = (
        normalize_with_map(
            source
        )
    )

    normalized_quote, _ = (
        normalize_with_map(
            quote
        )
    )

    normalized_quote = (
        normalized_quote.strip()
    )

    position = (
        normalized_source.find(
            normalized_quote
        )
    )

    if position < 0:
        return (
            None,
            None,
        )

    normalized_end = (
        position
        + len(normalized_quote)
        - 1
    )

    if (
        position >= len(
            original_indexes
        )
        or normalized_end >= len(
            original_indexes
        )
    ):
        return (
            None,
            None,
        )

    start_offset = (
        original_indexes[
            position
        ]
    )

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
    issue_slug: str,
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

    if not evidence_supports_position(
        quote,
        issue_slug,
        position_id,
    ):
        return (
            False,
            None,
            None,
            None,
        )

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
) -> tuple[
    str,
    bool,
]:
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
            issue["slug"],
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

        stance_id = (
            stance["id"]
        )

        connection.execute(
            """
            DELETE FROM evidence
            WHERE stance_id = ?
            """,
            (stance_id,),
        )
        
        stored_quote = quote

    if (
        quote_verified
        and start_offset is not None
        and end_offset is not None
    ):
        source_text = (
            case["summary"]
            if evidence_role == "summary"
            else case["full_text"]
        )

        source_text = (
            source_text
            or ""
        )

        stored_quote = (
            source_text[
                start_offset:end_offset
            ].strip()
        )

        if (
        quote_verified
        and evidence_role
        and stored_quote
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
                    stored_quote,
                ),
            )
        connection.commit()

    return (
        status,
        quote_verified,
    )


def main():
    parser = (
        argparse.ArgumentParser()
    )

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
        args.issue_slug,
        args.limit,
    )

    provider = (
        get_llm_provider()
    )

    print()
    print("=" * 70)
    print(
        "JURISSHIFT — CLASSIFICATION"
    )
    print("=" * 70)

    print(
        f"Questão: "
        f"{issue['title']}"
    )

    print(
        f"Modelo:  "
        f"{provider.model}"
    )

    print(
        f"Casos:   "
        f"{len(cases)}"
    )

    print()

    if not cases:
        print(
            "Nenhum caso pertence ao corpus desta issue."
        )
        print(
            "Faz primeiro a ingestão e o registo em "
            "corpus_membership."
        )
        return

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