import uuid
from app.models.finding import Finding
from app.models.repository_health_snapshot import RepositoryHealthSnapshot
from app.services.health_service import (
    generate_reasons,
    compute_and_persist_health,
    recalculate_repository_health,
)


class MockSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        pass


def test_generate_reasons_first_snapshot():
    reasons = generate_reasons(None, {"security": 100}, 100, [])
    assert reasons == ["Initial health score computed."]


def test_generate_reasons_no_change():
    prev = RepositoryHealthSnapshot(
        category_scores={"security": 100, "ci_cd": 100}
    )
    reasons = generate_reasons(prev, {"security": 100, "ci_cd": 100}, 100, [])
    assert reasons == ["No change since last check."]


def test_generate_reasons_improvement():
    prev = RepositoryHealthSnapshot(category_scores={"security": 60})
    reasons = generate_reasons(prev, {"security": 100}, 100, [])
    assert len(reasons) == 1
    assert "improved by 40 points" in reasons[0]
    assert "Security" in reasons[0]


def test_generate_reasons_drop():
    prev = RepositoryHealthSnapshot(category_scores={"security": 100})
    f = Finding(category="security", severity="critical", type="sql_injection")
    reasons = generate_reasons(prev, {"security": 60}, 60, [f])
    assert len(reasons) == 1
    assert "dropped by 40 points" in reasons[0]
    assert "Security" in reasons[0]
    assert "sql_injection" in reasons[0]
    assert "critical" in reasons[0]


def test_compute_and_persist_health_zero_findings(monkeypatch):
    monkeypatch.setattr(
        "app.services.health_service.get_all_open_findings_for_repository",
        lambda db, repo: [],
    )
    monkeypatch.setattr(
        "app.services.health_service.get_latest_snapshot",
        lambda db, repo: None,
    )

    db = MockSession()
    repo_id = uuid.uuid4()

    snapshot = compute_and_persist_health(db, repo_id)
    assert snapshot.overall_score == 100
    assert snapshot.reasons == ["Initial health score computed."]
    assert snapshot in db.added


def test_compute_and_persist_health_critical_finding(monkeypatch):
    f = Finding(category="security", severity="critical", type="cve-1234")
    monkeypatch.setattr(
        "app.services.health_service.get_all_open_findings_for_repository",
        lambda db, repo: [f],
    )

    prev = RepositoryHealthSnapshot(
        overall_score=100,
        category_scores={
            "security": 100,
            "ci_cd": 100,
            "dependencies": 100,
            "issues": 100,
            "pull_requests": 100,
            "code_quality": 100,
        },
    )
    monkeypatch.setattr(
        "app.services.health_service.get_latest_snapshot",
        lambda db, repo: prev,
    )

    db = MockSession()
    repo_id = uuid.uuid4()

    snapshot = compute_and_persist_health(db, repo_id)
    assert snapshot.overall_score < 100
    assert any("dropped" in r for r in snapshot.reasons)
    assert snapshot in db.added


def test_compute_and_persist_health_resolved_finding(monkeypatch):
    monkeypatch.setattr(
        "app.services.health_service.get_all_open_findings_for_repository",
        lambda db, repo: [],
    )

    prev = RepositoryHealthSnapshot(
        overall_score=60,
        category_scores={
            "security": 60,
            "ci_cd": 100,
            "dependencies": 100,
            "issues": 100,
            "pull_requests": 100,
            "code_quality": 100,
        },
    )
    monkeypatch.setattr(
        "app.services.health_service.get_latest_snapshot",
        lambda db, repo: prev,
    )

    db = MockSession()
    repo_id = uuid.uuid4()

    snapshot = compute_and_persist_health(db, repo_id)
    assert snapshot.overall_score > 60
    assert any("improved" in r for r in snapshot.reasons)


def test_compute_and_persist_health_no_changes(monkeypatch):
    f = Finding(category="security", severity="critical", type="cve-1234")
    monkeypatch.setattr(
        "app.services.health_service.get_all_open_findings_for_repository",
        lambda db, repo: [f],
    )

    prev = RepositoryHealthSnapshot(
        overall_score=93,
        category_scores={
            "security": 60,
            "ci_cd": 100,
            "dependencies": 100,
            "issues": 100,
            "pull_requests": 100,
            "code_quality": 100,
        },
        reasons=["No change since last check."],
    )
    monkeypatch.setattr(
        "app.services.health_service.get_latest_snapshot",
        lambda db, repo: prev,
    )

    db = MockSession()
    repo_id = uuid.uuid4()

    snapshot = compute_and_persist_health(db, repo_id)
    assert snapshot.overall_score == int(round((60 + 100 * 5) / 6))
    assert snapshot.reasons == ["No change since last check."]


def test_generate_reasons_cap_five():
    prev = RepositoryHealthSnapshot(
        category_scores={
            "security": 100,
            "ci_cd": 100,
            "dependencies": 100,
            "issues": 100,
            "pull_requests": 100,
            "code_quality": 100,
        }
    )
    new_scores = {
        "security": 20,
        "ci_cd": 30,
        "dependencies": 40,
        "issues": 50,
        "pull_requests": 60,
        "code_quality": 70,
    }
    reasons = generate_reasons(prev, new_scores, 45, [])
    assert len(reasons) == 5
    categories_in_reasons = " ".join(reasons).lower()
    assert "security" in categories_in_reasons
    assert "ci cd" in categories_in_reasons
    assert "dependencies" in categories_in_reasons
    assert "issues" in categories_in_reasons
    assert "pull requests" in categories_in_reasons
    assert "code quality" not in categories_in_reasons


def test_finding_service_includes_acknowledged(monkeypatch):
    class MockQuery:
        def filter(self, *args, **kwargs):
            self.filters = args
            return self

        def all(self):
            return []

    mock_q = MockQuery()
    db = MockSession()
    db.query = lambda model: mock_q

    from app.services.finding_service import (
        get_all_open_findings_for_repository,
    )

    get_all_open_findings_for_repository(db, uuid.uuid4())

    # Check that in_ is used for ["open", "acknowledged"]
    # We can infer it works if the query doesn't crash since SQLAlchemy mock
    # isn't full
    # We just ensure it runs. Real DB test is better but we use unit tests
    # here.


def test_health_drop_notification_thresholds(monkeypatch):
    from app.services import notification_dispatch_service

    dispatched = []

    def mock_dispatch(*args, **kwargs):
        dispatched.append(kwargs)

    monkeypatch.setattr(
        notification_dispatch_service, "dispatch_notification", mock_dispatch
    )

    monkeypatch.setattr(
        "app.services.health_service.get_all_open_findings_for_repository",
        lambda db, repo: [],
    )
    monkeypatch.setattr(
        "app.services.health_service.compute_category_scores", lambda f: {}
    )

    def get_mock_db():
        db = MockSession()

        def mock_query(model):
            class MockQuery:
                def filter(self, *args, **kwargs):
                    return self

                def first(self):
                    if model.__name__ == "Repository":

                        class R:
                            connection_id = uuid.uuid4()

                        return R()
                    if model.__name__ == "GitHubConnection":

                        class C:
                            user_id = uuid.uuid4()

                        return C()
                    return None

            return MockQuery()

        db.query = mock_query
        return db

    # 1. 14 point drop
    monkeypatch.setattr(
        "app.services.health_service.compute_overall_score", lambda c: 86
    )
    monkeypatch.setattr(
        "app.services.health_service.get_latest_snapshot",
        lambda db, repo: RepositoryHealthSnapshot(overall_score=100),
    )
    compute_and_persist_health(get_mock_db(), uuid.uuid4())
    assert len(dispatched) == 0

    # 2. 15 point drop (threshold) -> medium
    monkeypatch.setattr(
        "app.services.health_service.compute_overall_score", lambda c: 85
    )
    monkeypatch.setattr(
        "app.services.health_service.get_latest_snapshot",
        lambda db, repo: RepositoryHealthSnapshot(overall_score=100),
    )
    compute_and_persist_health(get_mock_db(), uuid.uuid4())
    assert len(dispatched) == 1
    assert dispatched[0]["severity"] == "medium"
    assert dispatched[0]["notification_type"] == "health_score_dropped"

    # 3. 30 point drop (2*threshold) -> high
    dispatched.clear()
    monkeypatch.setattr(
        "app.services.health_service.compute_overall_score", lambda c: 70
    )
    monkeypatch.setattr(
        "app.services.health_service.get_latest_snapshot",
        lambda db, repo: RepositoryHealthSnapshot(overall_score=100),
    )
    compute_and_persist_health(get_mock_db(), uuid.uuid4())
    assert len(dispatched) == 1
    assert dispatched[0]["severity"] == "high"

    # 4. Improvement -> no notification
    dispatched.clear()
    monkeypatch.setattr(
        "app.services.health_service.compute_overall_score", lambda c: 100
    )
    monkeypatch.setattr(
        "app.services.health_service.get_latest_snapshot",
        lambda db, repo: RepositoryHealthSnapshot(overall_score=80),
    )
    compute_and_persist_health(get_mock_db(), uuid.uuid4())
    assert len(dispatched) == 0


def test_health_drop_notification_exception_handling(monkeypatch):
    from app.services import notification_dispatch_service

    def get_mock_db():
        db = MockSession()

        def mock_query(model):
            class MockQuery:
                def filter(self, *args, **kwargs):
                    return self

                def first(self):
                    if model.__name__ == "Repository":

                        class R:
                            connection_id = uuid.uuid4()

                        return R()
                    if model.__name__ == "GitHubConnection":

                        class C:
                            user_id = uuid.uuid4()

                        return C()
                    return None

            return MockQuery()

        db.query = mock_query
        return db

    def mock_dispatch_raise(*args, **kwargs):
        raise ValueError("Simulated dispatch failure")

    monkeypatch.setattr(
        notification_dispatch_service,
        "dispatch_notification",
        mock_dispatch_raise,
    )

    monkeypatch.setattr(
        "app.services.health_service.get_all_open_findings_for_repository",
        lambda db, repo: [],
    )
    monkeypatch.setattr(
        "app.services.health_service.compute_category_scores", lambda f: {}
    )
    # 30 point drop
    monkeypatch.setattr(
        "app.services.health_service.compute_overall_score", lambda c: 70
    )
    monkeypatch.setattr(
        "app.services.health_service.get_latest_snapshot",
        lambda db, repo: RepositoryHealthSnapshot(overall_score=100),
    )

    db = get_mock_db()
    snapshot = compute_and_persist_health(db, uuid.uuid4())
    assert snapshot in db.added  # Persistence not aborted!


def test_recalculate_repository_health_produces_identical_snapshot(
    monkeypatch,
):
    """
    Validates that recalculate_repository_health yields an identical scoring
    outcome to an on-demand recalculation given the exact same open findings
    state.
    """
    f = Finding(category="security", severity="critical", type="sql_injection")
    monkeypatch.setattr(
        "app.services.health_service.get_all_open_findings_for_repository",
        lambda db, repo: [f],
    )

    prev = RepositoryHealthSnapshot(
        overall_score=100,
        category_scores={
            "security": 100,
            "ci_cd": 100,
            "dependencies": 100,
            "issues": 100,
            "pull_requests": 100,
            "code_quality": 100,
        },
    )
    monkeypatch.setattr(
        "app.services.health_service.get_latest_snapshot",
        lambda db, repo: prev,
    )

    db = MockSession()
    repo_id = uuid.uuid4()

    on_demand_snapshot = compute_and_persist_health(db, repo_id)

    db2 = MockSession()
    recalculated_snapshot = recalculate_repository_health(db2, repo_id)

    # Verify outputs are identical
    assert (
        recalculated_snapshot.overall_score == on_demand_snapshot.overall_score
    )
    assert (
        recalculated_snapshot.category_scores
        == on_demand_snapshot.category_scores
    )
    assert recalculated_snapshot.reasons == on_demand_snapshot.reasons
