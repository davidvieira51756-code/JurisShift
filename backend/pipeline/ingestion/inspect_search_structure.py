import json
import re
from pathlib import Path

from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[3]

HTML_PATH = (
    PROJECT_ROOT
    / "data"
    / "cache"
    / "search_vencimento_antecipado.html"
)


def main():
    html = HTML_PATH.read_text(
        encoding="utf-8",
        errors="replace",
    )

    soup = BeautifulSoup(html, "lxml")

    print("=" * 80)
    print("__NEXT_DATA__")
    print("=" * 80)

    next_data = soup.find(
        "script",
        id="__NEXT_DATA__",
    )

    if next_data:
        raw = next_data.string or next_data.get_text()

        data = json.loads(raw)

        print(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )[:8000]
        )
    else:
        print("Não encontrado")

    print()
    print("=" * 80)
    print("SCRIPTS")
    print("=" * 80)

    for script in soup.find_all(
        "script",
        src=True,
    ):
        print(script["src"])

    print()
    print("=" * 80)
    print("URLs / ENDPOINTS SUSPEITOS NO HTML")
    print("=" * 80)

    patterns = [
        r'https?://[^"\'\s<>]+',
        r'["\']([^"\']*(?:api|search|pesquisa)[^"\']*)["\']',
    ]

    found = set()

    for pattern in patterns:
        for match in re.findall(
            pattern,
            html,
            flags=re.IGNORECASE,
        ):
            value = (
                match
                if isinstance(match, str)
                else match[0]
            )

            if value not in found:
                found.add(value)
                print(value)


if __name__ == "__main__":
    main()