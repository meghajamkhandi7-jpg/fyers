"""FYERS REST client utilities for LiveBench tools."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import requests


class FyersClient:
    """Thin FYERS v3 HTTP client with env-driven configuration."""

    def __init__(
        self,
        access_token: Optional[str] = None,
        api_base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self.api_base_url = (api_base_url or os.getenv("FYERS_API_BASE_URL") or "https://api-t1.fyers.in/api/v3").rstrip("/")
        self.api_root_url = self._derive_api_root(self.api_base_url)
        self.access_token = access_token or os.getenv("FYERS_ACCESS_TOKEN")
        self.app_id = os.getenv("FYERS_APP_ID") or os.getenv("FYERS_CLIENT_ID")
        self.auth_header = os.getenv("FYERS_AUTH_HEADER")
        self.timeout_seconds = timeout_seconds or float(os.getenv("FYERS_TIMEOUT_SECONDS", "30"))

    @staticmethod
    def _derive_api_root(base_url: str) -> str:
        """Derive host root from configured API URL.

        Example:
        - https://api-t1.fyers.in/api/v3 -> https://api-t1.fyers.in
        - https://api-t1.fyers.in -> https://api-t1.fyers.in
        """
        markers = ["/api/v3", "/api/v2", "/api"]
        for marker in markers:
            if marker in base_url:
                return base_url.split(marker, 1)[0].rstrip("/")
        return base_url.rstrip("/")

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.access_token:
            token = self.access_token.strip()

            # 1) Explicit override (highest priority)
            if self.auth_header and self.auth_header.strip():
                headers["Authorization"] = self.auth_header.strip()
            # 2) Native FYERS format often required by APIs: APP_ID:ACCESS_TOKEN
            elif self.app_id and self.app_id.strip():
                headers["Authorization"] = f"{self.app_id.strip()}:{token}"
            # 3) Fallback to Bearer for compatibility
            else:
                if not token.lower().startswith("bearer "):
                    token = f"Bearer {token}"
                headers["Authorization"] = token
        return headers

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.access_token:
            return {
                "success": False,
                "error": "FYERS_ACCESS_TOKEN is not set",
                "message": "Set FYERS_ACCESS_TOKEN in .env before calling FYERS tools",
            }

        if path.startswith("http://") or path.startswith("https://"):
            url = path
        else:
            url = f"{self.api_base_url}/{path.lstrip('/')}"
        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=self._headers(),
                json=payload,
                params=params,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            return {
                "success": False,
                "error": f"Request failed: {exc}",
                "url": url,
            }

        body: Any
        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}

        success = 200 <= response.status_code < 300
        result = {
            "success": success,
            "status_code": response.status_code,
            "url": url,
            "data": body,
        }

        if not success:
            result["error"] = self._extract_error(body)

        return result

    @staticmethod
    def _extract_error(body: Any) -> str:
        if isinstance(body, dict):
            for key in ("message", "error", "reason", "s"):
                value = body.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            return json.dumps(body)
        return str(body)

    def profile(self) -> Dict[str, Any]:
        return self._request("GET", "/profile")

    def funds(self) -> Dict[str, Any]:
        return self._request("GET", "/funds")

    def holdings(self) -> Dict[str, Any]:
        return self._request("GET", "/holdings")

    def positions(self) -> Dict[str, Any]:
        return self._request("GET", "/positions")

    def quotes(self, symbols: str) -> Dict[str, Any]:
        attempts = [
            ("POST", "/quotes", {"symbols": symbols}, None),
            ("GET", "/quotes", None, {"symbols": symbols}),
            ("GET", "/data/quotes", None, {"symbols": symbols}),
            ("POST", "/data/quotes", {"symbols": symbols}, None),
            ("GET", f"{self.api_root_url}/data/quotes", None, {"symbols": symbols}),
            ("POST", f"{self.api_root_url}/data/quotes", {"symbols": symbols}, None),
            ("GET", f"{self.api_root_url}/quotes", None, {"symbols": symbols}),
            ("POST", f"{self.api_root_url}/quotes", {"symbols": symbols}, None),
        ]

        errors: list[Dict[str, Any]] = []
        for method, path, payload, params in attempts:
            result = self._request(method, path, payload=payload, params=params)
            if result.get("success"):
                result["quote_endpoint_used"] = f"{method} {path}"
                return result
            errors.append(
                {
                    "attempt": f"{method} {path}",
                    "status_code": result.get("status_code"),
                    "error": result.get("error"),
                    "url": result.get("url"),
                }
            )

        return {
            "success": False,
            "error": "All FYERS quote endpoint attempts failed",
            "attempts": errors,
        }

    def place_order(self, order_payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/orders", payload=order_payload)
