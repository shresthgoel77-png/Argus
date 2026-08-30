import json
from app.observability.prometheus_client import instant_query
from app.detection import thresholds
from app.observability.promql import ERROR_RATE_QUERY, LATENCY_P95_QUERY, WEBHOOK_FAILURE_QUERY

def detect_high_error_rate(service: str) -> dict:
    query = ERROR_RATE_QUERY.format(service=service, window=thresholds.DETECTION_WINDOW)
    
    res = instant_query(query)
    value = 0.0
    if res and len(res) > 0:
        val_str = res[0].get("value", [0, "0"])[1]
        try:
            val_float = float(val_str)
            if str(val_float) != "nan":
                value = val_float
        except ValueError:
            pass

    firing = value > thresholds.ERROR_RATE_MEDIUM
    severity = None
    if firing:
        severity = "high" if value > thresholds.ERROR_RATE_HIGH else "medium"

    return {
        "firing": firing,
        "type": "high_error_rate",
        "service": service,
        "severity": severity,
        "value": value,
        "query": query,
        "window": thresholds.DETECTION_WINDOW
    }


def detect_high_latency(service: str) -> dict:
    query = LATENCY_P95_QUERY.format(service=service, window=thresholds.DETECTION_WINDOW)
    
    res = instant_query(query)
    value = 0.0
    if res and len(res) > 0:
        val_str = res[0].get("value", [0, "0"])[1]
        try:
            val_float = float(val_str)
            if str(val_float) != "nan":
                value = val_float
        except ValueError:
            pass

    firing = value > thresholds.LATENCY_P95_MEDIUM_MS
    severity = None
    if firing:
        severity = "high" if value > thresholds.LATENCY_P95_HIGH_MS else "medium"

    return {
        "firing": firing,
        "type": "high_latency",
        "service": service,
        "severity": severity,
        "value": value,
        "query": query,
        "window": thresholds.DETECTION_WINDOW
    }


def detect_webhook_failure(service: str) -> dict:
    query = WEBHOOK_FAILURE_QUERY.format(service=service, window=thresholds.DETECTION_WINDOW)
    
    res = instant_query(query)
    value = 0.0
    if res and len(res) > 0:
        val_str = res[0].get("value", [0, "0"])[1]
        try:
            val_float = float(val_str)
            if str(val_float) != "nan":
                value = val_float
        except ValueError:
            pass

    firing = value > thresholds.WEBHOOK_FAILURE_MEDIUM
    severity = None
    if firing:
        severity = "high" if value > thresholds.WEBHOOK_FAILURE_HIGH else "medium"

    return {
        "firing": firing,
        "type": "webhook_failure",
        "service": service,
        "severity": severity,
        "value": value,
        "query": query,
        "window": thresholds.DETECTION_WINDOW
    }
