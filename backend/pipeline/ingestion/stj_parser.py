import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup


@dataclass
class StjCase:
    ecli: Optional[str]
    process_number: Optional[str]

    section: Optional[str]
    area: Optional[str]
    rapporteur: Optional[str]

    descriptors: list[str]

    decision_date: Optional[str]

    procedural_type: Optional[str]
    decision: Optional[str]
    voting: Optional[str]

    summary: Optional[str]
    full_text: Optional[str]

    source_url: str


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        value,
    )

    return "".join(
        char
        for char in normalized
        if not unicodedata.combining(char)
    )


def _normalize_key(value: str) -> str:
    value = _strip_accents(value)
    value = value.casefold()

    return re.sub(
        r"[^a-z0-9]",
        "",
        value,
    )


def _find_value(
    doc: dict[str, Any],
    *aliases: str,
) -> Any:

    wanted = {
        _normalize_key(alias)
        for alias in aliases
    }

    for key, value in doc.items():
        if _normalize_key(str(key)) in wanted:
            return value

    return None


def _preferred_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value

    for key in (
        "Show",
        "Original",
        "Index",
    ):
        candidate = value.get(key)

        if candidate not in (
            None,
            "",
            [],
            {},
        ):
            return candidate

    return None


def _simple_text(
    value: Any,
) -> Optional[str]:

    value = _preferred_value(value)

    if value is None:
        return None

    if isinstance(value, list):
        value = " / ".join(
            str(item)
            for item in value
            if item is not None
        )

    value = re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()

    return value or None


def _html_to_text(
    value: Any,
) -> Optional[str]:

    value = _preferred_value(value)

    if value is None:
        return None

    if isinstance(value, list):
        value = "\n".join(
            str(item)
            for item in value
            if item is not None
        )

    if not isinstance(value, str):
        value = str(value)

    if not value.strip():
        return None

    soup = BeautifulSoup(
        value,
        "lxml",
    )

    text = soup.get_text(
        separator="\n",
        strip=True,
    )

    lines = []

    for line in text.splitlines():
        line = re.sub(
            r"\s+",
            " ",
            line,
        ).strip()

        if line:
            lines.append(line)

    return "\n".join(lines) or None


def _descriptors(
    value: Any,
) -> list[str]:

    value = _preferred_value(value)

    if value is None:
        return []

    if isinstance(value, list):
        return [
            re.sub(
                r"\s+",
                " ",
                str(item),
            ).strip()
            for item in value
            if str(item).strip()
        ]

    return [
        item.strip()
        for item in str(value).split("/")
        if item.strip()
    ]


def _parse_date(
    value: Any,
) -> Optional[str]:

    value = _simple_text(value)

    if not value:
        return None

    for date_format in (
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ):
        try:
            parsed = datetime.strptime(
                value,
                date_format,
            )

            return parsed.date().isoformat()

        except ValueError:
            pass

    return value


def _extract_doc(
    html: bytes | str,
) -> dict[str, Any]:

    soup = BeautifulSoup(
        html,
        "lxml",
    )

    script = soup.find(
        "script",
        id="__NEXT_DATA__",
    )

    if script is None:
        raise ValueError(
            "Página sem __NEXT_DATA__. "
            "Não parece ser um acórdão válido do juris.stj.pt."
        )

    raw = script.string or script.get_text()

    if not raw:
        raise ValueError(
            "__NEXT_DATA__ está vazio."
        )

    data = json.loads(raw)

    try:
        doc = (
            data["props"]
            ["pageProps"]
            ["doc"]
        )

    except (KeyError, TypeError) as exc:
        raise ValueError(
            "Não encontrei props.pageProps.doc."
        ) from exc

    if not isinstance(doc, dict):
        raise ValueError(
            "pageProps.doc não é um objeto."
        )

    return doc


def _extract_ecli(
    doc: dict[str, Any],
    source_url: str,
) -> Optional[str]:

    ecli = _simple_text(
        _find_value(
            doc,
            "ECLI",
        )
    )

    if ecli:
        return re.sub(
            r"\s+",
            "",
            ecli,
        )

    parsed = urlparse(source_url)

    last_part = (
        parsed.path
        .rstrip("/")
        .split("/")[-1]
    )

    if last_part.upper().startswith("ECLI"):
        return unquote(last_part)

    return None


def parse_case(
    html: bytes | str,
    source_url: str,
) -> StjCase:

    doc = _extract_doc(html)

    return StjCase(
        ecli=_extract_ecli(
            doc,
            source_url,
        ),

        process_number=_simple_text(
            _find_value(
                doc,
                "N.º de Processo",
                "Nº de Processo",
                "Numero de Processo",
                "Processo",
            )
        ),

        section=_simple_text(
            _find_value(
                doc,
                "Secção",
                "Seccao",
            )
        ),

        area=_simple_text(
            _find_value(
                doc,
                "Área",
                "Area",
            )
        ),

        rapporteur=_simple_text(
            _find_value(
                doc,
                "Relator",
                "Relator Nome Profissional",
            )
        ),

        descriptors=_descriptors(
            _find_value(
                doc,
                "Descritores",
            )
        ),

        decision_date=_parse_date(
            _find_value(
                doc,
                "Data",
                "Data do Acórdão",
            )
        ),

        procedural_type=_simple_text(
            _find_value(
                doc,
                "Meio Processual",
                "MeioProcessual",
            )
        ),

        decision=_simple_text(
            _find_value(
                doc,
                "Decisão",
                "Decisao",
            )
        ),

        voting=_simple_text(
            _find_value(
                doc,
                "Votação",
                "Votacao",
            )
        ),

        summary=_html_to_text(
            _find_value(
                doc,
                "Sumário",
                "Sumario",
            )
        ),

        full_text=_html_to_text(
            _find_value(
                doc,
                "Texto",
                "Decisão Texto Integral",
            )
        ),

        source_url=source_url,
    )