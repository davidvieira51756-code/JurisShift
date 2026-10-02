import hashlib
import os
import time
import ssl
import truststore
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = PROJECT_ROOT / "data" / "raw"

TIMEOUT_SECONDS = float(
    os.getenv("DGSI_TIMEOUT_SECONDS", "90")
)

USER_AGENT = os.getenv(
    "DGSI_USER_AGENT",
    "JurisShift/0.1 research prototype",
)

MAX_RETRIES = 3


def _cache_filename(url: str) -> str:
    parsed = urlparse(url)

    last_part = parsed.path.rstrip("/").split("/")[-1]

    if last_part:
        safe_id = "".join(
            char
            for char in last_part
            if char.isalnum() or char in {"-", "_"}
        )

        if safe_id:
            return f"{safe_id}.html"

    digest = hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()

    return f"{digest}.html"


def fetch_case_html(
    url: str,
    force: bool = False,
) -> bytes:
    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache_path = CACHE_DIR / _cache_filename(url)

    if cache_path.exists() and not force:
        print(f"[cache] {cache_path.name}")
        return cache_path.read_bytes()

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.7",
        "Connection": "close",
    }

    timeout = httpx.Timeout(
        connect=20.0,
        read=TIMEOUT_SECONDS,
        write=30.0,
        pool=30.0,
    )

    last_error = None

    ssl_context = truststore.SSLContext(
    ssl.PROTOCOL_TLS_CLIENT
)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(
                f"[fetch] tentativa "
                f"{attempt}/{MAX_RETRIES}"
            )
            print(f"        {url}")

            with httpx.Client(
                headers=headers,
                timeout=timeout,
                follow_redirects=True,
                http2=False,
                verify=ssl_context,
            ) as client:
                response = client.get(url)

            response.raise_for_status()

            content = response.content

            if not content:
                raise RuntimeError(
                    "O DGSI devolveu uma resposta vazia."
                )

            cache_path.write_bytes(content)

            print(
                f"[saved] {cache_path.name} "
                f"({len(content):,} bytes)"
            )

            return content

        except (
            httpx.TimeoutException,
            httpx.NetworkError,
        ) as exc:
            last_error = exc

            print(
                f"[retry] {type(exc).__name__}: "
                f"{exc}"
            )

        except httpx.HTTPStatusError as exc:
            last_error = exc

            status = exc.response.status_code

            print(
                f"[http] status {status}"
            )

            # Não vale a pena insistir em erros permanentes.
            if status not in {
                408,
                429,
                500,
                502,
                503,
                504,
            }:
                raise

        if attempt < MAX_RETRIES:
            wait_seconds = 2 ** attempt

            print(
                f"[wait] {wait_seconds}s "
                f"antes de tentar novamente..."
            )

            time.sleep(wait_seconds)

    raise RuntimeError(
        "Não foi possível obter o acórdão do DGSI "
        f"após {MAX_RETRIES} tentativas."
    ) from last_error