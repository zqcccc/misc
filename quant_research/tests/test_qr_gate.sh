#!/usr/bin/env bash
# qr 台账门禁回归测试：在临时 QR_HOME 上跑，不碰真实台账。
# 用法: quant_research/tests/test_qr_gate.sh
set -uo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QR_ROOT="$(dirname "$SELF_DIR")"
QR="$QR_ROOT/qr"

PASS_N=0; FAIL_N=0
ok()  { PASS_N=$((PASS_N+1)); echo "  ok   $1"; }
bad() { FAIL_N=$((FAIL_N+1)); echo "  FAIL $1"; }

# 门禁测试的重点是「该拒的有没有拒」，所以断言写成对退出码的期望
expect_ok()   { local d="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$d"; else bad "$d（本应成功却失败）"; fi; }
expect_fail() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then bad "$d（本应被拒却放行）"; else ok "$d"; fi; }
expect_eq()   { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1（期望 $3，实际 $2）"; fi; }

TMP="$(mktemp -d /tmp/qr-gate-test.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/templates" "$TMP/hypotheses" "$TMP/locks" "$TMP/verified/H0002"
cp "$QR_ROOT/templates/hypothesis.md" "$TMP/templates/hypothesis.md"
export QR_HOME="$TMP" QR_AGENT="gate-test"

card()  { ls "$TMP/hypotheses/$1-"*.md 2>/dev/null | head -1; }
fmval() { sed -n "/^$2:/{s/^$2:[[:space:]]*//p;q;}" "$(card "$1")"; }

cat > "$TMP/verified/H0002/exploratory.json" <<'JSON'
{"schema_version": 2, "stage": "exploratory", "role": "alpha", "verdict_code": "DIAGNOSTIC",
 "falsification_failures": [], "execution_check": {}, "data_provenance": {}, "window_consistency": {}}
JSON
cat > "$TMP/verified/H0002/candidate.json" <<'JSON'
{"schema_version": 2, "stage": "candidate", "role": "alpha", "verdict_code": "PASS",
 "falsification_failures": [],
 "execution_check": {"validated": true}, "data_provenance": {"source_count": 1},
 "window_consistency": {"oos_start": "2019-01-02"},
 "alpha_beta": {"ann_alpha": 0.08, "alpha_t": 3.1},
 "monte_carlo": {"prob_profit": 0.98},
 "random_portfolio": {"percentile_vs_random": 0.99},
 "selection_adjustment": {"DSR": 0.97}}
JSON

# 门禁必须 fail-closed：无效统计值（NaN / 越界）不能因为「不小于阈值」就放行
cat > "$TMP/verified/H0002/nan_stat.json" <<'JSON'
{"schema_version": 2, "stage": "candidate", "role": "alpha", "verdict_code": "PASS",
 "falsification_failures": [],
 "execution_check": {"validated": true}, "data_provenance": {"source_count": 1},
 "window_consistency": {"oos_start": "2019-01-02"},
 "alpha_beta": {"ann_alpha": 0.08, "alpha_t": 3.1},
 "monte_carlo": {"prob_profit": 0.98},
 "random_portfolio": {"percentile_vs_random": NaN},
 "selection_adjustment": {"DSR": 0.97}}
JSON
cat > "$TMP/verified/H0002/oob_stat.json" <<'JSON'
{"schema_version": 2, "stage": "candidate", "role": "alpha", "verdict_code": "PASS",
 "falsification_failures": [],
 "execution_check": {"validated": true}, "data_provenance": {"source_count": 1},
 "window_consistency": {"oos_start": "2019-01-02"},
 "alpha_beta": {"ann_alpha": 0.08, "alpha_t": 3.1},
 "monte_carlo": {"prob_profit": 0.98},
 "random_portfolio": {"percentile_vs_random": 1.1},
 "selection_adjustment": {"DSR": 0.97}}
JSON

echo "── claim 参数校验"
expect_ok   "--role hedge 可以占坑"          "$QR" claim "对冲角色测试卡" --market multi --family other --role hedge
expect_eq   "research_role 落到 frontmatter" "$(fmval H0001 research_role)" "hedge"
expect_fail "--role bogus 被拒"              "$QR" claim "非法角色"   --market multi --family other --role bogus
expect_fail "--parent 指向不存在的卡被拒"     "$QR" claim "悬空父卡"   --market multi --family other --parent H9999
expect_fail "--parent 格式错被拒"            "$QR" claim "格式错父卡" --market multi --family other --parent H1
expect_ok   "--parent 指向真实卡可以占坑"     "$QR" claim "合法子卡"   --market multi --family other --parent H0001
expect_eq   "被拒的 claim 不占号段"           "$(fmval H0002 parent)" "H0001"

echo "── verdict PASS 门禁"
expect_fail "PASS 缺 --report 被拒"           "$QR" verdict H0001 PASS "对冲卡想直接过"
expect_fail "非 alpha 角色不能自动 PASS"       "$QR" verdict H0001 PASS "对冲角色配 alpha 报告" --report verified/H0002/candidate.json
expect_fail "stage=exploratory 的报告不能 PASS" "$QR" verdict H0002 PASS "拿探索报告冒充" --report verified/H0002/exploratory.json
expect_fail "统计值是 NaN 的报告不能 PASS"     "$QR" verdict H0002 PASS "统计值算崩了" --report verified/H0002/nan_stat.json
expect_fail "统计值越界的报告不能 PASS"        "$QR" verdict H0002 PASS "分位大于 1" --report verified/H0002/oob_stat.json
expect_ok   "candidate 报告可以 PASS"          "$QR" verdict H0002 PASS "证据齐全" --report verified/H0002/candidate.json
expect_eq   "PASS 已写回卡片"                 "$(fmval H0002 verdict)" "PASS"

"$QR" claim "第三张卡用于裁决测试" --market multi --family other >/dev/null 2>&1

echo "── 裁决必须写死因、必须说人话"
expect_fail "FAIL 不写 --cause 被拒" "$QR" verdict H0003 FAIL "这条路死了"
expect_fail "死因不在词表里被拒"     "$QR" verdict H0003 FAIL --cause 随便写 "这条路死了"
expect_fail "结论句带行话被拒"       "$QR" verdict H0003 FAIL --cause 强度不足 "净 alpha 只有 2.9%，DSR 0.74 未过线"
expect_ok   "人话结论 + 合法死因可以裁决" "$QR" verdict H0003 FAIL --cause 成本吃穿 "信号是真的，但每次进出的手续费比它赚的还多"
expect_eq   "死因写回卡片" "$(fmval H0003 cause)" "成本吃穿"
if grep -q '🔴 \[multi\] .* —— 成本吃穿 —— 信号是真的' "$TMP/KNOWLEDGE.md"; then
  ok "KNOWLEDGE.md 一行里有红绿灯/死因/人话"
else
  bad "KNOWLEDGE.md 行格式不对: $(tail -1 "$TMP/KNOWLEDGE.md")"
fi
KLINE_LEN=$(tail -1 "$TMP/KNOWLEDGE.md" | wc -m | tr -d ' ')
if [ "$KLINE_LEN" -lt 400 ]; then ok "KNOWLEDGE 行长可扫（$KLINE_LEN 字节）"; else bad "KNOWLEDGE 行过长: $KLINE_LEN"; fi

echo "── 打分卡回验"
"$QR" claim "带打分的卡" --market multi --family other --score 9/14 >/dev/null 2>&1
expect_eq "打分写进卡片" "$(fmval H0004 score)" "9/14"
case "$("$QR" scorecard)" in *"样本不足"*) ok "没数据时如实说样本不足，不硬给结论";; *) bad "scorecard 在没数据时给了结论";; esac
"$QR" verdict H0004 FAIL --cause 无机理 "想不出谁会持续为这件事付钱" >/dev/null 2>&1
case "$("$QR" scorecard)" in *"9/14"*64.3*) ok "分数按满分归一后与结局并列显示";; *) bad "scorecard 没把分数和结局对上: $("$QR" scorecard | tail -2)";; esac

echo "── 线索队列"
LEADS_BEFORE="$("$QR" leads)"
case "$LEADS_BEFORE" in *"没有未接手的线索"*) ok "干净台账没有线索";; *) bad "空台账不该有线索";; esac
printf '\n- 重启线=等到成本降到 2bp 以下再验\n' >> "$(card H0003)"
case "$("$QR" leads)" in *"等到成本降到 2bp 以下再验"*) ok "卡里写的重启线会被 qr leads 捞出来";; *) bad "qr leads 没捞到重启线";; esac
"$QR" claim "接手 H0003 的线索" --market multi --family other --parent H0003 >/dev/null 2>&1
case "$("$QR" leads)" in *"等到成本降到 2bp 以下再验"*) bad "已被子卡接手的线索不该再提示";; *) ok "有子卡接手后线索自动下架";; esac

echo "── A 层成本闸"
cat > "$TMP/verified/H0002/screen_stop.json" <<'JSON'
{"schema_version": 2, "stage": "screen", "edge_cost_ratio": 0.25,
 "screen_verdict": "STOP", "说人话": "交易费就把它吃光了"}
JSON
cat > "$TMP/verified/H0002/screen_go.json" <<'JSON'
{"schema_version": 2, "stage": "screen", "edge_cost_ratio": 12.5,
 "screen_verdict": "GO", "说人话": "毛收益是成本的 12.5 倍"}
JSON
cat > "$TMP/verified/H0002/not_screen.json" <<'JSON'
{"schema_version": 2, "stage": "candidate", "screen_verdict": "GO"}
JSON

expect_fail "STOP 时 qr screen 返回非零（提醒别再写回测）" "$QR" screen H0001 --report verified/H0002/screen_stop.json
expect_eq   "STOP 也要留痕在卡片上" "$(fmval H0001 screen_verdict)" "STOP"
expect_fail "非 screen 产物被拒" "$QR" screen H0001 --report verified/H0002/not_screen.json
expect_ok   "GO 时 qr screen 正常通过" "$QR" screen H0001 --report verified/H0002/screen_go.json
expect_eq   "GO 覆盖掉之前的 STOP" "$(fmval H0001 screen_verdict)" "GO"
expect_eq   "毛/成本比值写进卡片" "$(fmval H0001 edge_cost_ratio)" "12.5"

echo "── 协议指纹"
DIGEST="$("$QR" protocol | sed -n 's/^指纹:[[:space:]]*//p')"
if printf '%s' "$DIGEST" | grep -qE '^[0-9a-f]{16}$'; then ok "qr protocol 给出 16 位指纹"; else bad "qr protocol 指纹异常: $DIGEST"; fi
expect_eq "PASS 卡片盖上了当前协议指纹" "$(fmval H0002 protocol_sha256)" "$DIGEST"

echo "── audit 能抓住手改卡片"
expect_ok "干净台账 audit 通过" "$QR" audit

sed -i '' 's/^research_role: alpha$/research_role: 随便写/' "$(card H0002)"
expect_fail "非法 research_role 被 audit 拦下" "$QR" audit

sed -i '' 's/^research_role: 随便写$/research_role: hedge/' "$(card H0002)"
expect_fail "改角色后 PASS 报告 role 对不上被 audit 拦下" "$QR" audit

sed -i '' 's/^research_role: hedge$/research_role: alpha/' "$(card H0002)"
sed -i '' 's/^parent:.*$/parent: H9999/' "$(card H0002)"
expect_fail "悬空 parent 被 audit 拦下" "$QR" audit


# frontmatter 少了闭合的 ---，之后所有 set_fm 都会静默丢字段，必须报错而不是放行
python3 - "$(card H0002)" <<'PY'
import sys
p = sys.argv[1]
lines = open(p, encoding="utf-8").read().split("\n")
end = next(i for i, l in enumerate(lines[1:], 1) if l == "---")
lines = [l for l in lines[:end] if not l.startswith("screen_verdict:")] + lines[end + 1:]
open(p, "w", encoding="utf-8").write("\n".join(lines))
PY
expect_fail "frontmatter 未闭合被 audit 拦下" "$QR" audit
expect_fail "frontmatter 未闭合时新增字段不许静默成功" "$QR" screen H0002 --report verified/H0002/screen_go.json

sed -i '' 's/^parent: H9999$/parent:/' "$(card H0002)"
sed -i '' 's/^protocol_sha256: .*$/protocol_sha256: unresolved/' "$(card H0002)"
expect_fail "PASS 但协议指纹为 unresolved 被 audit 拦下" "$QR" audit

echo "── 归属保护必须覆盖【所有】改卡片的写入口（B0008）"
# gpt 2026-09-05 发现：verdict/release 有归属校验，screen 没有，于是别的 agent 能把
# 别人卡上的成本闸从 STOP 覆盖成 GO，而 qr audit 照样通过。
# 这条测试遍历所有会改卡片的子命令，漏掉任何一个都会红。
OWNED="$("$QR" claim "归属保护测试卡" --market multi --family other --agent owner-a 2>/dev/null | head -1 | awk '{print $1}')"
expect_fail "非坑主不能改成本闸(screen)" env QR_AGENT=intruder "$QR" screen "$OWNED" --report verified/H0002/screen_go.json
expect_fail "非坑主不能裁决(verdict)"    env QR_AGENT=intruder "$QR" verdict "$OWNED" FAIL --cause 强度不足 "太弱了不值得做"
expect_fail "非坑主不能释放(release)"    env QR_AGENT=intruder "$QR" release "$OWNED" "抢一个"
expect_ok   "坑主自己可以改成本闸"        env QR_AGENT=owner-a "$QR" screen "$OWNED" --report verified/H0002/screen_go.json

echo "── execution 角色走载体替换验收，不套 alpha 的判读线"
cat > "$TMP/verified/H0002/carrier.json" <<'JSON'
{"schema_version": 2, "stage": "candidate", "role": "execution", "verdict_code": "PASS",
 "falsification_failures": [],
 "execution_check": {"validated": true}, "data_provenance": {"source_count": 1},
 "carrier_risk": {"validated": true},
 "carrier_swap": {"net_diff_annual": 0.03, "net_diff_t": 4.1,
                  "exposure_adjusted_excess_annual": 0.028, "exposure_adjusted_t": 3.9,
                  "beta_vs_incumbent": 1.01, "r_squared": 0.98},
 "carrier_swap_stressed": {"net_diff_annual": 0.021}}
JSON
cat > "$TMP/verified/H0002/carrier_norisk.json" <<'JSON'
{"schema_version": 2, "stage": "candidate", "role": "execution", "verdict_code": "PASS",
 "falsification_failures": [],
 "execution_check": {"validated": true}, "data_provenance": {"source_count": 1},
 "carrier_swap": {"net_diff_annual": 0.03, "net_diff_t": 4.1,
                  "exposure_adjusted_excess_annual": 0.028, "exposure_adjusted_t": 3.9,
                  "beta_vs_incumbent": 1.01, "r_squared": 0.98},
 "carrier_swap_stressed": {"net_diff_annual": 0.021}}
JSON
EXEC_ID="$("$QR" claim "载体替换测试卡" --market multi --family other --role execution 2>/dev/null | head -1 | awk '{print $1}')"
expect_fail "execution 卡不能拿 alpha 报告 PASS" "$QR" verdict $EXEC_ID PASS "拿错报告" --report verified/H0002/candidate.json
expect_fail "载体风险未申报不能 PASS"           "$QR" verdict $EXEC_ID PASS "缺风险申报" --report verified/H0002/carrier_norisk.json
expect_ok   "载体替换报告可以 PASS"             "$QR" verdict $EXEC_ID PASS "同一份敞口换个方式拿，一年多留下三个点" --report verified/H0002/carrier.json
expect_eq   "execution 的 PASS 写回卡片"        "$(fmval $EXEC_ID verdict)" "PASS"


echo
echo "qr gate: passed=$PASS_N failed=$FAIL_N"
[ "$FAIL_N" -eq 0 ]
