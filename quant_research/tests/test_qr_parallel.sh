#!/usr/bin/env bash
# 并行基础设施回归测试：阻塞记录 / 接管 CAS / 开工基线与增量自检 / 协议版本与重判队列。
# 全程在临时 QR_HOME 上跑，不碰真实台账。
set -uo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QR_ROOT="$(dirname "$SELF_DIR")"
QR="$QR_ROOT/qr"

PASS_N=0; FAIL_N=0
ok()  { PASS_N=$((PASS_N+1)); echo "  ok   $1"; }
bad() { FAIL_N=$((FAIL_N+1)); echo "  FAIL $1"; }
expect_ok()   { local d="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$d"; else bad "$d（本应成功却失败）"; fi; }
expect_fail() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then bad "$d（本应被拒却放行）"; else ok "$d"; fi; }
expect_eq()   { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1（期望 $3，实际 $2）"; fi; }

TMP="$(mktemp -d /tmp/qr-parallel-test.XXXXXX)"
PROTO="$TMP/proto"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/templates" "$TMP/hypotheses" "$TMP/locks" "$PROTO"
cp "$QR_ROOT/templates/hypothesis.md" "$TMP/templates/hypothesis.md"
printf '# fake protocol\n' > "$PROTO/SKILL.md"
printf 'x = 1\n' > "$PROTO/qbt.py"
cp "$QR_ROOT/qr" "$TMP/qr"; chmod +x "$TMP/qr"
export QR_HOME="$TMP" QBT_HOME="$PROTO" QR_AGENT="alice"
QRT="$TMP/qr"

fp() { QR_AGENT=alice "$QRT" protocol | sed -n 's/^指纹: *//p'; }

echo "== 阻塞记录 =="
expect_ok   "开一条 WARN 阻塞"  "$QRT" blocker open "示例：某个指标口径存疑" --severity WARN
expect_ok   "WARN 不挡 blocker list" "$QRT" blocker list
expect_fail "非法严重级被拒"     "$QRT" blocker open "x" --severity URGENT
expect_fail "HALT 不写 --blocks 被拒" "$QRT" blocker open "没写作用域" --severity HALT
expect_ok   "开一条挡所有人的 HALT"  "$QRT" blocker open "验收门禁能被绕过" --severity HALT --blocks all --evidence some/path
expect_fail "有 HALT/all 时 list 退出码 1" "$QRT" blocker list
expect_fail "关闭阻塞必须写清怎么解决的" "$QRT" blocker close B0002
expect_ok   "关闭 HALT"          "$QRT" blocker close B0002 "已修复并登记 v2"
expect_ok   "HALT 关闭后 list 恢复 0" "$QRT" blocker list
expect_fail "重复关闭被拒"       "$QRT" blocker close B0002 "再关一次"

echo
echo "== 协议版本与重判队列 =="
expect_fail "未登记版本时 register 缺 impact 被拒" "$QRT" protocol register v1 --note x
expect_ok   "登记 v1"  "$QRT" protocol register v1 --impact none --note "起始版本"
expect_fail "同一指纹重复登记被拒" "$QRT" protocol register v2 --impact none --note "重复"
expect_eq   "protocol 能把指纹翻成版本" "$("$QRT" protocol | sed -n 's/^版本: *//p')" "v1"

# 造一张判于 v1 的 FAIL 卡
"$QRT" claim "测试假设一" --family other --market multi --agent alice >/dev/null 2>&1
"$QRT" verdict H0001 FAIL --cause 信号无增量 "把整个池子买了一遍，什么都没多出来" >/dev/null 2>&1
expect_eq "卡片盖上了当时的指纹" "$(sed -n 's/^protocol_sha256: *//p' "$TMP"/hypotheses/H0001-*.md)" "$(fp)"

# 协议变更 → 新指纹 → 登记为 tighten
printf 'x = 2\n' > "$PROTO/qbt.py"
expect_ok "改协议后能登记 v2" "$QRT" protocol register v2 --impact tighten --note "门槛收紧"
expect_eq "tighten 不牵连 FAIL 卡" "$("$QRT" rejudge | sed -n 's/.*待重判 \([0-9]*\) 张.*/\1/p')" "0"

# loosen 才会把 FAIL 卡拉进队列
printf 'x = 3\n' > "$PROTO/qbt.py"
"$QRT" protocol register v3 --impact loosen --note "门槛放宽" >/dev/null 2>&1
expect_eq "loosen 把 FAIL 卡拉进待重判" "$("$QRT" rejudge | sed -n 's/.*待重判 \([0-9]*\) 张.*/\1/p')" "1"

echo
echo "== 开工基线与增量自检 =="
expect_fail "没有基线就自检会被拒" "$QRT" selfcheck --agent bob
mkrun() { "$QRT" start --agent "$1" 2>/dev/null | sed -n 's/.*export QR_RUN=\([^ ]*\).*/\1/p' | head -1; }
RUN_A="$(mkrun alice)"
if [ -n "$RUN_A" ]; then ok "开工写基线并给出 run token"; else bad "开工没给出 run token"; fi
export QR_RUN="$RUN_A"
expect_ok   "没动任何东西 → 自检通过" "$QRT" selfcheck --agent alice

# 关键回归：开工前就存在的改动不算数，只有开工后的改动才算
printf 'x = 4\n' > "$PROTO/qbt.py"
expect_fail "开工后改协议 → 自检不通过" "$QRT" selfcheck --agent alice
# 归因：HEAD 动了说明期间有提交落地，是维护者的改动，不该判成这个 agent 的违规
# （2026-09-05 实测：我并发改 qr 时，gpt 的收工自检开出了一条假阳性的 HALT/all）
sed -i '' 's/^git_head=.*/git_head=deadbee/' "$TMP/runs/$RUN_A.env" 2>/dev/null || \
  sed -i 's/^git_head=.*/git_head=deadbee/' "$TMP/runs/$RUN_A.env"
expect_ok "HEAD 变了 → 判为维护而非违规" "$QRT" selfcheck --agent alice
RUN_A="$(mkrun alice)"; export QR_RUN="$RUN_A"
expect_ok   "同样的脏工作区，重新开工后自检通过（增量为零）" "$QRT" selfcheck --agent alice

# HALT 阻塞挡开工
"$QRT" blocker open "新发现的门禁漏洞" --severity HALT --blocks all >/dev/null 2>&1
expect_fail "有 HALT/all 时开工被挡" "$QRT" start --agent alice
"$QRT" blocker close B0003 "已处理" >/dev/null 2>&1
expect_ok   "关掉 HALT 后可以开工" "$QRT" start --agent alice
RUN_A="$(mkrun alice)"; export QR_RUN="$RUN_A"

echo
echo "== 占坑归属与接管 =="
QR_RUN="$RUN_A" "$QRT" claim "测试假设二" --family other --market multi --agent alice >/dev/null 2>&1
RUN_B="$(mkrun bob)"
expect_fail "非坑主不能裁决" env QR_AGENT=bob QR_RUN=$RUN_B "$QRT" verdict H0002 FAIL --cause 强度不足 "太弱了不值得做"
expect_fail "非坑主不能释放" env QR_AGENT=bob QR_RUN=$RUN_B "$QRT" release H0002 "抢一个"
expect_ok   "非坑主可以留痕" env QR_AGENT=bob QR_RUN=$RUN_B "$QRT" note H0002 "我打算接管这张卡"
expect_ok   "留痕标注了非坑主" grep -q "非坑主，坑主是 alice" "$(ls "$TMP"/hypotheses/H0002-*.md)"
expect_fail "接管必须写 --expect" env QR_AGENT=bob QR_RUN=$RUN_B "$QRT" takeover H0002 --agent bob
expect_fail "expect 对不上就拒绝接管" env QR_AGENT=bob QR_RUN=$RUN_B "$QRT" takeover H0002 --expect carol --agent bob
expect_fail "没到僵尸线不许接管" env QR_AGENT=bob QR_RUN=$RUN_B "$QRT" takeover H0002 --expect alice --agent bob
expect_ok   "--force 可以接管"   env QR_AGENT=bob QR_RUN=$RUN_B "$QRT" takeover H0002 --expect alice --agent bob --force
expect_eq   "接管后坑主变了" "$(sed -n 's/^agent=//p' "$TMP/locks/H0002/owner")" "bob"
expect_fail "原坑主接管后不能再裁决" env QR_AGENT=alice QR_RUN=$RUN_A "$QRT" verdict H0002 FAIL --cause 强度不足 "太弱了"
expect_ok   "新坑主可以裁决" env QR_AGENT=bob QR_RUN=$RUN_B "$QRT" verdict H0002 FAIL --cause 强度不足 "太弱了不值得做"

echo
echo "== 台账写锁 =="
mkdir -p "$TMP/locks/.mutex-ledger"
QR_LOCK_WAIT_TICKS=3 expect_fail "锁被占用时写命令等待后放弃" env QR_LOCK_WAIT_TICKS=3 "$QRT" note H0001 "抢锁"
rmdir "$TMP/locks/.mutex-ledger"
expect_ok "锁释放后恢复正常" "$QRT" note H0001 "锁已释放"
expect_ok "只读命令不受写锁影响" bash -c 'mkdir -p "$QR_HOME/locks/.mutex-ledger"; "'"$QRT"'" list >/dev/null; rc=$?; rmdir "$QR_HOME/locks/.mutex-ledger"; exit $rc'

echo
echo "== 阻塞作用域：挡受影响的，不挡所有人 =="
# 这是 2026-09-05 的教训：B0005（A股数据）与 B0003（某张卡待复核）两条 HALT
# 把整支编队挡了一整天，而它们跟加密货币、美股、外汇的研究毫无关系。
BID="$("$QRT" blocker open "A股复权口径待修" --severity HALT --blocks market:cn_stock --evidence x 2>/dev/null | head -1 | awk '{print $1}')"
expect_ok   "有作用域的 HALT 不挡 list"        "$QRT" blocker list
expect_ok   "有作用域的 HALT 不挡开工"          "$QRT" start --agent alice
expect_fail "被挡的市场不许开新课题"            env QR_AGENT=alice QR_RUN=$RUN_A "$QRT" claim "A股某想法" --market cn_stock --family other
expect_ok   "别的市场照常开课题"                env QR_AGENT=alice QR_RUN=$RUN_A "$QRT" claim "币圈某想法" --market crypto_perp --family other
expect_ok   "start 会点名被挡的市场"            bash -c '"'"$QRT"'" start --agent alice 2>/dev/null | grep -q "cn_stock"'
"$QRT" blocker close "$BID" "数据已重建并对账" >/dev/null 2>&1
expect_ok   "关闭后该市场恢复"                  env QR_AGENT=alice QR_RUN=$RUN_A "$QRT" claim "A股另一想法" --market cn_stock --family other
rm -f runs/alice.env 2>/dev/null || true

echo
echo "== 同名 agent 并发：归属与基线按【运行】走，不按名字走 =="
# 2026-09-05 实测：两个都叫 claude 的 agent 并行时，①互相能覆盖成本闸与裁决；
# ②A 号改协议后 B 号一开工就覆盖 runs/<名字>.env，A 号自检报「协议未变、自检通过」
#   —— 审计本身被绕过。名字是给人读的标签，同名并发很正常，坏的是拿标签当身份。
mkrun() { "$QRT" start --agent "$1" 2>/dev/null | sed -n 's/.*export QR_RUN=\([^ ]*\).*/\1/p' | head -1; }
RA="$(mkrun dup)"; RB="$(mkrun dup)"
if [ -n "$RA" ] && [ -n "$RB" ] && [ "$RA" != "$RB" ]; then ok "同名两次开工拿到不同 token"; else bad "同名两次开工的 token 不该相同（$RA / $RB）"; fi
CID="$(QR_AGENT=dup QR_RUN=$RA "$QRT" claim "A 号的课题" --market multi --family other 2>/dev/null | head -1 | awk '{print $1}')"
expect_eq "占坑记下了 run token" "$(sed -n 's/^run=//p' "$TMP/locks/$CID/owner")" "$RA"
expect_fail "同名不同运行不能裁决别人的卡" env QR_AGENT=dup QR_RUN=$RB "$QRT" verdict "$CID" FAIL --cause 无机理 "抢卡"
expect_fail "同名不同运行不能改别人的成本闸" env QR_AGENT=dup QR_RUN=$RB "$QRT" screen "$CID" --report verified/H0002/screen_go.json
expect_ok   "坑主自己可以裁决" env QR_AGENT=dup QR_RUN=$RA "$QRT" verdict "$CID" FAIL --cause 无机理 "自己的卡自己判"
# 歧义必须是错误，不能是默认：名下多个运行且没带 QR_RUN 时要报错，不能猜
expect_fail "有并发运行却不带 QR_RUN → 自检报错" env -u QR_RUN QR_AGENT=dup "$QRT" selfcheck --agent dup
expect_ok   "带上 QR_RUN 就能自检" env QR_AGENT=dup QR_RUN=$RA "$QRT" selfcheck --agent dup
# 单个运行时不该给人添麻烦：自动解析
RS="$(mkrun solo)"
expect_ok   "只有一个运行时不带 QR_RUN 也能自检" env QR_AGENT=solo "$QRT" selfcheck --agent solo

echo
echo "== 署名是元数据，不是身份 =="
# 名字的用途是「后来人看这张卡是谁做的」，不参与任何门禁。所以：不必由人指定、
# 不必唯一、缺了也不该影响正确性 —— 只影响可读性。
expect_ok "不给署名也能开工" "$QRT" start
NAMED="$("$QRT" start --as "Claude Opus 5" 2>/dev/null | sed -n 's/.*export QR_RUN=\([^ ]*\).*/\1/p' | head -1)"
case "$NAMED" in claude-opus-5-*) ok "token 前缀按署名 ASCII 化（$NAMED）";; *) bad "token 前缀不对：$NAMED";; esac
if [ -f "$TMP/runs/$NAMED.env" ] && [ "$(sed -n 's/^agent=//p' "$TMP/runs/$NAMED.env")" = "Claude Opus 5" ]; then
  ok "基线里保留了原样的署名（含空格/大小写）"
else bad "基线没保留原样署名"; fi
expect_ok "带空格的署名能自检" env QR_AGENT="Claude Opus 5" QR_RUN="$NAMED" "$QRT" selfcheck --agent "Claude Opus 5"

echo
echo "== locale 兼容性 =="
# macOS 的 bash 3.2 在 C.UTF-8 下会把紧跟 $var 的中文字节读进变量名（B0006）。
# 所有面向 agent 的输出都带中文，必须在任何 locale 下都不炸。
for L in C C.UTF-8 en_US.UTF-8 zh_CN.UTF-8; do
  err="$(LC_ALL="$L" "$QRT" start --agent "lc$L" 2>&1 >/dev/null || true)"
  if [ -z "$err" ]; then ok "LC_ALL=$L 下 qr start 无 stderr"; else bad "LC_ALL=$L 下 qr start 报错：$err"; fi
  err="$(LC_ALL="$L" "$QRT" selfcheck --agent "lc$L" 2>&1 >/dev/null || true)"
  if [ -z "$err" ]; then ok "LC_ALL=$L 下 qr selfcheck 无 stderr"; else bad "LC_ALL=$L 下 qr selfcheck 报错：$err"; fi
done

echo
echo "结果：通过 $PASS_N，失败 $FAIL_N"
[ "$FAIL_N" -eq 0 ]
