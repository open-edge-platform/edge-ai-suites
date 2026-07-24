
# 1. initialize（第一条 curl）
# 告诉服务器"我是一个新客户端，我们建立连接吧"。服务器会分配一个 session id，放在响应的 mcp-session-id 这个 HTTP 响应头里返回给你。这条命令用 -D -（打印响应头）配合 grep/cut，把这个 id 抠出来存进 $SID 变量。这一步之后你才有 $SID 可用。
SID=$(curl -sS -D - -o /tmp/init_body.json -X POST http://localhost:3100/mcp \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"manual-verify","version":"1.0"}}}' \
  | grep -i mcp-session-id | tr -d '\r' | cut -d' ' -f2)

# 2. notifications/initialized（第二条 curl）
# MCP 协议握手的收尾确认，格式上必须发，告诉服务器"初始化完成了"。不发这条，后面的订阅可能被服务器拒绝或行为不确定。
curl -sS -X POST http://localhost:3100/mcp -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

# 3. resources/subscribe（第三条 curl）
# 真正的订阅动作：告诉服务器"以后 smartbuilding://monitor/cam_child/alerts 这个资源有更新，请通知我这个 session（$SID）"。服务器内部会把 $SID 记到 McpSubscriberRegistry 里。
curl -sS -X POST http://localhost:3100/mcp -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"resources/subscribe","params":{"uri":"smartbuilding://monitor/cam_child/alerts"}}'

echo $SID

# 初次查阅
curl -sS -X POST http://localhost:3100/mcp -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":3,"method":"resources/read","params":{"uri":"smartbuilding://monitor/cam_child/alerts"}}'


# # 4. GET /mcp（另开一个终端，保持长连接监听推送（同一个 $SID）
# # 这不是发请求，而是打开一条长连接（SSE），用同一个 $SID 告诉服务器"我在这条连接上等你推送"。当 cam_child 有新 alert 时，服务器会通过这条连接主动推 notifications/resources/updated 消息过来 —— 这就是你要的"终端接收 alert 推送"。
# curl -sS -N -X GET http://localhost:3100/mcp -H "Accept: text/event-stream" -H "mcp-session-id: $SID"
# # 一旦有新 alert 产生，这里会收到：
# #   event: message
# #   data: {"method":"notifications/resources/updated","params":{"uri":"smartbuilding://monitor/cam_child/alerts"},"jsonrpc":"2.0"}

# # 收到通知后（通知本身不带 payload），用同一 $SID 按 cursor 拉增量内容：
# curl -sS -X POST http://localhost:3100/mcp -H "Content-Type: application/json" \
#   -H "Accept: application/json, text/event-stream" -H "mcp-session-id: $SID" \
#   -d '{"jsonrpc":"2.0","id":3,"method":"resources/read","params":{"uri":"smartbuilding://monitor/cam_child/alerts?since=<上次的 latestId>"}}'

cat <<EOF
  GET /mcp（另开一个终端，保持长连接监听推送（同一个 $SID）
  curl -sS -N -X GET http://localhost:3100/mcp -H "Accept: text/event-stream" -H "mcp-session-id: $SID"

  收到通知后（通知本身不带 payload），用同一 $SID 按 cursor 拉增量内容：
  curl -sS -X POST http://localhost:3100/mcp -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":3,"method":"resources/read","params":{"uri":"smartbuilding://monitor/cam_child/alerts?since=<上次的 latestId>"}}'
EOF