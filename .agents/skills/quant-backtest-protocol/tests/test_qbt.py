import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "qbt.py"
SPEC = importlib.util.spec_from_file_location("qbt", SCRIPT)
qbt = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qbt)


class QbtV2Tests(unittest.TestCase):
    def test_permutation_rejects_invalid_values_for_every_alias(self):
        bad = [None, True, False, "NaN", "0.99", float("nan"), float("inf"),
               -float("inf"), -0.01, 1.01, [], {}, 10**400]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "perm.json"
            for field in ("percentile_vs_random", "percentile", "p_value"):
                for value in bad:
                    with self.subTest(field=field, value=repr(value)):
                        path.write_text(json.dumps({field: value}))
                        self.assertIn("error", qbt.load_permutation_result(str(path)))
                for value in (0, 1, 0.94999, 0.95):
                    path.write_text(json.dumps({field: value}))
                    out = qbt.load_permutation_result(str(path))
                    self.assertNotIn("error", out)
                    self.assertEqual(out["percentile_vs_random"], 1-value if field == "p_value" else value)
            for obj in ({}, {"percentile": .99, "p_value": .5},
                        {"percentile_vs_random": .99, "percentile": "NaN"}):
                path.write_text(json.dumps(obj))
                self.assertIn("error", qbt.load_permutation_result(str(path)))
            # 别名只要求四位小数一致：一个存 4 位一个存 6 位是常见写法，不是矛盾
            path.write_text(json.dumps({"percentile": 0.9667, "p_value": 0.033333}))
            mixed = qbt.load_permutation_result(str(path))
            self.assertNotIn("error", mixed)
            self.assertEqual(mixed["percentile_vs_random"], 0.9667)
            # 但判读仍用未取整的原值，0.94999 不许被并成 0.95
            path.write_text(json.dumps({"percentile": 0.94999, "p_value": 0.05}))
            self.assertEqual(qbt.load_permutation_result(str(path))["percentile_vs_random"], 0.94999)

    def test_exploratory_report_has_no_gate_noise(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            idx = pd.date_range("2019-01-02", periods=400, freq="B")
            rng = np.random.default_rng(21)
            bench = rng.normal(0.0001, 0.006, len(idx))
            pd.DataFrame({"date": idx, "ret": 0.0008 + bench}).to_csv(root / "r.csv", index=False)
            pd.DataFrame({"date": idx, "ret": bench}).to_csv(root / "b.csv", index=False)
            out = root / "exp.json"
            subprocess.run([sys.executable, str(SCRIPT), "report", "--returns", str(root / "r.csv"),
                            "--bench", str(root / "b.csv"), "--exploratory", "--market", "us_stock",
                            "--out", str(out), "--iters", "100"], check=True, capture_output=True, text=True)
            rep = json.loads(out.read_text())
            self.assertEqual(rep["verdict_code"], "DIAGNOSTIC")
            # 探索诊断不跑置换/搜索调整层，缺失是正常的，不该混进失败列表
            self.assertFalse([f for f in rep["falsification_failures"]
                              if "random_portfolio" in f or "selection_adjustment" in f],
                             rep["falsification_failures"])

    def test_final_gate_rejects_invalid_internal_statistics(self):
        good = {"alpha_beta": {"ann_alpha": .1, "alpha_t": 3},
                "monte_carlo": {"prob_profit": .99},
                "random_portfolio": {"percentile_vs_random": .99},
                "selection_adjustment": {"PSR": .99}}
        self.assertEqual(qbt.validate_gate_statistics(good), [])
        for section, fields in good.items():
            for field in fields:
                for value in (None, float("nan"), float("inf"), True, "0.99"):
                    obj = json.loads(json.dumps(good))
                    obj[section][field] = value
                    self.assertTrue(qbt.validate_gate_statistics(obj), (section, field, value))
        good["selection_adjustment"] = {"DSR": 1.1}
        self.assertTrue(qbt.validate_gate_statistics(good))

    def test_registry_rejects_invalid_statistics_without_writing_cards(self):
        registry = SCRIPT.parents[4] / "quant_research" / "qr"
        source = registry.read_text()
        code = source.split("import json, sys, math\np, expected_role", 1)[1].split("\nPY", 1)[0]
        code = "import json, sys, math\np, expected_role" + code
        good = {"schema_version": 2, "stage": "candidate", "role": "alpha",
                "verdict_code": "PASS", "falsification_failures": [],
                "execution_check": {}, "data_provenance": {}, "window_consistency": {},
                "alpha_beta": {"ann_alpha": .1, "alpha_t": 3},
                "monte_carlo": {"prob_profit": .99},
                "random_portfolio": {"percentile_vs_random": .99},
                "selection_adjustment": {"PSR": .99}}
        with tempfile.TemporaryDirectory() as td:
            report = Path(td) / "report.json"
            for value, expected in ((.99, 0), (float("nan"), 1), (1.1, 1), (None, 1), (True, 1)):
                good["random_portfolio"]["percentile_vs_random"] = value
                report.write_text(json.dumps(good))
                proc = subprocess.run([sys.executable, "-c", code, str(report), "alpha"],
                                      capture_output=True, text=True)
                self.assertEqual(proc.returncode, expected, proc.stderr)

    def test_random_portfolio_requires_explicit_n_short(self):
        # 纯多策略配多空随机对照会把分位系统性抬高，所以不给静默默认值
        with self.assertRaises(SystemExit):
            qbt.require_n_short(None)
        self.assertEqual(qbt.require_n_short(0), 0)
        self.assertEqual(qbt.require_n_short(5), 5)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            idx = pd.date_range("2020-01-01", periods=200, freq="B")
            rng = np.random.default_rng(3)
            pd.DataFrame(rng.normal(0, 0.01, (len(idx), 6)),
                         index=idx, columns=list("abcdef")).to_csv(root / "panel.csv")
            cmd = [sys.executable, str(SCRIPT), "randomport", "--panel", str(root / "panel.csv"),
                   "--sharpe", "1.0", "--n-long", "3", "--iters", "20"]
            miss = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(miss.returncode, 0)
            self.assertIn("--n-short", miss.stderr)
            got = subprocess.run(cmd + ["--n-short", "0"], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(got.stdout)["n_short"], 0)

    def test_alpha_beta_verdict_requires_significance(self):
        idx = pd.date_range("2020-01-01", periods=600, freq="B", tz="UTC")
        rng = np.random.default_rng(11)
        bench = pd.Series(rng.normal(0.0002, 0.01, len(idx)), index=idx)
        # 噪音淹没的微弱正 alpha：符号为正但不显著，结论句不许说「策略本身有效」
        weak = pd.Series(0.00002 + 0.9 * bench.to_numpy() + rng.normal(0, 0.02, len(idx)), index=idx)
        out = qbt.alpha_beta(weak, bench, 252)
        self.assertGreater(out["ann_alpha"], 0)
        self.assertFalse(out["alpha_significant"])
        self.assertIn("不显著", out["verdict"])
        self.assertNotIn("策略本身有效", out["verdict"].split("：")[0])

    def _carrier_fixture(self, root, beta=1.0, edge=0.0003):
        idx = pd.date_range("2017-01-02", periods=1200, freq="B")
        rng = np.random.default_rng(5)
        inc = rng.normal(0.0002, 0.011, len(idx))
        car = edge + beta * inc + rng.normal(0, 0.0015, len(idx))
        pd.DataFrame({"date": idx, "ret": car}).to_csv(root / "car.csv", index=False)
        pd.DataFrame({"date": idx, "ret": inc}).to_csv(root / "inc.csv", index=False)
        pd.DataFrame({"date": idx, "ret": car - 0.00005}).to_csv(root / "car_stress.csv", index=False)
        (root / "risk.json").write_text(json.dumps({
            "margin_ratio": 0.12, "peak_drawdown_over_margin": 2.1, "min_capital": 1200000,
            "forced_liquidation_plan": "先卖货币ETF，T+0 到账", "roll_liquidity_evidence": "换月日盘口五档实测",
            "regulatory_tail": "限仓与保证金比例调整"}))
        (root / "exec.json").write_text(json.dumps({
            "information_time": "t-1 close", "decision_time": "after t-1 close",
            "execution_time": "t open", "pnl_start": "t open", "pnl_end": "t close",
            "price_field": "open", "timezone": "Asia/Shanghai",
            "pnl_start_not_before_execution": True, "validated": True}))
        raw = root / "raw.csv"
        raw.write_text("date,close\n2017-01-02,1\n")
        (root / "data.json").write_text(json.dumps({"sources": [{
            "provider": "test fixture", "retrieved_at": "2026-09-05T00:00:00Z",
            "url_or_query": "local", "raw_file": "raw.csv",
            "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(), "rows": 1,
            "start": "2017-01-02", "end": "2021-08-06", "timezone": "Asia/Shanghai",
            "adjustment": "none"}]}))

    def _run_carrier(self, root, out, extra=()):
        subprocess.run([sys.executable, str(SCRIPT), "carrier",
                        "--returns", str(root / "car.csv"), "--bench", str(root / "inc.csv"),
                        "--market", "cn_stock", "--carrier-risk", str(root / "risk.json"),
                        "--execution-manifest", str(root / "exec.json"),
                        "--data-manifest", str(root / "data.json"),
                        "--out", str(out), *extra], check=True, capture_output=True, text=True)
        return json.loads(out.read_text())

    def test_carrier_passes_only_with_matched_exposure_stress_and_risk(self):
        with tempfile.TemporaryDirectory() as td:
            root, out = Path(td), Path(td) / "v.json"
            self._carrier_fixture(root)

            # 缺压力档 → 不许 PASS
            miss = self._run_carrier(root, out)
            self.assertEqual(miss["verdict_code"], "FAIL")
            self.assertTrue(any("carrier_swap_stressed" in f for f in miss["falsification_failures"]))

            good = self._run_carrier(root, out, ["--carrier-stressed", str(root / "car_stress.csv")])
            self.assertEqual(good["verdict_code"], "PASS", good["falsification_failures"])
            self.assertEqual(good["role"], "execution")
            self.assertEqual(good["notes"], [])
            self.assertAlmostEqual(good["carrier_swap"]["beta_vs_incumbent"], 1.0, delta=0.03)

            # 载体风险少一项 → 立刻掉回 FAIL
            (root / "risk.json").write_text(json.dumps({
                "margin_ratio": 0.12, "peak_drawdown_over_margin": 2.1, "min_capital": 1200000,
                "forced_liquidation_plan": "", "roll_liquidity_evidence": "x", "regulatory_tail": "y"}))
            bad = self._run_carrier(root, out, ["--carrier-stressed", str(root / "car_stress.csv")])
            self.assertEqual(bad["verdict_code"], "FAIL")
            self.assertTrue(any("forced_liquidation_plan" in f for f in bad["falsification_failures"]))

    def test_carrier_flags_exposure_mismatch_and_rejects_negative_edge(self):
        with tempfile.TemporaryDirectory() as td:
            root, out = Path(td), Path(td) / "v.json"
            # 多拿 15% 敞口：原始净差被抬高，报告必须把这件事说出来
            self._carrier_fixture(root, beta=1.15)
            rep = self._run_carrier(root, out, ["--carrier-stressed", str(root / "car_stress.csv")])
            self.assertTrue(any("同暴露不成立" in n for n in rep["notes"]), rep["notes"])
            cs = rep["carrier_swap"]
            self.assertGreater(cs["net_diff_annual"], cs["exposure_adjusted_excess_annual"])

            # 换载体反而更贵：暴露调整后差额为负，必须判死
            self._carrier_fixture(root, beta=1.0, edge=-0.0003)
            neg = self._run_carrier(root, out, ["--carrier-stressed", str(root / "car_stress.csv")])
            self.assertEqual(neg["verdict_code"], "FAIL")
            self.assertTrue(any("≤ 0" in f for f in neg["falsification_failures"]))

    def test_control_shape_check_catches_long_only_vs_long_short_control(self):
        """B0002 那个真实事故的回归：纯多策略配多空中性对照，必须被判不同构。

        这条测试本身就是 B0007 要求的「反例」——一道给不出反例的检查等于没有检查。
        """
        idx = pd.date_range("2020-01-01", periods=500, freq="B")
        rng = np.random.default_rng(17)
        M = 30
        mkt = rng.normal(0.0003, 0.011, len(idx))
        panel = pd.DataFrame(
            {f"s{i}": mkt + rng.normal(0, 0.012, len(idx)) for i in range(M)}, index=idx)

        # 真策略：纯多（等权持有 5 只），beta ≈ 1
        long_only = panel.iloc[:, :5].mean(axis=1)

        # 对照 A：多空中性（--n-short 5，旧的默认值）→ beta ≈ 0，与真策略不同构
        bad = qbt.random_portfolio(panel, 5, 5, 1, 200, 1, 252, 1.0)
        got_bad = qbt.control_shape_check(long_only, panel, bad)
        self.assertFalse(got_bad["same_shape"], got_bad)
        self.assertIn("不是一种东西", got_bad["说人话"])

        # 对照 B：同样纯多（--n-short 0）→ beta ≈ 1，同构
        good = qbt.random_portfolio(panel, 5, 0, 1, 200, 1, 252, 1.0)
        got_good = qbt.control_shape_check(long_only, panel, good)
        self.assertTrue(got_good["same_shape"], got_good)

        # 两者的分位数差多少 —— 这就是当初 75.05% → 99.65% 的来源
        self.assertLess(good["null_beta_p50"] - bad["null_beta_p50"], 2.0)
        self.assertGreater(good["null_beta_p50"], 0.5)
        self.assertLess(abs(bad["null_beta_p50"]), 0.35)

    def test_max_drawdown_counts_the_initial_capital(self):
        """首日就亏掉的钱必须算进最大回撤（B0009）。

        反例（B0007 要求每道判读线都能举出会让它失败的输入）：
        首日 −50%、随后连涨的净值路径。不把期初本金放进路径的话，第一天就成了
        cummax 的起点，那 50% 永远看不见，最大回撤被报成 0 —— 一个亏一半开局的
        策略会以「零回撤」通过风险判读。
        """
        idx = pd.date_range("2020-01-01", periods=40, freq="B")
        crash_then_rally = pd.Series([-0.5] + [0.02] * 39, index=idx)
        self.assertAlmostEqual(
            qbt.perf_stats(crash_then_rally, 252)["max_drawdown"], 0.5, places=6)

        # 同一个坑在 carrier 的 mdd 里也有一份
        rng = np.random.default_rng(3)
        inc = pd.Series(rng.normal(0.0005, 0.01, 120), index=pd.date_range(
            "2020-01-01", periods=120, freq="B"))
        car = inc.copy()
        car.iloc[0] = -0.5
        got = qbt.carrier_swap(car, inc, 252)
        self.assertLess(got["max_drawdown_carrier"], -0.45)

        # 正常路径不受影响：全程上涨的最大回撤仍是 0
        up = pd.Series([0.001] * 40, index=idx)
        self.assertAlmostEqual(qbt.perf_stats(up, 252)["max_drawdown"], 0.0, places=6)

    def test_alpha_beta_reports_hac_standard_error(self):
        idx = pd.date_range("2020-01-01", periods=400, freq="B", tz="UTC")
        rng = np.random.default_rng(7)
        bench = pd.Series(rng.normal(0.0002, 0.01, len(idx)), index=idx)
        # 自相关残差让 HAC 与普通独立同分布标准误的区别有现实意义。
        eps = np.zeros(len(idx))
        shocks = rng.normal(0, 0.004, len(idx))
        for i in range(1, len(idx)):
            eps[i] = 0.7 * eps[i - 1] + shocks[i]
        strategy = pd.Series(0.0005 + 0.4 * bench.to_numpy() + eps, index=idx)
        out = qbt.alpha_beta(strategy, bench, 252)
        self.assertEqual(out["alpha_se_method"], "Newey-West/HAC")
        self.assertGreaterEqual(out["nw_lags"], 1)
        self.assertIn("alpha_t", out)

    def test_single_spec_uses_psr_instead_of_fake_dsr(self):
        idx = pd.date_range("2020-01-01", periods=300, freq="B", tz="UTC")
        rng = np.random.default_rng(8)
        r = pd.Series(rng.normal(0.0005, 0.01, len(idx)), index=idx)
        out = qbt.probabilistic_sharpe(r, 252)
        self.assertEqual(out["method"], "PSR-single-spec")
        self.assertIn("PSR", out)

    def test_manifests_fail_closed(self):
        self.assertIn("error", qbt.validate_execution_manifest(None))
        self.assertIn("error", qbt.validate_data_manifest(None))

    def test_strict_report_rejects_missing_layers_but_exploratory_is_diagnostic(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dates = pd.date_range("2022-01-03", periods=120, freq="B")
            rng = np.random.default_rng(9)
            ret = rng.normal(0.0005, 0.01, len(dates))
            bench = rng.normal(0.0002, 0.009, len(dates))
            pd.DataFrame({"date": dates, "ret": ret}).to_csv(root / "r.csv", index=False)
            pd.DataFrame({"date": dates, "ret": bench}).to_csv(root / "b.csv", index=False)

            strict_out = root / "strict.json"
            subprocess.run([
                sys.executable, str(SCRIPT), "report", "--returns", str(root / "r.csv"),
                "--bench", str(root / "b.csv"), "--single-spec", "--market", "us_stock",
                "--out", str(strict_out), "--iters", "100",
            ], check=True, capture_output=True, text=True)
            strict = json.loads(strict_out.read_text())
            self.assertEqual(strict["verdict_code"], "FAIL")
            self.assertTrue(any("execution_check" in x for x in strict["falsification_failures"]))
            self.assertTrue(any("data_provenance" in x for x in strict["falsification_failures"]))

            diag_out = root / "diag.json"
            subprocess.run([
                sys.executable, str(SCRIPT), "report", "--returns", str(root / "r.csv"),
                "--bench", str(root / "b.csv"), "--single-spec", "--market", "us_stock",
                "--exploratory", "--out", str(diag_out), "--iters", "100",
            ], check=True, capture_output=True, text=True)
            diag = json.loads(diag_out.read_text())
            self.assertEqual(diag["verdict_code"], "DIAGNOSTIC")

    def test_screen_stops_cost_eaten_ideas_before_any_backtest(self):
        # 用三张真实卡片的口径回放：成本闸应该在写代码之前就给出和最终裁决一致的方向
        h0011 = qbt.screen_edge_vs_cost(0.133, 216000, 5)      # 15m 全池每根换仓
        self.assertEqual(h0011["screen_verdict"], "STOP")
        self.assertLess(h0011["edge_cost_ratio"], 0.01)

        h0029 = qbt.screen_edge_vs_cost(0.29, 730, 5)          # 每日时段进出
        self.assertEqual(h0029["screen_verdict"], "STOP")

        h0003 = qbt.screen_edge_vs_cost(0.0625, 2, 5)          # 资金费收割，几乎不换手
        self.assertEqual(h0003["screen_verdict"], "GO")

        thin = qbt.screen_edge_vs_cost(0.069, 15, 20)          # 毛/成本 ≈ 2.3
        self.assertEqual(thin["screen_verdict"], "THIN")

    def test_screen_go_requires_surviving_stress_cost(self):
        # 毛/成本 = 3.0 刚好过线，但成本翻倍后只剩 1.5 倍——仍算 GO
        ok = qbt.screen_edge_vs_cost(0.03, 100, 1)
        self.assertEqual(ok["edge_cost_ratio"], 3.0)
        self.assertEqual(ok["screen_verdict"], "GO")
        # 持有成本（资金费/借券）不随压力倍数放大，但会压低基础比值
        with_funding = qbt.screen_edge_vs_cost(0.03, 100, 1, funding_annual=0.02)
        self.assertEqual(with_funding["screen_verdict"], "STOP")
        # 零成本口径不该被成本关拦下
        free = qbt.screen_edge_vs_cost(0.05, 0, 5)
        self.assertEqual(free["screen_verdict"], "GO")
        self.assertIsNone(free["edge_cost_ratio"])

    def test_data_manifest_rejects_forged_sha256(self):
        # 数据清单的全部价值在于「哈希对不上就过不了」，否则填个 64 位假串就能冒充溯源
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = root / "raw.csv"
            raw.write_text("date,close\n2019-01-02,1\n")
            src = {
                "provider": "test fixture", "retrieved_at": "2026-09-04T00:00:00Z",
                "url_or_query": "local test fixture", "raw_file": "raw.csv",
                "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(), "rows": 1,
                "start": "2019-01-02", "end": "2020-12-01", "timezone": "UTC",
                "adjustment": "none",
            }
            good = root / "good.json"
            good.write_text(json.dumps({"sources": [src]}))
            self.assertNotIn("error", qbt.validate_data_manifest(str(good)))

            forged = root / "forged.json"
            forged.write_text(json.dumps({"sources": [dict(src, sha256="b" * 64)]}))
            self.assertIn("SHA256", qbt.validate_data_manifest(str(forged))["error"])

            # 声称的原始文件不在，同样不能算溯源通过
            missing = root / "missing.json"
            missing.write_text(json.dumps({"sources": [dict(src, raw_file="nope.csv")]}))
            self.assertIn("raw_file", qbt.validate_data_manifest(str(missing))["error"])

            # 事后改了原始文件也必须失效
            raw.write_text("date,close\n2019-01-02,2\n")
            self.assertIn("SHA256", qbt.validate_data_manifest(str(good))["error"])

    def test_strict_report_can_pass_with_complete_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dates = pd.date_range("2019-01-02", periods=500, freq="B")
            rng = np.random.default_rng(10)
            bench = rng.normal(0.0001, 0.006, len(dates))
            ret = 0.0012 + 0.1 * bench + rng.normal(0, 0.002, len(dates))
            pd.DataFrame({"date": dates, "ret": ret}).to_csv(root / "r.csv", index=False)
            pd.DataFrame({"date": dates, "ret": bench}).to_csv(root / "b.csv", index=False)
            (root / "perm.json").write_text(json.dumps({"percentile_vs_random": 0.99}))
            (root / "execution.json").write_text(json.dumps({
                "information_time": "t-1 close", "decision_time": "after t-1 close",
                "execution_time": "t open", "pnl_start": "t open", "pnl_end": "t close",
                "price_field": "open", "timezone": "UTC",
                "pnl_start_not_before_execution": True, "validated": True,
            }))
            raw = root / "raw.csv"
            raw.write_text("date,close\n2019-01-02,1\n")
            raw_sha = hashlib.sha256(raw.read_bytes()).hexdigest()
            (root / "data.json").write_text(json.dumps({"sources": [{
                "provider": "test fixture", "retrieved_at": "2026-09-04T00:00:00Z",
                "url_or_query": "local test fixture", "raw_file": "raw.csv",
                "sha256": raw_sha, "rows": 1, "start": "2019-01-02",
                "end": "2020-12-01", "timezone": "UTC", "adjustment": "none",
            }]}))
            out_path = root / "pass.json"
            subprocess.run([
                sys.executable, str(SCRIPT), "report", "--returns", str(root / "r.csv"),
                "--bench", str(root / "b.csv"), "--single-spec", "--market", "us_stock",
                "--permutation-result", str(root / "perm.json"),
                "--execution-manifest", str(root / "execution.json"),
                "--data-manifest", str(root / "data.json"),
                "--out", str(out_path), "--iters", "300",
            ], check=True, capture_output=True, text=True)
            out = json.loads(out_path.read_text())
            self.assertEqual(out["verdict_code"], "PASS", out["falsification_failures"])
            for field, value, expected in [
                ("percentile_vs_random", "NaN", "FAIL"),
                ("percentile_vs_random", 1.1, "FAIL"),
                ("p_value", "invalid", "FAIL"),
                ("percentile", 0.94999, "FAIL"),
                ("percentile", 0.95, "PASS"),
            ]:
                (root / "perm.json").write_text(json.dumps({field: value}))
                subprocess.run([
                    sys.executable, str(SCRIPT), "report", "--returns", str(root / "r.csv"),
                    "--bench", str(root / "b.csv"), "--single-spec", "--market", "us_stock",
                    "--permutation-result", str(root / "perm.json"),
                    "--execution-manifest", str(root / "execution.json"),
                    "--data-manifest", str(root / "data.json"),
                    "--out", str(out_path), "--iters", "100",
                ], check=True, capture_output=True, text=True)
                result = json.loads(out_path.read_text())
                self.assertEqual(result["verdict_code"], expected, (field, value, result))



if __name__ == "__main__":
    unittest.main()
