from sqlalchemy.orm import Session
from app.models import Incident, Evidence
from app.investigation.window import determine_window
from app.observability.loki_client import query_range, LokiUnavailableError

def collect_logs_evidence(incident: Incident, db_session: Session) -> list[Evidence]:
    start, end = determine_window(incident)
    
    if incident.type == "webhook_failure":
        logql = '{job="' + incident.service + '"} |~ "(?i)(error|/webhook/payment-event)"'
    else:
        logql = '{job="' + incident.service + '"} |= "error"'
        
    evidence_list = []
    
    try:
        results = query_range(logql, start, end, limit=500) # query a bit more to sort closest 50
        
        incident_ts_ns = int(incident.timestamp.timestamp() * 1e9)
        results.sort(key=lambda x: abs(int(x["timestamp"]) - incident_ts_ns))
        matched_lines = results[:50]
        
        content = {
            "logql": logql,
            "window": {
                "start": start.isoformat(),
                "end": end.isoformat()
            },
            "matched_lines": matched_lines,
            "match_count": len(matched_lines)
        }
        
        ev = Evidence(
            incident_id=incident.id,
            category="observed_fact",
            content=content
        )
        evidence_list.append(ev)
        
    except LokiUnavailableError as e:
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
