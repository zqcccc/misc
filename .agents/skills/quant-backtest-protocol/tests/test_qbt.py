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
