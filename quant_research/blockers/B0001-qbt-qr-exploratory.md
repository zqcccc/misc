---
id: B0001
title: 门禁校验清单在 qbt.py 与 qr 两处各写一份，会漂移（原三项中的前两项已在协议 v5 修掉）
status: open
severity: WARN
scope: protocol
opened_by: claude
opened_at: 2026-09-05T03:24:45Z
closed_by:
closed_at:
evidence: DESIGN.md#还没做的
---

## 卡在哪

三处都不影响当前任何结论的正确性，所以是 WARN 不是 HALT。等下一次有人被授权做协议维护时一起改，
改完记得 `qr protocol register v3 --impact ...`。

1. **exploratory 报告混入门禁噪音。** `qbt.py` 里 `fails.extend(validate_gate_statistics(rep))`
   写在 `if strict:` 外面，`--exploratory` 跑出来的 DIAGNOSTIC 报告会凭空多出
   `random_portfolio.percentile_vs_random 缺失`、`selection_adjustment.PSR 缺失` 两条。
   裁决不受影响（照样是 DIAGNOSTIC），但会让人误以为出了问题。挪进 strict 分支即可。

2. **置换别名一致性容差过紧。** `load_permutation_result` 用 `abs_tol=1e-12` 比对
   `percentile` / `p_value` / `percentile_vs_random`。实测 `{"percentile": 0.9667,
   "p_value": 0.033333}` 这种"一个存 4 位小数、一个存 6 位"的正常文件会被判
   「多个统计字段互相矛盾」而拒掉。方向是 fail-closed 所以不危险，但会误杀合法候选。
   放宽到 `1e-6`，或者两边都 round 到 4 位再比。

3. **门禁校验清单两处重复。** 同一份必需统计值清单在 `qbt.py` 的 `validate_gate_statistics`
   和 `qr` 的内嵌 python 里各写了一遍，会漂移。而且 `qr` 不在协议指纹的计算范围内
   （指纹只扫协议目录下的 `.md`/`.py`），`qr` 那一层被改了指纹发现不了。

## 处理日志

- `2026-09-05T03:24:45Z` claude：开出这条阻塞（WARN）。

- `2026-09-05T06:30:00Z` claude：**第 1、2 项已修，登记为协议 v5（f186e8ce5874ee75，影响 none）。**
  - 第 1 项：`fails.extend(validate_gate_statistics(rep))` 挪进 `if strict:` 分支。
    `--exploratory` 的诊断报告不再凭空多出「random_portfolio/selection_adjustment 缺失」两条。
  - 第 2 项：别名一致性从 `abs_tol=1e-12` 改为**四位小数比较**。
    `{"percentile": 0.9667, "p_value": 0.033333}` 这种正常文件不再被误判成互相矛盾；
    判读仍用未取整的原值，`0.94999` 不会被并成 `0.95` 后晋级。
    只读扫描全工作区 68 份含置换别名的 JSON（其中 5 份同时带 ≥2 个别名，都是 randomport 自产），
    无一会被原容差误杀，所以历史裁决不受影响，影响登记为 `none`。
  - 各补 1 条回归，qbt 16 项全过。

- **第 3 项不修，本条阻塞保持 open（WARN）。** 让 `qr` 去 exec `qbt.py` 做校验会把台账 CLI
  绑死在协议目录可用上——`qr` 现在没有协议目录也能跑 audit/claim/note，绑上之后不能。
  代价是那份清单仍有两份。缓解措施：`tests/test_qr_gate.sh` 现在在 **qr 这一层**也覆盖了
  NaN、越界统计值和 execution 角色的载体门禁，任何一侧漂移都会让测试红。
  这是一个有意接受的欠账，不是忘了；同时记在 `DESIGN.md`「还没做的」。
