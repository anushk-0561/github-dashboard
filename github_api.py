"""
github_api.py
==============
All GitHub API interactions live here.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests

REST_BASE = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"


class GitHubAPIError(Exception):
    """Raised for any non-recoverable GitHub API failure."""
    pass


class GitHubClient:
    """GitHub API client with rate limit handling."""

    def __init__(self, token: str | None = None, timeout: int = 20) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN") or ""
        self.timeout = timeout
        self.session = requests.Session()
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-activity-dashboard",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token and not self.token.startswith("ghp_your"):
            headers["Authorization"] = f"Bearer {self.token}"
        self.session.headers.update(headers)

    def _handle_rate_limit(self, response: requests.Response) -> bool:
        """Handle rate limiting by sleeping until reset."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        if response.status_code in (403, 429) and remaining == "0":
            reset = int(response.headers.get("X-RateLimit-Reset", "0"))
            wait_s = max(reset - int(time.time()), 1)
            wait_s = min(wait_s, 60)
            time.sleep(wait_s)
            return True
        return False

    def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """GET request with retry logic."""
        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                raise GitHubAPIError(f"Network error: {exc}") from exc

            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                raise GitHubAPIError("User not found on GitHub.")
            if self._handle_rate_limit(resp):
                continue
            if resp.status_code == 401:
                raise GitHubAPIError("Invalid GitHub token (401 Unauthorized).")
            time.sleep(1 + attempt)
        raise GitHubAPIError(f"GitHub API call failed after retries: {resp.status_code}")

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Execute GraphQL query."""
        if not self.token or self.token.startswith("ghp_your"):
            raise GitHubAPIError(
                "GraphQL requires a GITHUB_TOKEN. Add one to your .env file."
            )
        try:
            resp = self.session.post(
                GRAPHQL_URL,
                json={"query": query, "variables": variables},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise GitHubAPIError(f"Network error: {exc}") from exc

        if resp.status_code != 200:
            raise GitHubAPIError(f"GraphQL failed: {resp.status_code}")
        data = resp.json()
        if "errors" in data:
            raise GitHubAPIError(f"GraphQL errors: {data['errors']}")
        return data["data"]

    def get_user(self, username: str) -> dict[str, Any]:
        """Fetch user profile."""
        return self._get(f"{REST_BASE}/users/{username}")

    def get_all_repos(self, username: str) -> list[dict[str, Any]]:
        """Fetch all repositories with pagination."""
        repos = []
        page = 1
        while True:
            chunk = self._get(
                f"{REST_BASE}/users/{username}/repos",
                params={"per_page": 100, "page": page, "type": "owner"},
            )
            if not chunk:
                break
            repos.extend(chunk)
            if len(chunk) < 100:
                break
            page += 1
            if page > 50:
                break
        return repos

    def get_contributions(self, username: str) -> dict[str, Any]:
        """Fetch contribution calendar via GraphQL."""
        query = """
        query($login: String!) {
          user(login: $login) {
            contributionsCollection {
              contributionCalendar {
                totalContributions
                weeks {
                  contributionDays {
                    date
                    contributionCount
                    weekday
                  }
                }
              }
            }
          }
        }
        """
        data = self._graphql(query, {"login": username})
        user = data.get("user")
        if not user:
            raise GitHubAPIError("User not found via GraphQL.")
        return user["contributionsCollection"]["contributionCalendar"]
    