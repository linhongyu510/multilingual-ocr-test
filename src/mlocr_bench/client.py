"""HTTP client for the OCR service under test.

Credentials are never hardcoded. The API key is read, in priority order, from
the ``api_key`` argument, the ``MLOCR_API_KEY`` environment variable, or the
config file — so a key never has to live in version control.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["OCRResponse", "OCRClient", "MissingDependencyError"]

DEFAULT_ENDPOINT = "http://localhost:16110"
API_KEY_ENV_VAR = "MLOCR_API_KEY"
ENDPOINT_ENV_VAR = "MLOCR_ENDPOINT"


class MissingDependencyError(RuntimeError):
    """Raised when ``requests`` is unavailable."""


@dataclass
class OCRResponse:
    """Outcome of a single recognition request."""

    text: str
    status: str
    elapsed_seconds: float
    http_status: int | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "success"


class OCRClient:
    """Thin, retrying client for an OCR HTTP endpoint.

    The response shape is intentionally forgiving: services differ in whether
    they return ``{"data": [{"text": ...}]}``, ``{"results": [...]}`` or a bare
    ``{"text": ...}``, and all three are accepted.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        *,
        timeout: float = 30.0,
        retries: int = 2,
        backoff: float = 0.5,
        verify_tls: bool = True,
    ) -> None:
        self.endpoint = (endpoint or os.environ.get(ENDPOINT_ENV_VAR) or DEFAULT_ENDPOINT).rstrip("/")
        self.api_key = api_key or os.environ.get(API_KEY_ENV_VAR)
        self.timeout = timeout
        self.retries = max(0, retries)
        self.backoff = backoff
        self.verify_tls = verify_tls

        try:
            import requests  # noqa: PLC0415  (optional at import time)
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise MissingDependencyError(
                "the 'requests' package is required to call an OCR endpoint; "
                "install it with: pip install 'mlocr-bench[http]'"
            ) from exc
        self._session = requests.Session()
        self._requests = requests

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    @staticmethod
    def _extract_text(payload: Any) -> str:
        """Pull recognised text out of the various shapes services return."""
        if isinstance(payload, str):
            return payload
        if not isinstance(payload, dict):
            return ""
        for key in ("data", "results", "lines", "items"):
            block = payload.get(key)
            if isinstance(block, list):
                parts = [
                    str(item.get("text", "")) if isinstance(item, dict) else str(item)
                    for item in block
                ]
                joined = " ".join(p for p in parts if p)
                if joined:
                    return joined
        for key in ("text", "result", "content"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    def recognize(self, image_path: str | Path, language: str) -> OCRResponse:
        """Send one image and return the recognised text plus timing.

        Network and HTTP failures are captured in the returned object rather
        than raised, so a long benchmark run is never aborted by one bad
        sample. Transient failures (timeouts, connection errors, 5xx) are
        retried with exponential backoff; a 4xx is returned immediately since
        retrying an unsupported language cannot help.
        """
        image_path = Path(image_path)
        url = f"{self.endpoint}/v1/ocr"
        started = time.perf_counter()
        last_error: str | None = None
        last_http: int | None = None

        for attempt in range(self.retries + 1):
            try:
                with image_path.open("rb") as handle:
                    response = self._session.post(
                        url,
                        files={"file": (image_path.name, handle, "image/png")},
                        data={"language": language},
                        headers=self._headers(),
                        timeout=self.timeout,
                        verify=self.verify_tls,
                    )
                last_http = response.status_code

                if response.status_code == 200:
                    try:
                        payload = response.json()
                    except ValueError:
                        payload = response.text
                    return OCRResponse(
                        text=self._extract_text(payload),
                        status="success",
                        elapsed_seconds=time.perf_counter() - started,
                        http_status=200,
                    )

                # 4xx is a definitive answer (unsupported language, bad auth).
                if 400 <= response.status_code < 500:
                    return OCRResponse(
                        text="",
                        status=f"http_{response.status_code}",
                        elapsed_seconds=time.perf_counter() - started,
                        http_status=response.status_code,
                        error=response.text[:200],
                    )
                last_error = f"HTTP {response.status_code}"

            except self._requests.exceptions.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"[:200]

            if attempt < self.retries:
                time.sleep(self.backoff * (2**attempt))

        return OCRResponse(
            text="",
            status="unreachable",
            elapsed_seconds=time.perf_counter() - started,
            http_status=last_http,
            error=last_error,
        )

    def health_check(self) -> tuple[bool, str]:
        """Best-effort reachability probe; used to fail fast with clear advice."""
        for path in ("/health", "/healthz", "/"):
            try:
                response = self._session.get(
                    f"{self.endpoint}{path}", timeout=min(self.timeout, 5.0), verify=self.verify_tls
                )
                if response.status_code < 500:
                    return True, f"reachable ({path} -> HTTP {response.status_code})"
            except self._requests.exceptions.RequestException as exc:
                last = f"{type(exc).__name__}"
                continue
        return False, f"no response from {self.endpoint}"
