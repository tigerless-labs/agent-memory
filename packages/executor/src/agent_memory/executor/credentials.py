"""Short-lived credentials for hosts that need them.

A Vertex access token lasts about an hour and a benchmark matrix runs longer than that, so
the token is minted on demand and refreshed before it goes stale rather than captured once at
launch. Nothing here is written to disk or logged: the value is handed straight to the child
process environment.
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
import time

GCLOUD = "gcloud"
TOKEN_COMMAND = ("auth", "print-access-token")
ACCOUNT_ENV = "GCLOUD_ACCOUNT"
PROJECT_ENV = "GOOGLE_CLOUD_PROJECT"
LOCATION_ENV = "VERTEX_LOCATION"
BASE_URL_ENV = "GEMINI_BASE_URL"
API_KEY_ENV = "GEMINI_API_KEY"
VERTEX_URL = (
    "https://aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/endpoints/openapi"
)
REFRESH_SECONDS = 1800.0
TOKEN_TIMEOUT_SECONDS = 60.0


@dataclasses.dataclass
class VertexCredentials:
    """Mints and reuses one token, refreshing it well before an hour is up."""

    minted_at: float = 0.0
    token: str = ""

    def environment(self) -> dict[str, str]:
        project = os.environ.get(PROJECT_ENV, "")
        location = os.environ.get(LOCATION_ENV, "")
        if not project or not location:
            return {}
        if os.environ.get(API_KEY_ENV):
            return {}
        token = self._token()
        if not token:
            return {}
        return {
            BASE_URL_ENV: VERTEX_URL.format(project=project, location=location),
            API_KEY_ENV: token,
        }

    def _token(self, now: float | None = None) -> str:
        moment = time.monotonic() if now is None else now
        if self.token and moment - self.minted_at < REFRESH_SECONDS:
            return self.token
        minted = self._mint()
        if minted:
            self.token = minted
            self.minted_at = moment
        return self.token

    def _mint(self) -> str:
        command = [GCLOUD, *TOKEN_COMMAND]
        account = os.environ.get(ACCOUNT_ENV)
        if account:
            command.append(f"--account={account}")
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=TOKEN_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return completed.stdout.strip() if completed.returncode == 0 else ""
