import os
import datetime
from app.models import Incident

def determine_window(incident: Incident) -> tuple[datetime.datetime, datetime.datetime]:
    lookback = int(os.getenv("INVESTIGATION_LOOKBACK_MINUTES", "10"))
    lookforward = int(os.getenv("INVESTIGATION_LOOKFORWARD_MINUTES", "1"))
    
    dt = incident.timestamp.replace(tzinfo=datetime.timezone.utc)
    start = dt - datetime.timedelta(minutes=lookback)
    
    now = datetime.datetime.now(datetime.timezone.utc)
    end_candidate = dt + datetime.timedelta(minutes=lookforward)
    end = min(now, end_candidate)
    
    return start, end
