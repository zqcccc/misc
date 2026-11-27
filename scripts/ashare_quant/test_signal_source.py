import json
import os
import tempfile
import unittest

from scripts.ashare_quant.signal_service import (
    SignalDataError,
    format_feishu_message,
    load_final_backtest_position,
    validate_signal_date_consistency,
)


def make_payload(date="2026-09-02", regime=False, holdings=None, drop=None):
    """构造合成回测交付物; cash_weight 对缺 weight 的持仓容错, 保证 fixture 本身可用,
    由被测函数 (而非 fixture) 抛出 SignalDataError。"""
    holdings = holdings if holdings is not None else [
        {"symbol": "600519.SS", "name": "贵州茅台", "shares": 500, "price": 1500.0, "weight": 0.3,
         "value": 750000.0}
    ]
    entry = {
        "date": date,
        "holdings": holdings,
        "cash_weight": 1.0 - sum(h.get("weight", 0) for h in holdings),
        "regime_healthy": regime,
    }
    if drop:
        entry.pop(drop)
    prev = {
        "date": "2026-09-01",
        "holdings": [dict(h) for h in holdings],
        "cash_weight": entry["cash_weight"],
        "regime_healthy": regime,
    }
    return {
        "full_sample_top3": {
            "recent_positions": [prev, entry],
        }
    }


def make_sig(date="2026-09-02", regime=True, top_picks=None, position_history=None):
    return {
        "date": date,
        "regime_healthy": regime,
        "top_picks": top_picks if top_picks is not None else ["600519.SS"],
        "cash_weight": 0.7,
        "benchmark_close": 4.0,
        "benchmark_ma20": 3.9,
        "benchmark_ma60": 3.8,
        "picks_detail": [{"symbol": "600519.SS", "name": "贵州茅台", "shares": 500,
                          "price": 1500.0, "weight": 0.3}],
        "position_history": position_history if position_history is not None else {
            "2026-09-01": {"symbols": ["600519.SS"], "regime_healthy": True},
            "2026-09-02": {"symbols": ["600519.SS"], "regime_healthy": True},
        },
    }


class TempFileCase(unittest.TestCase):
    def setUp(self):
        os.makedirs("temp", exist_ok=True)
        self._tmp = tempfile.TemporaryDirectory(dir="temp")
        self.addCleanup(self._tmp.cleanup)

    def write_payload(self, payload, raw=None):
        path = os.path.join(self._tmp.name, "ashare_strategy_backtest.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw if raw is not None else json.dumps(payload, ensure_ascii=False))
        return path


class TestLoadFinalBacktestPosition(TempFileCase):
    def test_valid_payload(self):
        pos = load_final_backtest_position(self.write_payload(make_payload()))
        self.assertEqual(pos["date"], "2026-09-02")
        self.assertFalse(pos["regime_healthy"])
        self.assertEqual(len(pos["holdings"]), 1)
        self.assertEqual(pos["position_history"]["2026-09-01"]["symbols"], ["600519.SS"])
        self.assertEqual(pos["position_history"]["2026-09-02"]["regime_healthy"], False)

    def test_missing_file_fails_closed(self):
        with self.assertRaises(SignalDataError):
            load_final_backtest_position(os.path.join(self._tmp.name, "missing.json"))

    def test_missing_regime_field_fails_closed(self):
        path = self.write_payload(make_payload(drop="regime_healthy"))
        with self.assertRaises(SignalDataError):
            load_final_backtest_position(path)

    def test_missing_date_fails_closed(self):
        path = self.write_payload(make_payload(drop="date"))
        with self.assertRaises(SignalDataError):
            load_final_backtest_position(path)

    def test_holding_missing_weight_fails_closed(self):
        bad = [{"symbol": "600519.SS", "name": "贵州茅台", "shares": 500, "price": 1500.0}]
        path = self.write_payload(make_payload(holdings=bad))
        with self.assertRaises(SignalDataError):
            load_final_backtest_position(path)

    def test_empty_recent_positions_fails_closed(self):
        path = self.write_payload({"full_sample_top3": {"recent_positions": []}})
        with self.assertRaises(SignalDataError):
            load_final_backtest_position(path)

    def test_corrupted_json_fails_closed(self):
        path = self.write_payload(None, raw="{not valid json")
        with self.assertRaises(SignalDataError):
            load_final_backtest_position(path)


class TestSignalDateConsistency(unittest.TestCase):
    def test_same_date_passes(self):
        self.assertIsNone(validate_signal_date_consistency("2026-09-02", "2026-09-02"))

    def test_mismatch_fails_closed(self):
        with self.assertRaises(SignalDataError):
            validate_signal_date_consistency("2026-09-02", "2026-09-03")

    def test_mismatch_message_names_both_dates(self):
        with self.assertRaises(SignalDataError) as ctx:
            validate_signal_date_consistency("2026-09-02", "2026-09-03")
        self.assertIn("2026-09-02", str(ctx.exception))
        self.assertIn("2026-09-03", str(ctx.exception))


class TestChangeDetection(unittest.TestCase):
    def test_first_run_pushes(self):
        need = format_feishu_message(make_sig(), {"last_signal_date": None})[2]
        self.assertTrue(need)

    def test_already_notified_date_suppressed(self):
        need = format_feishu_message(make_sig(), {"last_signal_date": "2026-09-02"})[2]
        self.assertFalse(need)

    def test_cursor_outside_window_pushes(self):
        need = format_feishu_message(make_sig(), {"last_signal_date": "2026-08-01"})[2]
        self.assertTrue(need)

    def test_same_state_as_cursor_suppressed(self):
        need = format_feishu_message(make_sig(), {"last_signal_date": "2026-09-01"})[2]
        self.assertFalse(need)

    def test_changed_holdings_push(self):
        sig = make_sig(top_picks=["300750.SZ"])
        need = format_feishu_message(sig, {"last_signal_date": "2026-09-01"})[2]
        self.assertTrue(need)

    def test_changed_regime_push(self):
        sig = make_sig(regime=False)
        need = format_feishu_message(sig, {"last_signal_date": "2026-09-01"})[2]
        self.assertTrue(need)

    def test_unhealthy_with_residual_holdings_lists_them(self):
        title, msg, need = format_feishu_message(
            make_sig(regime=False), {"last_signal_date": "2026-09-01"}
        )
        self.assertTrue(need)
        self.assertIn("待调仓/止损处置", msg)


if __name__ == "__main__":
    unittest.main()
