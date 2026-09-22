#!/bin/bash
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# RAG知识库查询脚本
# 用法: ./query_rag.sh "your question here" [top_n] [max_tokens]
HOST_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '/src/ {for (i = 1; i <= NF; ++i) if ($i == "src") {print $(i + 1); exit}}')
HOST_IP="${HOST_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"

if [ -z "${HOST_IP// }" ]; then
 HOST_IP=localhost
fi

HOST_IP="${HOST_IP// /}"
PORT="16011"
API_ENDPOINT="/v1/chatqna"
URL="http://${HOST_IP}:${PORT}${API_ENDPOINT}"
if [ $# -eq 0 ]; then
 echo "错误: 请提供查询问题"
 echo "用法: $0 \"your question here\""
 exit 1
fi
QUESTION="$1"
TOP_N="${2:-5}"
MAX_TOKENS="${3:-1200}"
JSON_DATA=$(cat <<EOF
{
 "messages": "$QUESTION",
 "top_n": $TOP_N,
 "max_tokens": $MAX_TOKENS,
 "chat_template_kwargs":{"enable_thinking": false, "enable_rag_retrieval": true},
 "stream": true
}
EOF
)

curl -X POST "$URL" \
 -H "Content-Type: application/json" \
 -d "$JSON_DATA" \
 -s
