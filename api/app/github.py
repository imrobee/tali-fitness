"""Asking GitHub Actions to run a workflow now (REST "Create a workflow dispatch event",
docs.github.com). Used by the demo's self-heal (D121) and by Sync now in production (D133).

The token is a fine-grained one with Actions: write on one repository only. It is never
logged, and neither is GitHub's answer body.
"""

import logging

import httpx2
from pydantic import SecretStr

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"  # the current version on docs.github.com, 2026-11-05
BRANCH = "main"  # GitHub dispatches only workflows on the default branch


def dispatch_workflow(
    repo: str,
    workflow: str,
    token: SecretStr,
    inputs: dict[str, str] | None = None,
    transport: httpx2.BaseTransport | None = None,
) -> bool:
    """POST .../actions/workflows/<workflow>/dispatches. True when GitHub accepted it."""
    url = f"{GITHUB_API}/repos/{repo}/actions/workflows/{workflow}/dispatches"
    headers = {
        "Authorization": f"Bearer {token.get_secret_value()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    body: dict = {"ref": BRANCH}
    if inputs:
        body["inputs"] = inputs
    try:
        with httpx2.Client(transport=transport, timeout=10) as client:
            response = client.post(url, json=body, headers=headers)
    except httpx2.HTTPError as error:
        logger.warning(
            "github_dispatch_failed workflow=%s error=%s", workflow, type(error).__name__
        )
        return False
    logger.info("github_dispatch workflow=%s status=%s", workflow, response.status_code)
    return response.is_success
