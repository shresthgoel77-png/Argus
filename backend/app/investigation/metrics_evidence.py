from sqlalchemy.orm import Session
from app.models import Incident, Evidence
from app.investigation.window import determine_window
from app.observability.promql import ERROR_RATE_QUERY, LATENCY_P95_QUERY, WEBHOOK_FAILURE_QUERY
from app.observability.prometheus_client import range_query, PrometheusUnavailableError
from app.detection import thresholds

def collect_metrics_evidence(incident: Incident, db_session: Session) -> list[Evidence]:
    start, end = determine_window(incident)
    
    signals = [
        ("error_rate", ERROR_RATE_QUERY),
        ("latency_p95", LATENCY_P95_QUERY),
        ("webhook_failure", WEBHOOK_FAILURE_QUERY),
    ]
    
    evidence_list = []
    
    for signal_name, query_template in signals:
        query = query_template.format(service=incident.service, window=thresholds.DETECTION_WINDOW)
        
        try:
            results = range_query(query, start, end, step="15s")
            
            datapoints = []
            peak_value = 0.0
            
            if results and len(results) > 0:
                values = results[0].get("values", [])
                for val in values:
                    if len(val) >= 2:
                        ts, v_str = val[0], val[1]
                        try:
                            v_float = float(v_str)
                            if str(v_float) != "nan":
                                datapoints.append([ts, v_float])
                                peak_value = max(peak_value, v_float)
                        except ValueError:
                            pass
            
            content = {
                "signal": signal_name,
                "query": query,
                "window": {
                    "start": start.isoformat(),
                    "end": end.isoformat()
                },
                "datapoints": datapoints,
                "peak_value": peak_value
            }
            
            ev = Evidence(
                incident_id=incident.id,
                category="observed_fact",
                content=content
            )
            evidence_list.append(ev)
            
        except PrometheusUnavailableError as e:
            ev = Evidence(
                incident_id=incident.id,
                category="collection_error",
                content={"error": str(e)}
            )
            evidence_list.append(ev)
            
    for ev in evidence_list:
        db_session.add(ev)
    db_session.commit()
    
    for ev in evidence_list:
        db_session.refresh(ev)
        
    return evidence_list
