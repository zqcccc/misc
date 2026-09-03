"""测试 PB+ROE 策略的绝对因果律（防未来函数硬门禁）。

1. 截断不变性：数据在 T_cut 截断后，T_cut 之前的 PB、ROE、综合得分、选股名单必须逐点相同。
2. 未来扰动不变性：T_cut 之后的未来财务数据或价格被扰动/篡改，T_cut 之前的选股结果不可受任何影响。
"""
import numpy as np
import pandas as pd
import pytest

from aq import panel, universe, strategies_pb_roe


@pytest.fixture(scope="module")
def loaded_panels():
    p = panel.load_panels(["close", "close_raw", "amount"])
    p["pb"] = pd.read_parquet("astock_quant/data/panel/pb.parquet")
    p["roe"] = pd.read_parquet("astock_quant/data/panel/roe.parquet")
    return p


def test_pb_roe_truncation_invariant(loaded_panels):
    """截断测试：取中间某个调仓日，截断前后打分完全一致。"""
    p = loaded_panels
    mask = universe.investable(p)
    cut = p["close"].index[1500]  # 约 2021 年某个时点

    score_full = strategies_pb_roe.compute_pb_roe_score(
        pb=p["pb"], roe=p["roe"], mask=mask, weight_pb=0.5, weight_roe=0.5
    )

    # 截断数据
    p_trunc = {k: v.loc[:cut].copy() for k, v in p.items()}
    mask_trunc = universe.investable(p_trunc)
    score_trunc = strategies_pb_roe.compute_pb_roe_score(
        pb=p_trunc["pb"], roe=p_trunc["roe"], mask=mask_trunc, weight_pb=0.5, weight_roe=0.5
    )

    # 检查截断点当天打分
    s_full_cut = score_full.loc[cut].dropna()
    s_trunc_cut = score_trunc.loc[cut].dropna()

    assert len(s_full_cut) > 0, "截断日全量打分不可为空"
    assert len(s_trunc_cut) > 0, "截断日截断打分不可为空"
    assert set(s_full_cut.index) == set(s_trunc_cut.index), "候选标的集合必须完全相同"

    diff = np.abs(s_full_cut.values - s_trunc_cut.values)
    assert np.max(diff) < 1e-6, f"存在未来函数泄露！截断日前后打分最大偏差: {np.max(diff)}"

    # 检查选出的 Top 20
    top_full = s_full_cut.nlargest(20).index.tolist()
    top_trunc = s_trunc_cut.nlargest(20).index.tolist()
    assert top_full == top_trunc, "截断日前后选出的 Top 20 标的必须 100% 严格一致"


def test_pb_roe_future_perturbation_invariant(loaded_panels):
    """未来扰动测试：改变 T_cut 之后的未来财务数据，历史选股绝对不受污染。"""
    p = loaded_panels
    mask = universe.investable(p)
    cut = p["close"].index[1200]

    score_full = strategies_pb_roe.compute_pb_roe_score(
        pb=p["pb"], roe=p["roe"], mask=mask, weight_pb=0.5, weight_roe=0.5
    )

    p_pert = {k: v.copy() for k, v in p.items()}
    future_idx = p["close"].index > cut
    # 把未来的 PB 与 ROE 恶意修改
    p_pert["pb"].loc[future_idx] = 999.0
    p_pert["roe"].loc[future_idx] = -999.0

    score_pert = strategies_pb_roe.compute_pb_roe_score(
        pb=p_pert["pb"], roe=p_pert["roe"], mask=mask, weight_pb=0.5, weight_roe=0.5
    )

    s_full_cut = score_full.loc[cut].dropna()
    s_pert_cut = score_pert.loc[cut].dropna()

    diff = np.abs(s_full_cut.values - s_pert_cut.values)
    assert np.max(diff) < 1e-6, "未来数据扰动影响到了历史截面的打分！"
    top_full = s_full_cut.nlargest(20).index.tolist()
    top_pert = s_pert_cut.nlargest(20).index.tolist()
    assert top_full == top_pert, "未来扰动影响了历史 Top 20 选股！"
