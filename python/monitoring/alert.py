"""
alert.py — 3-level alert system: WARNING / RISK / CRITICAL

Ghi ra file log. Extension sau có thể thêm Telegram / email hook.
"""

import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

SEVERITY_WARNING  = "WARNING"
SEVERITY_RISK     = "RISK"
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_NORMAL   = "NORMAL"


def send_alert(
    severity: str,
    strategy: str,
    message: str,
    log_dir: str = "logs",
) -> None:
    """
    Ghi alert ra file và stdout.

    Args:
        severity: WARNING | RISK | CRITICAL | NORMAL
        strategy: tên strategy
        message:  nội dung alert
        log_dir:  thư mục chứa monitoring_alert.log
    """
    ts   = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{severity:<8}] [{strategy}] {message}"

    Path(log_dir).mkdir(exist_ok=True)
    log_path = Path(log_dir) / "monitoring_alert.log"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

    if severity == SEVERITY_CRITICAL:
        log.critical(line)
    elif severity == SEVERITY_RISK:
        log.warning(line)
    elif severity == SEVERITY_WARNING:
        log.warning(line)
    else:
        log.info(line)
