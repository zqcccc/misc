# STOP 停止约定

## 终止命令

在仓库根目录或终端执行以下任一命令即可全局生效：

```bash
touch quant_research/loop/STOP
# 或者直接在仓库根目录：
touch STOP
```

## 退出机制

- `STOP` 哨兵全局生效：多实例或者单实例长跑时，任一时刻创建此文件，运行实例都会在当前轮次边界检测到并退出。
- 实例在每轮主循环开始前先检测（`test -f quant_research/loop/STOP`）。
- 当前正在执行的假设验证不会被强行截断，待完成当前卡的日志与裁决收尾后安全退出。

## 恢复继续循环

`STOP` 具有持久性，重新启动循环前必须先清理：

```bash
rm -f quant_research/loop/STOP STOP
```
