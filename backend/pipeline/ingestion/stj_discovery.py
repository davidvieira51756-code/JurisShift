import os
import ssl
import time
from urllib.parse import quote

import httpx
import truststore
from dotenv import load_dotenv


load_dotenv()

BASE_URL = "https://juris.stj.pt"
SEARCH_API_URL = f"{BASE_URL}/api/search"

REQUEST_DELAY = float(
    os.getenv("DGSI_REQUEST_DELAY_SECONDS", "1.75")
)

TIMEOUT_SECONDS = float(
    os.getenv("DGSI_TIMEOUT_SECONDS", "30")
)


def _preferred(value):
    if isinstance(value, dict):
        for key in ("Show", "Original", "Index"):
            candidate = value.get(key)

            if candidate not in (
                None,
                "",
                [],
                {},
            ):
                return candidate

    return value


def _first(value):
    value = _preferred(value)

    if isinstance(value, list):
        return value[0] if value else None

    return value


def _build_case_url(source: dict) -> str | None:
    ecli = _first(
        source.get("ECLI")
    )

    if ecli:
        encoded = quote(
            str(ecli),
            safe="",
        )

        return (
            f"{BASE_URL}/ecli/{encoded}"
        )

    process_number = (
        source.get("Número de Processo")
        or source.get("N.º de Processo")
        or source.get("Processo")
    )

    uuid = source.get("UUID")

    process_number = _first(
        process_number
    )

    uuid = _first(uuid)

    if process_number and uuid:
        encoded_process = quote(
            str(process_number),
            safe="",
        )

        encoded_uuid = quote(
            str(uuid),
            safe="",
        )

        return (
            f"{BASE_URL}/"
            f"{encoded_process}/"
            f"{encoded_uuid}"
        )

    return None


def discover_cases(
    descriptor: str,
    max_pages: int | None = None,
) -> list[dict]:

    ssl_context = truststore.SSLContext(
        ssl.PROTOCOL_TLS_CLIENT
    )

    timeout = httpx.Timeout(
        connect=20,
        read=TIMEOUT_SECONDS,
        write=30,
        pool=30,
    )

    results = []
    seen_urls = set()

    page = 0

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "JurisShift/0.1"
        ),
        "Accept": "application/json",
    }

    with httpx.Client(
        verify=ssl_context,
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
    ) as client:

        while True:
            if (
                max_pages is not None
                and page >= max_pages
            ):
                break

            print(
                f"[search] página {page}"
            )

            response = client.get(
                SEARCH_API_URL,
                params={
                    "Descritores": descriptor,
                    "page": page,
                },
            )

            response.raise_for_status()

            hits = response.json()

            if not isinstance(hits, list):
                raise RuntimeError(
                    "A API de pesquisa não devolveu uma lista."
                )

            if not hits:
                break

            print(
                f"         {len(hits)} resultados"
            )

            for hit in hits:
                source = hit.get(
                    "_source",
                    {},
                )

                url = _build_case_url(
                    source
                )

                if not url:
                    print(
                        "[skip] resultado sem URL identificável"
                    )
                    continue

                if url in seen_urls:
                    continue

                seen_urls.add(url)

                results.append(
                    {
                        "url": url,
                        "ecli": _first(
                            source.get("ECLI")
                        ),
                        "process_number": _first(
                            source.get(
                                "Número de Processo"
                            )
                            or source.get(
                                "N.º de Processo"
                            )
                        ),
                        "date": _first(
                            source.get("Data")
                        ),
                        "rapporteur": _first(
                            source.get(
                                "Relator Nome Profissional"
                            )
                        ),
                    }
                )

            # A API entrega 10 por página.
            # Se vierem menos de 10 chegámos à última.
            if len(hits) < 10:
                break

            page += 1

            time.sleep(
                REQUEST_DELAY
            )

    return results