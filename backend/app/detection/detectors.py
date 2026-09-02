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

def detect_razorpay_tampering(service: str) -> dict:
    """Detects tampered signatures or duplicated events from Razorpay."""
    sig_query = f'increase(razorpay_webhook_signature_failures_total{{job="{service}"}}[{thresholds.DETECTION_WINDOW}])'
    dup_query = f'increase(razorpay_webhook_duplicate_events_total{{job="{service}"}}[{thresholds.DETECTION_WINDOW}])'
    
    firing = False
    max_val = 0.0
    active_query = sig_query
    
    for q in [sig_query, dup_query]:
        res = instant_query(q)
        if res and len(res) > 0:
            val_str = res[0].get("value", [0, "0"])[1]
            try:
                val = float(val_str)
                if str(val) != "nan" and val > 0.5:
                    firing = True
                    if val > max_val:
                        max_val = val
                        active_query = q
            except ValueError:
                pass

    severity = "high" if firing else None

    return {
        "firing": firing,
        "type": "webhook_failure",
        "service": service,
        "severity": severity,
        "value": max_val,
        "query": active_query,
        "window": thresholds.DETECTION_WINDOW
    }
