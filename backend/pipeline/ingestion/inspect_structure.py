from pathlib import Path
import re

from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[3]

HTML_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "ECLI3APT3ASTJ3A20223A448217T8MAIAP1S1C8.html"
)

KEYWORDS = [
    "processo",
    "relator",
    "descritores",
    "data",
    "sumário",
    "sumario",
    "decisão",
    "decisao",
    "texto integral",
    "ecli",
]


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def main():
    html = HTML_PATH.read_text(
        encoding="utf-8",
        errors="replace",
    )

    soup = BeautifulSoup(
        html,
        "lxml",
    )

    print("=" * 80)
    print("TITLE")
    print("=" * 80)

    print(
        soup.title.get_text(" ", strip=True)
        if soup.title
        else "SEM TITLE"
    )

    print()

    for keyword in KEYWORDS:
        print("=" * 80)
        print(f"KEYWORD: {keyword}")
        print("=" * 80)

        matches = soup.find_all(
            string=re.compile(
                re.escape(keyword),
                re.IGNORECASE,
            )
        )

        if not matches:
            print("SEM RESULTADOS")
            print()
            continue

        for index, node in enumerate(
            matches[:8],
            start=1,
        ):
            parent = node.parent

            print(f"\n--- RESULTADO {index} ---")

            if parent is None:
                print(clean(str(node))[:1000])
                continue

            print(f"TAG: {parent.name}")
            print(f"ATTRS: {parent.attrs}")

            print("TEXT:")
            print(
                clean(
                    parent.get_text(
                        " ",
                        strip=True,
                    )
                )[:1500]
            )

            ancestor = parent.parent

            if ancestor is not None:
                print("\nPARENT:")
                print(f"TAG: {ancestor.name}")
                print(f"ATTRS: {ancestor.attrs}")

                print(
                    clean(
                        ancestor.get_text(
                            " ",
                            strip=True,
                        )
                    )[:2000]
                )

        print()

    print("=" * 80)
    print("POSSÍVEIS BLOCOS JSON / SCRIPT")
    print("=" * 80)

    for script in soup.find_all("script"):
        content = script.string or script.get_text()

        if not content:
            continue

        lowered = content.casefold()

        if any(
            keyword.casefold() in lowered
            for keyword in KEYWORDS
        ):
            print()
            print(
                clean(content)[:3000]
            )


if __name__ == "__main__":
    main()