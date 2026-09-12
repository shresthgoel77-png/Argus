from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RepoRef:
    github_repo_id: int
    full_name: str


@dataclass
class NormalizedWebhookEvent:
    delivery_id: str
    event_type: str
    action: str | None
    installation_id: int | None
    repository: RepoRef | None
    installation_account_login: str | None
    installation_account_type: str | None
    repositories_removed: list[RepoRef]
    raw_payload: dict[str, Any]


def parse_webhook_payload(
    event_type: str, delivery_id: str, payload: dict[str, Any]
) -> NormalizedWebhookEvent:
    """Safely parse a GitHub webhook payload into a normalized internal representation."""
    if not isinstance(payload, dict):
        payload = {}

    action = payload.get("action")

    installation = payload.get("installation")
    if not isinstance(installation, dict):
        installation = {}

    installation_id = installation.get("id")

    install_account = installation.get("account")
    if not isinstance(install_account, dict):
        install_account = {}

    installation_account_login = None
    installation_account_type = None
    if event_type in ("installation", "installation_repositories"):
        installation_account_login = install_account.get("login")
        installation_account_type = install_account.get("type")

    repository = None
    if event_type in ("pull_request", "issues", "issue_comment", "workflow_run", "push"):
        repo = payload.get("repository")
        if isinstance(repo, dict):
            repo_id = repo.get("id")
            repo_name = repo.get("full_name")
            if repo_id is not None and repo_name is not None:
                repository = RepoRef(github_repo_id=repo_id, full_name=repo_name)

    repositories_removed: list[RepoRef] = []
    if event_type == "installation_repositories":
        removed_repos = payload.get("repositories_removed")
        if isinstance(removed_repos, list):
            for r in removed_repos:
                if isinstance(r, dict):
                    r_id = r.get("id")
                    r_name = r.get("full_name")
                    if r_id is not None and r_name is not None:
                        repositories_removed.append(
                            RepoRef(github_repo_id=r_id, full_name=r_name)
                        )

    return NormalizedWebhookEvent(
        delivery_id=delivery_id,
        event_type=event_type,
        action=action,
        installation_id=installation_id,
        repository=repository,
        installation_account_login=installation_account_login,
        installation_account_type=installation_account_type,
        repositories_removed=repositories_removed,
        raw_payload=payload,
    )
