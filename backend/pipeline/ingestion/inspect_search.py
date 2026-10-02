import re
import ssl
from pathlib import Path
from urllib.parse import urljoin

import httpx
import truststore
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[3]

CACHE_PATH = (
    PROJECT_ROOT
    / "data"
    / "cache"
    / "search_vencimento_antecipado.html"
)

SEARCH_URL = (
    "https://juris.stj.pt/pesquisa"
    "?Descritores=Vencimento+antecipado"
)


def clean(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def main():
    CACHE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    ssl_context = truststore.SSLContext(
        ssl.PROTOCOL_TLS_CLIENT
    )

    if CACHE_PATH.exists():
        print("[cache] página de pesquisa")
        html = CACHE_PATH.read_bytes()

    else:
        print("[fetch] página de pesquisa")
        print(SEARCH_URL)

        with httpx.Client(
            verify=ssl_context,
            follow_redirects=True,
            timeout=30,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "JurisShift/0.1"
                ),
            },
        ) as client:
            response = client.get(
                SEARCH_URL
            )

            response.raise_for_status()

            html = response.content

        CACHE_PATH.write_bytes(html)

        print(
            f"[saved] "
            f"{len(html):,} bytes"
        )

    soup = BeautifulSoup(
        html,
        "lxml",
    )

    print()
    print("=" * 80)
    print("POSSÍVEIS RESULTADOS")
    print("=" * 80)

    found = []

    for anchor in soup.find_all(
        "a",
        href=True,
    ):
        text = clean(
            anchor.get_text(
                " ",
                strip=True,
            )
        )

        href = anchor["href"]

        # Os resultados normalmente mostram
        # o número do processo no link.
        if not re.search(
            r"\d+/\d+",
            text,
        ):
            continue

        absolute_url = urljoin(
            "https://juris.stj.pt",
            href,
        )

        item = (
            text,
            absolute_url,
        )

        if item not in found:
            found.append(item)

    for index, (
        text,
        url,
    ) in enumerate(
        found[:20],
        start=1,
    ):
        print()
        print(f"{index}. {text}")
        print(f"   {url}")

    print()
    print("=" * 80)
    print(
        f"Encontrados: {len(found)}"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()