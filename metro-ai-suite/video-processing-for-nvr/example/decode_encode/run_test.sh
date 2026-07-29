#!/usr/bin/env bash

# =========================
# 配置区
# =========================
CMD="./decode_encode -f config_16ports.txt -t 20"
LOG_DIR="./logs"
SUMMARY_LOG="./run_summary.log"

mkdir -p "$LOG_DIR"

# =========================
# 函数区
# =========================
format_seconds() {
    local total=$1
    local days=$((total / 86400))
    local hours=$(((total % 86400) / 3600))
    local mins=$(((total % 3600) / 60))
    local secs=$((total % 60))

    if [ "$days" -gt 0 ]; then
        printf "%dd %02dh %02dm %02ds" "$days" "$hours" "$mins" "$secs"
    else
        printf "%02dh %02dm %02ds" "$hours" "$mins" "$secs"
    fi
}

cleanup() {
    echo
    echo "检测到中断信号，脚本退出。"
    echo "总运行时间：$(format_seconds $(( $(date +%s) - SCRIPT_START_TIME )))"
    echo "已执行次数：$COUNT"
    echo "日志目录：$LOG_DIR"
    echo "汇总日志：$SUMMARY_LOG"
    exit 0
}

trap cleanup SIGINT SIGTERM

# =========================
# 主逻辑
# =========================
SCRIPT_START_TIME=$(date +%s)
COUNT=0

echo "========== 循环测试开始 ==========" | tee -a "$SUMMARY_LOG"
echo "开始时间：$(date '+%F %T')" | tee -a "$SUMMARY_LOG"
echo "执行命令：$CMD" | tee -a "$SUMMARY_LOG"
echo "日志目录：$LOG_DIR" | tee -a "$SUMMARY_LOG"
echo "=================================" | tee -a "$SUMMARY_LOG"

while true; do
    COUNT=$((COUNT + 1))

    RUN_START_TIME=$(date +%s)
    RUN_START_STR=$(date '+%F %T')

    # 每次运行一个独立日志，文件名里带次数和时间戳
    LOG_FILE="$LOG_DIR/run_${COUNT}_$(date '+%Y%m%d_%H%M%S').log"

    TOTAL_ELAPSED=$((RUN_START_TIME - SCRIPT_START_TIME))

    echo
    echo "[$(date '+%F %T')] 开始第 $COUNT 次运行"
    echo "脚本总运行时间：$(format_seconds "$TOTAL_ELAPSED")"
    echo "本次日志文件：$LOG_FILE"

    {
        echo "========== 第 $COUNT 次运行开始 =========="
        echo "开始时间：$RUN_START_STR"
        echo "执行命令：$CMD"
        echo "========================================="
    } >> "$LOG_FILE"

    # 执行命令，并将 stdout/stderr 全部写入日志
    # 如果希望控制台也实时看到程序输出，可以把下面这一行改成：
    # eval "$CMD" 2>&1 | tee -a "$LOG_FILE"
    eval "$CMD" >> "$LOG_FILE" 2>&1
    RET=$?

    RUN_END_TIME=$(date +%s)
    RUN_END_STR=$(date '+%F %T')
    RUN_ELAPSED=$((RUN_END_TIME - RUN_START_TIME))
    TOTAL_ELAPSED=$((RUN_END_TIME - SCRIPT_START_TIME))

    {
        echo
        echo "结束时间：$RUN_END_STR"
        echo "本次运行耗时：$(format_seconds "$RUN_ELAPSED")"
        echo "退出码：$RET"
        echo "========== 第 $COUNT 次运行结束 =========="
        echo
    } >> "$LOG_FILE"

    # 汇总日志，方便快速看哪次失败了
    echo "[$RUN_END_STR] 第 $COUNT 次运行结束 | 耗时: $(format_seconds "$RUN_ELAPSED") | 总耗时: $(format_seconds "$TOTAL_ELAPSED") | 退出码: $RET | 日志: $LOG_FILE" | tee -a "$SUMMARY_LOG"

    # 控制台提示
    echo "第 $COUNT 次运行完成，退出码: $RET，本次耗时: $(format_seconds "$RUN_ELAPSED")，总耗时: $(format_seconds "$TOTAL_ELAPSED")"

    # 如果你想在异常退出时停下来，把下面注释打开：
    # if [ "$RET" -ne 0 ]; then
    #     echo "检测到非0退出码，脚本停止。"
    #     exit "$RET"
    # fi
done
