import json
import logging
from datetime import datetime, timezone
from typing import Any


class AuditLogger:
    def __init__(self, name: str = "clawwork.audit") -> None:
        self._logger = logging.getLogger(name)

    def event(self, event_type: str, **payload: Any) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            **payload,
        }
        self._logger.info(json.dumps(record, ensure_ascii=False, sort_keys=True))
