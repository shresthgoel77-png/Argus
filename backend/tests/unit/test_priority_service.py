import pytest
from app.services.priority_service import compute_priority

@pytest.mark.parametrize("category,severity,expected", [
    # Info severity rule (info always maps to low, even if category is security)
    ("security", "info", "low"),
    ("quality", "info", "low"),
    ("performance", "info", "low"),
    
    # Standard mapping for non-security categories
    ("quality", "low", "low"),
    ("quality", "medium", "medium"),
    ("quality", "high", "high"),
    ("quality", "critical", "critical"),
    
    # Security category bump rule (one tier up, max critical)
    ("security", "low", "medium"),
    ("security", "medium", "high"),
    ("security", "high", "critical"),
    ("security", "critical", "critical"),
])
def test_compute_priority_table_driven(category, severity, expected):
    assert compute_priority(category=category, severity=severity) == expected
