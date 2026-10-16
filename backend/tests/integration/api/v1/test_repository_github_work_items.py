from unittest.mock import AsyncMock, MagicMock

import pytest


def test_dashboard_category_filters_match_analyzer_categories(
    db_session, test_user_repository
):
    from app.models.finding import Finding
    from app.services.finding_service import list_findings

    db_session.add_all(
        [
            Finding(
                repository_id=test_user_repository.id,
                category=category,
                type=f"type-{category}",
                title=f"title-{category}",
                description="test",
                severity="low",
                status="open",
                source="test",
                evidence={},
            )
            for category in ("issue", "pull_request", "ci", "repository_activity")
        ]
    )
    db_session.commit()
    user_id = test_user_repository.connection.user_id

    _, issue_items, _ = list_findings(
        db_session, user_id, category="issues"
    )
    _, ci_items, _ = list_findings(
        db_session, user_id, category="ci_cd"
    )

    assert {finding.category for finding in issue_items} == {"issue"}
    assert {finding.category for finding in ci_items} == {
        "ci",
        "repository_activity",
    }


@pytest.mark.asyncio
async def test_repository_work_item_endpoints_return_github_data(
    authorized_client, test_user_repository, monkeypatch
):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    async def issues(full_name):
        assert full_name == test_user_repository.full_name
        return [
            {
                "number": 4,
                "title": "Reported issue",
                "state": "open",
                "html_url": "https://github.com/test-org/test-repo/issues/4",
                "labels": [],
                "user": {"login": "reporter"},
            },
            {
                "number": 5,
                "title": "PR returned by GitHub issue API",
                "state": "open",
                "html_url": "https://github.com/test-org/test-repo/pull/5",
                "pull_request": {"url": "https://api.github.com/pulls/5"},
                "labels": [],
                "user": {"login": "contributor"},
            },
        ]

    async def pulls(full_name):
        assert full_name == test_user_repository.full_name
        return [
            {
                "number": 6,
                "title": "Actual pull request",
                "state": "open",
                "html_url": "https://github.com/test-org/test-repo/pull/6",
                "labels": [],
                "user": {"login": "author"},
                "draft": False,
            }
        ]

    client.list_repository_issues = issues
    client.list_repository_pulls = pulls
    monkeypatch.setattr(
        "app.api.v1.repositories.GitHubAppClient",
        lambda **kwargs: client,
    )

    issues_response = await authorized_client.get(
        f"/api/v1/repositories/{test_user_repository.id}/issues"
    )
    pulls_response = await authorized_client.get(
        f"/api/v1/repositories/{test_user_repository.id}/pull-requests"
    )

    assert issues_response.status_code == 200
    assert [item["number"] for item in issues_response.json()] == [4]
    assert issues_response.json()[0]["title"] == "Reported issue"
    assert pulls_response.status_code == 200
    assert [item["number"] for item in pulls_response.json()] == [6]
    assert pulls_response.json()[0]["title"] == "Actual pull request"

@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['issues', 'pull-requests'])
async def test_work_items_enforce_ownership_before_github(authorized_client, monkeypatch, kind):
    import uuid
    factory = MagicMock()
    monkeypatch.setattr('app.api.v1.repositories.GitHubAppClient', factory)
    response = await authorized_client.get(f'/api/v1/repositories/{uuid.uuid4()}/{kind}')
    assert response.status_code == 404
    factory.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('kind,method', [('issues', 'list_repository_issues'), ('pull-requests', 'list_repository_pulls')])
async def test_work_item_empty_and_permission_errors_are_distinct(authorized_client, test_user_repository, monkeypatch, kind, method):
    from app.integrations.github.exceptions import GitHubAuthError
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    call = AsyncMock(return_value=[])
    setattr(client, method, call)
    monkeypatch.setattr('app.api.v1.repositories.GitHubAppClient', lambda **kwargs: client)
    path = f'/api/v1/repositories/{test_user_repository.id}/{kind}'
    response = await authorized_client.get(path)
    assert response.status_code == 200 and response.json() == []
    call.side_effect = GitHubAuthError('GitHub App permission denied', response_status=403)
    response = await authorized_client.get(path)
    assert response.status_code == 403
    assert response.json()['error']['code'] == 'github_permission_error'
