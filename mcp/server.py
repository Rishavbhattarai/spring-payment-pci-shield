# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2", "pyyaml>=6"]
# ///
"""pci-shield-verify: MCP tools that check payment endpoints at runtime instead of by reading code.
Started by the plugin's .mcp.json via `uv run --script`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP  # noqa: E402

import verify_tools  # noqa: E402

mcp = FastMCP("pci-shield-verify")


@mcp.tool()
def docker_status() -> dict:
    """Check whether a Docker daemon is reachable. Testcontainers-based tests need it; without it they skip."""
    return verify_tools.docker_status()


@mcp.tool()
def openapi_idempotency_check(spec: str) -> dict:
    """List money-moving POST/PATCH operations (payment, checkout, charge, refund, transfer, payout, ...)
    in an OpenAPI 3 spec (file path or http(s) URL, JSON or YAML) that don't declare an Idempotency-Key header."""
    return verify_tools.openapi_idempotency_check(spec)


@mcp.tool()
def concurrency_probe(url: str, body: str, method: str = "POST", headers: dict | None = None,
                      concurrency: int = 10, id_field: str = "id") -> dict:
    """Fire `concurrency` identical requests at the same instant against a RUNNING service and report how many
    distinct resources were created (read from `id_field` of 2xx JSON responses). Pass the same Idempotency-Key in
    `headers` to simulate client retries: an idempotent endpoint must return SINGLE_RESOURCE. Never point this at
    production or a real PSP: it really sends the requests."""
    return verify_tools.concurrency_probe(url, body, method, headers, max(1, min(concurrency, 100)), id_field)


@mcp.tool()
def run_integration_tests(project_dir: str, test_pattern: str | None = None, java_home: str | None = None) -> dict:
    """Run the project's Maven/Gradle tests (optionally filtered, e.g. "PaymentApiIT") and return parsed JUnit
    results, including whether Docker was available. Use it to prove rollback and idempotency behaviour with
    Testcontainers. A skipped IT is not a pass."""
    return verify_tools.run_integration_tests(project_dir, test_pattern, java_home)


if __name__ == "__main__":
    mcp.run()
