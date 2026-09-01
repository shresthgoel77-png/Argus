import json
import os

import pytest
from fastapi.testclient import TestClient

from simulator import app as app_module
from simulator.app import app
from simulator.config import CONFIG_PATH, DEFAULT_CONFIG
from simulator.razorpay_utils import build_test_payment_event, sign_payload


client = TestClient(app)


def _metric_value(metrics_text, metric_name, labels=""):
    prefix = f"{metric_name}{labels} "
    for line in metrics_text.splitlines():
        if line.startswith(prefix):
            return float(line[len(prefix):])
    return 0.0


@pytest.fixture(autouse=True)
def reset_demo_state(monkeypatch):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    config = DEFAULT_CONFIG.copy()
    config["webhook_failure_rate"] = 0.0
    config["latency_ms_base"] = 0
    config["latency_ms_jitter"] = 0
    with open(CONFIG_PATH, "w") as config_file:
        json.dump(config, config_file)
    app_module._seen_razorpay_event_ids.clear()
    app_module._last_demo_event_id = None
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "test-secret")


def test_signed_fresh_event_is_accepted():
    event = build_test_payment_event()
    raw_body = json.dumps(event, separators=(",", ":")).encode()

    response = client.post(
        "/webhook/razorpay-event",
        content=raw_body,
        headers={"X-Razorpay-Signature": sign_payload("test-secret", raw_body)},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "received", "event_id": event["id"]}


def test_event_payload_shape_is_correct():
    event = build_test_payment_event()

    assert event["entity"] == "event"
    assert event["account_id"] == "acc_test_demo"
    assert event["event"] == "payment.captured"
    assert event["contains"] == ["payment"]
    assert event["payload"]["payment"]["entity"] == {
        "id": event["payload"]["payment"]["entity"]["id"],
        "amount": 50000,
        "currency": "INR",
        "status": "captured",
    }
    assert event["id"].startswith("evt_test_")
    assert isinstance(event["created_at"], int)


def test_missing_signature_is_rejected():
    event = build_test_payment_event()
    raw_body = json.dumps(event).encode()

    response = client.post("/webhook/razorpay-event", content=raw_body)

    assert response.status_code == 400
    assert response.json() == {"status": "invalid_signature"}


def test_malformed_json_is_rejected():
    raw_body = b"{malformed"

    response = client.post(
        "/webhook/razorpay-event",
        content=raw_body,
        headers={"X-Razorpay-Signature": sign_payload("test-secret", raw_body)},
    )

    assert response.status_code == 400
    assert response.json() == {"status": "invalid_payload"}


def test_missing_event_id_is_rejected():
    raw_body = json.dumps({"entity": "event"}).encode()

    response = client.post(
        "/webhook/razorpay-event",
        content=raw_body,
        headers={"X-Razorpay-Signature": sign_payload("test-secret", raw_body)},
    )

    assert response.status_code == 400
    assert response.json() == {"status": "missing_event_id"}


def test_tampered_signature_is_rejected_and_counted():
    before = client.get("/metrics").text
    before_count = _metric_value(
        before, "razorpay_webhook_signature_failures_total"
    )
    event = build_test_payment_event()
    raw_body = json.dumps(event).encode()
    signature = sign_payload("test-secret", raw_body)
    tampered = ("0" if signature[0] != "0" else "1") + signature[1:]

    response = client.post(
        "/webhook/razorpay-event",
        content=raw_body,
        headers={"X-Razorpay-Signature": tampered},
    )

    after_count = _metric_value(
        client.get("/metrics").text, "razorpay_webhook_signature_failures_total"
    )
    assert response.status_code == 400
    assert response.json() == {"status": "invalid_signature"}
    assert after_count - before_count == 1


def test_duplicate_is_ignored_without_reprocessing(monkeypatch):
    event = build_test_payment_event()
    raw_body = json.dumps(event).encode()
    signature = sign_payload("test-secret", raw_body)
    original_helper = app_module._simulate_razorpay_processing
    calls = 0

    async def spy_helper():
        nonlocal calls
        calls += 1
        return await original_helper()

    monkeypatch.setattr(app_module, "_simulate_razorpay_processing", spy_helper)
    first = client.post(
        "/webhook/razorpay-event",
        content=raw_body,
        headers={"X-Razorpay-Signature": signature},
    )
    second = client.post(
        "/webhook/razorpay-event",
        content=raw_body,
        headers={"X-Razorpay-Signature": signature},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == {
        "status": "duplicate_ignored",
        "event_id": event["id"],
    }
    assert calls == 1

    metrics = client.get("/metrics").text
    assert _metric_value(metrics, "razorpay_webhook_duplicate_events_total") >= 1


def test_processed_counters_increment_for_each_result():
    event = build_test_payment_event()
    raw_body = json.dumps(event).encode()
    valid_signature = sign_payload("test-secret", raw_body)
    before = client.get("/metrics").text
    accepted_before = _metric_value(
        before, "razorpay_webhook_processed_total", '{result="accepted"}'
    )
    rejected_before = _metric_value(
        before, "razorpay_webhook_processed_total", '{result="rejected_signature"}'
    )
    duplicate_before = _metric_value(
        before, "razorpay_webhook_processed_total", '{result="duplicate"}'
    )

    client.post(
        "/webhook/razorpay-event",
        content=raw_body,
        headers={"X-Razorpay-Signature": valid_signature},
    )
    client.post(
        "/webhook/razorpay-event",
        content=raw_body,
        headers={"X-Razorpay-Signature": "0" * 64},
    )
    client.post(
        "/webhook/razorpay-event",
        content=raw_body,
        headers={"X-Razorpay-Signature": valid_signature},
    )

    after = client.get("/metrics").text
    assert _metric_value(after, "razorpay_webhook_processed_total", '{result="accepted"}') - accepted_before == 1
    assert _metric_value(after, "razorpay_webhook_processed_total", '{result="rejected_signature"}') - rejected_before == 1
    assert _metric_value(after, "razorpay_webhook_processed_total", '{result="duplicate"}') - duplicate_before == 1


def test_demo_variants_and_unknown_variant():
    valid = client.post("/simulate/razorpay-webhook?variant=valid")
    tampered = client.post("/simulate/razorpay-webhook?variant=tampered")
    duplicate = client.post("/simulate/razorpay-webhook?variant=duplicate")
    unknown = client.post("/simulate/razorpay-webhook?variant=other")

    assert valid.status_code == 200
    assert valid.json()["result"]["status"] == "received"
    assert tampered.status_code == 200
    assert tampered.json()["result"] == {"status": "invalid_signature"}
    assert duplicate.status_code == 200
    assert duplicate.json()["result"]["status"] == "duplicate_ignored"
    assert duplicate.json()["event_id"] == valid.json()["event_id"]
    assert unknown.status_code == 400
    for response in (valid, tampered, duplicate):
        assert "test-secret" not in response.text


def test_seen_event_ids_are_capped():
    for event_number in range(app_module.MAX_SEEN_EVENTS + 1):
        event = build_test_payment_event()
        event["id"] = f"evt_{event_number}"
        raw_body = json.dumps(event).encode()
        response = client.post(
            "/webhook/razorpay-event",
            content=raw_body,
            headers={"X-Razorpay-Signature": sign_payload("test-secret", raw_body)},
        )
        assert response.status_code == 200

    assert len(app_module._seen_razorpay_event_ids) == app_module.MAX_SEEN_EVENTS
    assert "evt_0" not in app_module._seen_razorpay_event_ids