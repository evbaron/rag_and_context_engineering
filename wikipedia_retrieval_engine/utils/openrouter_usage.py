#!/usr/bin/env python3
"""Print and optionally log OpenRouter key usage and account credits.

Examples
--------
Check the API key used by the capstone scripts::

    python utils/openrouter_usage.py

Append a post-run snapshot to a CSV::

    python utils/openrouter_usage.py \
        --experiment-name vector_search_base \
        --log-csv "Capstone Checkpoint 4.1/openrouter_usage_log.csv"

The script reads OPENROUTER_API_KEY from the environment or a nearby .env file.
It never prints the API key itself.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT_SECONDS = 30.0

LOG_COLUMNS = [
    "logged_at_utc",
    "experiment_name",
    "key_label",
    "is_management_key",
    "is_free_tier",
    "usage",
    "usage_daily",
    "usage_weekly",
    "usage_monthly",
    "limit",
    "limit_remaining",
    "limit_reset",
    "byok_usage",
    "byok_usage_daily",
    "byok_usage_weekly",
    "byok_usage_monthly",
    "account_total_credits",
    "account_total_usage",
    "account_remaining_credits",
    "credits_error",
]


class OpenRouterUsageError(RuntimeError):
    """User-facing API or configuration error."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check OpenRouter usage for the configured API key."
    )
    parser.add_argument(
        "--key-env",
        default="OPENROUTER_API_KEY",
        help="Environment variable containing the API key to inspect.",
    )
    parser.add_argument(
        "--management-key-env",
        default="OPENROUTER_MANAGEMENT_KEY",
        help=(
            "Environment variable containing an optional management key for "
            "account credits, key listing, or --key-hash lookups."
        ),
    )
    parser.add_argument(
        "--env-file",
        action="append",
        type=Path,
        default=[],
        help=(
            "Additional .env file to load before reading keys. May be passed "
            "multiple times."
        ),
    )
    parser.add_argument(
        "--experiment-name",
        "--config-name",
        dest="experiment_name",
        default="",
        help="Optional run label to include when appending --log-csv.",
    )
    parser.add_argument(
        "--log-csv",
        type=Path,
        help="Optional CSV path where a timestamped usage snapshot is appended.",
    )
    parser.add_argument(
        "--key-hash",
        help=(
            "Inspect a specific key by hash using the management-key endpoint "
            "instead of the current OPENROUTER_API_KEY."
        ),
    )
    parser.add_argument(
        "--list-keys",
        action="store_true",
        help="List keys visible to the management key, then exit.",
    )
    parser.add_argument(
        "--include-disabled",
        action="store_true",
        help="Include disabled keys when using --list-keys.",
    )
    parser.add_argument(
        "--no-credits",
        action="store_true",
        help="Skip the account-level /credits request.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON data instead of the human-readable summary.",
    )
    parser.add_argument(
        "--warn-below",
        type=float,
        help=(
            "Print a warning if account credits or key limit remaining fall "
            "below this number of credits."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=OPENROUTER_BASE_URL,
        help=f"OpenRouter API base URL (default: {OPENROUTER_BASE_URL}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS:g}).",
    )
    return parser.parse_args(argv)


def load_env_files(extra_env_files: list[Path]) -> None:
    """Load simple KEY=VALUE entries without requiring python-dotenv."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / ".env",
        here.parents[3] / ".env",
        Path.cwd() / ".env",
        *extra_env_files,
    ]

    seen: set[Path] = set()
    for path in candidates:
        path = path.expanduser().resolve()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value


def get_required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise OpenRouterUsageError(
            f"{name} is not set. Put it in rag_and_context_engineering/.env "
            "or export it in your shell before running this script."
        )
    return value


def get_optional_env(name: str) -> str:
    return os.environ.get(name, "").strip()


def endpoint(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def api_get(
    base_url: str,
    path: str,
    token: str,
    *,
    timeout: float,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = endpoint(base_url, path)
    if query:
        url = f"{url}?{urlencode(query)}"
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        message = f"OpenRouter returned HTTP {exc.code} for {path}"
        if detail:
            message = f"{message}: {detail}"
        raise OpenRouterUsageError(message) from exc
    except URLError as exc:
        raise OpenRouterUsageError(f"Could not reach OpenRouter: {exc.reason}") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise OpenRouterUsageError(
            f"OpenRouter returned non-JSON response for {path}: {body[:200]}"
        ) from exc
    if not isinstance(payload, dict):
        raise OpenRouterUsageError(f"Unexpected response shape for {path}: {payload!r}")
    return payload


def data_object(payload: dict[str, Any], path: str) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise OpenRouterUsageError(f"OpenRouter response for {path} did not contain a data object.")
    return data


def data_list(payload: dict[str, Any], path: str) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list):
        raise OpenRouterUsageError(f"OpenRouter response for {path} did not contain a data list.")
    return [item for item in data if isinstance(item, dict)]


def as_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def format_credits(value: Any) -> str:
    number = as_number(value)
    return "n/a" if number is None else f"{number:,.4f}"


def format_bool(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "n/a"


def account_remaining(credits_data: dict[str, Any] | None) -> float | None:
    if not credits_data:
        return None
    total_credits = as_number(credits_data.get("total_credits"))
    total_usage = as_number(credits_data.get("total_usage"))
    if total_credits is None or total_usage is None:
        return None
    return total_credits - total_usage


def print_key_summary(key_data: dict[str, Any]) -> None:
    print("OpenRouter key usage")
    print(f"Label: {key_data.get('label', 'n/a')}")
    print(f"Management key: {format_bool(key_data.get('is_management_key'))}")
    print(f"Free tier: {format_bool(key_data.get('is_free_tier'))}")
    print(f"Usage: {format_credits(key_data.get('usage'))} credits")
    print(f"Daily usage: {format_credits(key_data.get('usage_daily'))} credits")
    print(f"Weekly usage: {format_credits(key_data.get('usage_weekly'))} credits")
    print(f"Monthly usage: {format_credits(key_data.get('usage_monthly'))} credits")
    print(f"Limit: {format_credits(key_data.get('limit'))} credits")
    print(f"Limit remaining: {format_credits(key_data.get('limit_remaining'))} credits")
    print(f"Limit reset: {key_data.get('limit_reset') or 'n/a'}")
    print(f"Expires at: {key_data.get('expires_at') or 'n/a'}")
    if any(field in key_data for field in ("byok_usage", "byok_usage_daily")):
        print(f"BYOK usage: {format_credits(key_data.get('byok_usage'))} credits")


def print_credits_summary(
    credits_data: dict[str, Any] | None,
    credits_error: str,
) -> None:
    print()
    print("OpenRouter account credits")
    if credits_error:
        print(f"Unavailable: {credits_error}")
        print("Tip: /credits may require OPENROUTER_MANAGEMENT_KEY.")
        return
    if credits_data is None:
        print("Skipped.")
        return
    print(f"Total credits: {format_credits(credits_data.get('total_credits'))}")
    print(f"Total usage: {format_credits(credits_data.get('total_usage'))}")
    print(f"Remaining: {format_credits(account_remaining(credits_data))}")


def print_key_list(keys: list[dict[str, Any]]) -> None:
    print("OpenRouter API keys")
    if not keys:
        print("(none returned)")
        return
    for key in keys:
        print(
            " | ".join(
                [
                    f"name={key.get('name') or 'n/a'}",
                    f"label={key.get('label') or 'n/a'}",
                    f"hash={key.get('hash') or 'n/a'}",
                    f"usage={format_credits(key.get('usage'))}",
                    f"remaining={format_credits(key.get('limit_remaining'))}",
                    f"limit={format_credits(key.get('limit'))}",
                    f"reset={key.get('limit_reset') or 'n/a'}",
                    f"disabled={format_bool(key.get('disabled'))}",
                ]
            )
        )


def log_usage_snapshot(
    log_path: Path,
    experiment_name: str,
    key_data: dict[str, Any],
    credits_data: dict[str, Any] | None,
    credits_error: str,
) -> None:
    log_path = log_path.expanduser().resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    existing_header: list[str] | None = None
    if log_path.is_file() and log_path.stat().st_size > 0:
        with log_path.open(newline="", encoding="utf-8") as stream:
            existing_header = next(csv.reader(stream), None)
        if existing_header != LOG_COLUMNS:
            raise OpenRouterUsageError(
                f"{log_path} has an unexpected header. Choose a new --log-csv "
                "path or update it to match this script's schema."
            )

    row = {
        "logged_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "experiment_name": experiment_name,
        "key_label": key_data.get("label"),
        "is_management_key": key_data.get("is_management_key"),
        "is_free_tier": key_data.get("is_free_tier"),
        "usage": key_data.get("usage"),
        "usage_daily": key_data.get("usage_daily"),
        "usage_weekly": key_data.get("usage_weekly"),
        "usage_monthly": key_data.get("usage_monthly"),
        "limit": key_data.get("limit"),
        "limit_remaining": key_data.get("limit_remaining"),
        "limit_reset": key_data.get("limit_reset"),
        "byok_usage": key_data.get("byok_usage"),
        "byok_usage_daily": key_data.get("byok_usage_daily"),
        "byok_usage_weekly": key_data.get("byok_usage_weekly"),
        "byok_usage_monthly": key_data.get("byok_usage_monthly"),
        "account_total_credits": None if credits_data is None else credits_data.get("total_credits"),
        "account_total_usage": None if credits_data is None else credits_data.get("total_usage"),
        "account_remaining_credits": account_remaining(credits_data),
        "credits_error": credits_error,
    }
    with log_path.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=LOG_COLUMNS)
        if existing_header is None:
            writer.writeheader()
        writer.writerow(row)
    print(f"\nUsage snapshot appended to: {log_path}")


def warn_if_low(
    threshold: float | None,
    key_data: dict[str, Any],
    credits_data: dict[str, Any] | None,
) -> None:
    if threshold is None:
        return
    remaining = account_remaining(credits_data)
    label = "account credits"
    if remaining is None:
        remaining = as_number(key_data.get("limit_remaining"))
        label = "key limit remaining"
    if remaining is not None and remaining < threshold:
        print(
            f"WARNING: OpenRouter {label} is {remaining:.4f}, below {threshold:.4f}.",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_env_files(args.env_file)

    try:
        management_key = get_optional_env(args.management_key_env)

        if args.list_keys:
            token = management_key or get_required_env(args.key_env)
            payload = api_get(
                args.base_url,
                "/keys",
                token,
                timeout=args.timeout,
                query={"include_disabled": "true"} if args.include_disabled else None,
            )
            keys = data_list(payload, "/keys")
            if args.json:
                print(json.dumps({"keys": keys}, indent=2, sort_keys=True))
            else:
                print_key_list(keys)
            return 0

        if args.key_hash:
            token = management_key or get_required_env(args.key_env)
            key_payload = api_get(
                args.base_url,
                f"/keys/{args.key_hash}",
                token,
                timeout=args.timeout,
            )
            key_data = data_object(key_payload, f"/keys/{args.key_hash}")
        else:
            api_key = get_required_env(args.key_env)
            key_payload = api_get(
                args.base_url,
                "/key",
                api_key,
                timeout=args.timeout,
            )
            key_data = data_object(key_payload, "/key")

        credits_data: dict[str, Any] | None = None
        credits_error = ""
        if not args.no_credits:
            try:
                credits_payload = api_get(
                    args.base_url,
                    "/credits",
                    management_key or get_required_env(args.key_env),
                    timeout=args.timeout,
                )
                credits_data = data_object(credits_payload, "/credits")
            except OpenRouterUsageError as exc:
                credits_error = str(exc)

        if args.json:
            print(
                json.dumps(
                    {
                        "key": key_data,
                        "credits": credits_data,
                        "credits_error": credits_error,
                        "account_remaining_credits": account_remaining(credits_data),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print_key_summary(key_data)
            print_credits_summary(credits_data, credits_error)

        warn_if_low(args.warn_below, key_data, credits_data)

        if args.log_csv:
            log_usage_snapshot(
                args.log_csv,
                args.experiment_name.strip(),
                key_data,
                credits_data,
                credits_error,
            )
        return 0
    except OpenRouterUsageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
