"""
MT5 connector module — Python <-> MetaTrader 5 interface.

Yêu cầu: pip install MetaTrader5
MT5 terminal phải đang chạy và đăng nhập trước khi gọi.
"""

import MetaTrader5 as mt5
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AccountInfo:
    login: int
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    currency: str


@dataclass
class SymbolInfo:
    name: str
    bid: float
    ask: float
    spread: int          # points
    volume_min: float
    volume_max: float
    volume_step: float
    trade_stops_level: int
    point: float
    digits: int
    contract_size: float


@dataclass
class MT5ConnectionConfig:
    path: str = ""          # path to terminal64.exe, empty = auto-detect
    login: int = 0          # 0 = dùng account đang đăng nhập
    password: str = ""
    server: str = ""
    timeout: int = 60000    # ms


# ---------------------------------------------------------------------------
# MT5Connector
# ---------------------------------------------------------------------------

class MT5Connector:
    """
    Wrapper quản lý kết nối Python <-> MT5.
    Dùng context manager để đảm bảo shutdown đúng cách.
    """

    def __init__(self, config: Optional[MT5ConnectionConfig] = None):
        self.config = config or MT5ConnectionConfig()
        self._connected = False

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False     # không suppress exception

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Khởi tạo kết nối MT5. Raise nếu fail."""
        kwargs = {}
        if self.config.path:
            kwargs["path"] = self.config.path
        if self.config.login:
            kwargs["login"] = self.config.login
            kwargs["password"] = self.config.password
            kwargs["server"] = self.config.server
        kwargs["timeout"] = self.config.timeout

        ok = mt5.initialize(**kwargs)
        if not ok:
            err = mt5.last_error()
            raise ConnectionError(f"MT5 initialize failed: {err}")

        self._connected = True
        info = mt5.terminal_info()
        logger.info(f"MT5 connected: build={info.build}, community={info.community_account}")
        return True

    def disconnect(self):
        if self._connected:
            mt5.shutdown()
            self._connected = False
            logger.info("MT5 disconnected")

    def _require_connected(self):
        if not self._connected:
            raise RuntimeError("MT5 chưa kết nối. Gọi connect() trước.")

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    def get_account_info(self) -> AccountInfo:
        self._require_connected()
        info = mt5.account_info()
        if info is None:
            raise RuntimeError(f"Không lấy được account info: {mt5.last_error()}")
        return AccountInfo(
            login=info.login,
            server=info.server,
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.margin_free,
            margin_level=info.margin_level,
            currency=info.currency,
        )

    # ------------------------------------------------------------------
    # Symbol
    # ------------------------------------------------------------------

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        self._require_connected()
        info = mt5.symbol_info(symbol)
        if info is None:
            raise ValueError(f"Symbol không tồn tại hoặc không select: {symbol}")
        # Đảm bảo symbol visible trong Market Watch
        if not info.visible:
            mt5.symbol_select(symbol, True)
        return SymbolInfo(
            name=info.name,
            bid=info.bid,
            ask=info.ask,
            spread=info.spread,
            volume_min=info.volume_min,
            volume_max=info.volume_max,
            volume_step=info.volume_step,
            trade_stops_level=info.trade_stops_level,
            point=info.point,
            digits=info.digits,
            contract_size=info.trade_contract_size,
        )

    def get_spread_points(self, symbol: str) -> int:
        return self.get_symbol_info(symbol).spread

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    def get_rates(
        self,
        symbol: str,
        timeframe: int,
        count: int = 500,
        from_date: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Lấy OHLCV bars.

        Args:
            timeframe: mt5.TIMEFRAME_* constant
            count: số bar gần nhất (nếu from_date = None)
            from_date: lấy từ ngày này nếu cần range cụ thể
        """
        self._require_connected()

        if from_date:
            rates = mt5.copy_rates_from(symbol, timeframe, from_date, count)
        else:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)

        if rates is None or len(rates) == 0:
            raise RuntimeError(f"Không lấy được rates {symbol}: {mt5.last_error()}")

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={
            "time": "timestamp",
            "open": "open", "high": "high",
            "low": "low", "close": "close",
            "tick_volume": "volume",
        })
        return df[["timestamp", "open", "high", "low", "close", "volume", "spread"]]

    # ------------------------------------------------------------------
    # Trade history (dùng cho monitoring agent)
    # ------------------------------------------------------------------

    def get_closed_deals(
        self,
        from_date: datetime,
        to_date: datetime,
        magic: Optional[int] = None,
        symbol: Optional[str] = None,
    ) -> pd.DataFrame:
        """Lấy lịch sử deals đã đóng."""
        self._require_connected()

        deals = mt5.history_deals_get(from_date, to_date)
        if deals is None:
            return pd.DataFrame()

        df = pd.DataFrame([d._asdict() for d in deals])
        if df.empty:
            return df

        df["time"] = pd.to_datetime(df["time"], unit="s")

        # Filter theo magic number
        if magic is not None and "magic" in df.columns:
            df = df[df["magic"] == magic]

        # Filter theo symbol
        if symbol is not None and "symbol" in df.columns:
            df = df[df["symbol"] == symbol]

        return df

    def get_open_positions(
        self,
        magic: Optional[int] = None,
        symbol: Optional[str] = None,
    ) -> pd.DataFrame:
        """Lấy các lệnh đang mở."""
        self._require_connected()

        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()

        if not positions:
            return pd.DataFrame()

        df = pd.DataFrame([p._asdict() for p in positions])

        if magic is not None and "magic" in df.columns:
            df = df[df["magic"] == magic]

        return df

    # ------------------------------------------------------------------
    # Portfolio state (đọc từ Global Variables)
    # ------------------------------------------------------------------

    def gv_get(self, name: str, default: float = 0.0) -> float:
        """Đọc MT5 Global Variable."""
        self._require_connected()
        if mt5.global_variable_exists(name):
            return mt5.global_variable_get(name)
        return default

    def gv_set(self, name: str, value: float) -> bool:
        """Ghi MT5 Global Variable."""
        self._require_connected()
        return mt5.global_variable_set(name, value)

    def get_portfolio_state(self, magic_base: int) -> dict:
        """Đọc trạng thái portfolio từ Global Variables do EA ghi."""
        prefix = f"QT_{magic_base}"
        return {
            "total_open_risk":  self.gv_get(f"{prefix}_TOTAL_RISK"),
            "daily_pl_pct":     self.gv_get(f"{prefix}_DAILY_PL"),
            "current_dd_pct":   self.gv_get(f"{prefix}_DD"),
            "open_positions":   int(self.gv_get(f"{prefix}_OPEN_COUNT")),
            "last_update_ts":   self.gv_get(f"{prefix}_TS"),
        }

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> dict:
        """Kiểm tra MT5 đang chạy và kết nối bình thường."""
        try:
            self._require_connected()
            info = mt5.terminal_info()
            acc = self.get_account_info()
            return {
                "ok": True,
                "build": info.build,
                "connected": info.connected,
                "trade_allowed": info.trade_allowed,
                "balance": acc.balance,
                "equity": acc.equity,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def get_connector(mt5_paths: dict) -> MT5Connector:
    """Tạo connector từ config yaml."""
    config = MT5ConnectionConfig(
        path=mt5_paths.get("terminal_exe", ""),
        login=mt5_paths.get("login", 0),
        password=mt5_paths.get("password", ""),
        server=mt5_paths.get("server", ""),
    )
    return MT5Connector(config)


# ---------------------------------------------------------------------------
# TIMEFRAME constants (re-export để code khác không import mt5 trực tiếp)
# ---------------------------------------------------------------------------

TIMEFRAME = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
    "W1":  mt5.TIMEFRAME_W1,
}
