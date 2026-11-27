import json
import os
import tempfile
import unittest
from datetime import date, timedelta

import pandas as pd

from scripts.ashare_quant.backtest_runner import (
    MAX_DATA_LAG_DAYS,
    atomic_write_json,
    derive_backtest_windows,
    first_date_on_or_after,
    last_date_before,
    subtract_months,
)
from scripts.ashare_quant.data_feed import resolve_end_date


def make_bm_df(last_date: str, first_date: str = "2019-01-01") -> pd.DataFrame:
    """构造合成基准行情 (工作日序列, 2019-01-01 起)。"""
    dates = pd.bdate_range(first_date, last_date)
    return pd.DataFrame({
        "date": dates,
        "close": [100.0 + 0.01 * i for i in range(len(dates))],
    })


class TestResolveEndDate(unittest.TestCase):
    def test_explicit_end_passthrough(self):
        """显式传入 end 时原样返回, 兼容旧调用。"""
        self.assertEqual(resolve_end_date("2020-01-01"), "2020-01-01")

    def test_default_is_runtime_next_day(self):
        """缺省取运行日次日 (yfinance end 为开区间, 才能覆盖运行当日K线)。"""
        self.assertEqual(resolve_end_date(today=date(2026, 9, 2)), "2026-09-03")
        self.assertEqual(resolve_end_date(), (date.today() + timedelta(days=1)).isoformat())


class TestSubtractMonths(unittest.TestCase):
    def test_half_year(self):
        self.assertEqual(subtract_months(date(2026, 9, 2), 6), date(2026, 3, 2))

    def test_day_clamp_to_month_end(self):
        self.assertEqual(subtract_months(date(2026, 3, 31), 1), date(2026, 2, 28))

    def test_leap_year_source(self):
        self.assertEqual(subtract_months(date(2024, 2, 29), 12), date(2023, 2, 28))

    def test_year_wrap(self):
        self.assertEqual(subtract_months(date(2025, 1, 15), 3), date(2024, 10, 15))


class TestFirstAndLastHelpers(unittest.TestCase):
    DATES = ["2024-01-02", "2024-01-03", "2024-01-04"]

    def test_first_on_or_after(self):
        self.assertEqual(first_date_on_or_after(self.DATES, "2024-01-03"), "2024-01-03")
        self.assertEqual(first_date_on_or_after(self.DATES, "2023-12-31"), "2024-01-02")

    def test_first_on_or_after_missing_raises(self):
        with self.assertRaises(ValueError):
            first_date_on_or_after(self.DATES, "2025-01-01")

    def test_last_before(self):
        self.assertEqual(last_date_before(self.DATES, "2024-01-04"), "2024-01-03")

    def test_last_before_missing_raises(self):
        with self.assertRaises(ValueError):
            last_date_before(self.DATES, "2024-01-02")


class TestDeriveBacktestWindows(unittest.TestCase):
    def test_matches_original_hardcoded_windows(self):
        """
        与旧硬编码口径对齐: 当基准行情止于 2026-09-02 时, 推导出的四段区间
        与旧版 (2019-01-01~2026-09-02 / 2019-01-01~2023-12-31 /
        2024-01-01~2026-02-27 / 2026-03-01~2026-09-02) 完全等效。
        旧硬编码起点 2026-03-01 为周日, 经 run_single_backtest 首个交易日对齐
        后实际起点即 2026-03-02 (周一), 与推导结果一致。
        """
        df = make_bm_df("2026-09-02")
        wins = derive_backtest_windows(df, today=date(2026, 9, 3))
        self.assertEqual(wins["full_start"], "2019-01-01")
        self.assertEqual(wins["full_end"], "2026-09-02")
        self.assertEqual(wins["in_sample_end"], "2023-12-31")
        self.assertEqual(wins["oos_start"], "2024-01-01")
        self.assertEqual(wins["oos_end"], "2026-02-27")
        self.assertEqual(wins["ultra_recent_start"], "2026-03-02")
        self.assertEqual(wins["ultra_recent_end"], "2026-09-02")
        self.assertEqual(wins["data_end"], "2026-09-02")

    def test_empty_benchmark_raises(self):
        with self.assertRaises(ValueError):
            derive_backtest_windows(pd.DataFrame(columns=["date", "close"]), today=date(2026, 9, 3))

    def test_unsorted_dates_raise(self):
        df = make_bm_df("2026-09-02").iloc[::-1].reset_index(drop=True)
        with self.assertRaises(ValueError):
            derive_backtest_windows(df, today=date(2026, 9, 3))

    def test_stale_benchmark_raises(self):
        """行情滞后超过容忍窗口 (14 个自然日) 时明确报错, 而非沿用旧截止日。"""
        df = make_bm_df("2026-08-01")  # 距 2026-09-03 已 33 天
        with self.assertRaises(ValueError):
            derive_backtest_windows(df, today=date(2026, 9, 3))

    def test_max_lag_boundary_allowed(self):
        df = make_bm_df("2026-08-20")  # 距 2026-09-03 恰好 MAX_DATA_LAG_DAYS 天
        self.assertEqual((date(2026, 9, 3) - date(2026, 8, 20)).days, MAX_DATA_LAG_DAYS)
        wins = derive_backtest_windows(df, today=date(2026, 9, 3))
        self.assertEqual(wins["data_end"], "2026-08-20")

    def test_future_benchmark_raises(self):
        df = make_bm_df("2026-09-10")  # 最新日期晚于运行日期
        with self.assertRaises(ValueError):
            derive_backtest_windows(df, today=date(2026, 9, 3))

    def test_empty_oos_window_raises(self):
        """基准止于 2024-06-30 时, 最新绝密段前推 6 个月吃掉整个样本外区间, 必须报错。"""
        df = make_bm_df("2024-06-30")
        with self.assertRaises(ValueError):
            derive_backtest_windows(df, today=date(2024, 7, 1))

    def test_benchmark_starting_after_full_sample_start_raises(self):
        df = make_bm_df("2026-09-02", first_date="2020-06-01")
        with self.assertRaises(ValueError):
            derive_backtest_windows(df, today=date(2026, 9, 3))


class TestAtomicWriteJson(unittest.TestCase):
    def setUp(self):
        os.makedirs("temp", exist_ok=True)
        self._tmp = tempfile.TemporaryDirectory(dir="temp")
        self.addCleanup(self._tmp.cleanup)
        self.target = os.path.join(self._tmp.name, "out.json")

    def _leftover_tmp_names(self):
        return [n for n in os.listdir(self._tmp.name) if ".tmp" in n]

    def test_success_writes_and_no_tmp_left(self):
        payload = {"a": 1, "b": ["中文", 2.5]}
        atomic_write_json(self.target, payload)
        with open(self.target, encoding="utf-8") as f:
            self.assertEqual(json.load(f), payload)
        self.assertEqual(self._leftover_tmp_names(), [])

    def test_overwrites_existing(self):
        with open(self.target, "w", encoding="utf-8") as f:
            f.write("old")
        atomic_write_json(self.target, {"new": True})
        with open(self.target, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"new": True})

    def test_failure_when_replace_fails_cleans_tmp(self):
        """目标路径被目录占用导致 os.replace 失败: 临时文件必须被清理并原样抛错。"""
        os.makedirs(self.target)
        with self.assertRaises(OSError):
            atomic_write_json(self.target, {"x": 1})
        self.assertEqual(self._leftover_tmp_names(), [])

    def test_failure_when_open_fails_leaves_nothing(self):
        bad_target = os.path.join(self._tmp.name, "missing_dir", "out.json")
        with self.assertRaises(OSError):
            atomic_write_json(bad_target, {"x": 1})
        self.assertEqual(os.listdir(self._tmp.name), [])


if __name__ == "__main__":
    unittest.main()
