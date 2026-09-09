from decimal import Decimal
from datetime import datetime, date
from uuid import UUID
from typing import Any

def serialize_for_api(obj: Any) -> Any:
    """Recursively converts Decimal, datetime, and UUID values into JSON primitives."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: serialize_for_api(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_api(item) for item in obj]
    elif isinstance(obj, tuple):
        return [serialize_for_api(item) for item in obj]
    return obj
