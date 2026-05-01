"""
walk_forward.py — Walk-Forward Optimization fold generator và runner.
"""

import logging
from dataclasses import dataclass
from datetime import date
from dateutil.relativedelta import relativedelta

log = logging.getLogger(__name__)


@dataclass
class WFOFold:
    index: int
    train_from: str   # "YYYY.MM.DD"
    train_to: str
    test_from: str
    test_to: str

    def __repr__(self):
        return (f"Fold {self.index}: "
                f"IS [{self.train_from}→{self.train_to}] "
                f"OOS [{self.test_from}→{self.test_to}]")


def generate_wf_folds(
    start: date,
    end: date,
    train_months: int = 12,
    test_months: int = 3,
) -> list[WFOFold]:
    """
    Tạo danh sách WFO folds với rolling window.

    Ví dụ train=12m, test=3m:
      Fold 1: IS  2020-01→2020-12  OOS 2021-01→2021-03
      Fold 2: IS  2020-04→2021-03  OOS 2021-04→2021-06
      ...

    Args:
        start:        ngày bắt đầu toàn bộ data
        end:          ngày kết thúc toàn bộ data
        train_months: độ dài cửa sổ train (IS)
        test_months:  độ dài cửa sổ test (OOS)

    Returns:
        List[WFOFold]
    """
    folds = []
    cursor = start
    idx = 1

    while True:
        train_from = cursor
        train_to   = cursor + relativedelta(months=train_months)
        test_from  = train_to
        test_to    = test_from + relativedelta(months=test_months)

        if test_to > end:
            break

        folds.append(WFOFold(
            index=idx,
            train_from=train_from.strftime("%Y.%m.%d"),
            train_to=train_to.strftime("%Y.%m.%d"),
            test_from=test_from.strftime("%Y.%m.%d"),
            test_to=test_to.strftime("%Y.%m.%d"),
        ))
        cursor += relativedelta(months=test_months)
        idx += 1

    log.info(f"Generated {len(folds)} WFO folds "
             f"(train={train_months}m, test={test_months}m)")
    return folds


def run_walk_forward(runner, base_config: dict, folds: list[WFOFold]) -> list[dict]:
    """
    Chạy IS + OOS backtest cho từng fold.

    Args:
        runner:      MT5TesterRunner instance
        base_config: config dict cơ bản (thiếu from_date / to_date)
        folds:       list từ generate_wf_folds()

    Returns:
        list[dict] — mỗi dict chứa fold index + IS result + OOS result
    """
    results = []

    for fold in folds:
        log.info(f"[WFO] {fold}")

        # --- IS backtest ---
        is_config = {
            **base_config,
            "from_date": fold.train_from,
            "to_date":   fold.train_to,
        }
        is_result = runner.run_backtest(is_config)
        is_result["fold_type"] = "IS"

        # --- OOS backtest ---
        oos_config = {
            **base_config,
            "from_date": fold.test_from,
            "to_date":   fold.test_to,
        }
        oos_result = runner.run_backtest(oos_config)
        oos_result["fold_type"] = "OOS"

        results.append({
            "fold":  fold.index,
            "range": str(fold),
            "is":    is_result,
            "oos":   oos_result,
        })

    passed = sum(1 for r in results if r["oos"]["status"] == "OK")
    log.info(f"[WFO] Complete: {passed}/{len(folds)} OOS runs OK")
    return results


def summarize_wf_results(wf_results: list[dict]) -> dict:
    """
    Tổng hợp kết quả WFO ở mức cao.
    (metrics chi tiết cần parse từng trade_log riêng)
    """
    total  = len(wf_results)
    is_ok  = sum(1 for r in wf_results if r["is"]["status"]  == "OK")
    oos_ok = sum(1 for r in wf_results if r["oos"]["status"] == "OK")
    return {
        "total_folds": total,
        "is_ok":       is_ok,
        "oos_ok":      oos_ok,
        "oos_pass_rate": oos_ok / total if total > 0 else 0,
    }
