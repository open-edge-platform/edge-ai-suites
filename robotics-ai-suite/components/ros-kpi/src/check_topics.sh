#!/bin/bash
# check_topics.sh — Simple ROS2 topic inspector
#
# Checks /cmd_vel_nav, /plan, and /camera/image_raw and prints:
#   - who is publishing / subscribing
#   - current publish frequency (sampled over a few seconds)
#   - the most recent message (one shot)
#
# Usage:
#   bash src/check_topics.sh            # default 5-second Hz sample, 3 messages
#   bash src/check_topics.sh --hz 10    # 10-second Hz sample
#   bash src/check_topics.sh --msgs 5   # show 5 messages per topic
#   bash src/check_topics.sh --move-secs 5  # seconds to sample odometry movement (default: 4)

# ── source ROS2 ──────────────────────────────────────────────────────────────
if [ -f /opt/ros/jazzy/setup.bash ]; then
    source /opt/ros/jazzy/setup.bash
elif [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
else
    echo "ERROR: ROS2 not found under /opt/ros/"
    exit 1
fi

# ── settings ─────────────────────────────────────────────────────────────────
HZ_DURATION=5      # seconds to measure publish frequency
MSG_COUNT=3        # number of messages to echo per topic
MOVE_SECS=4        # seconds between odometry samples for movement check

# parse optional --hz / --msgs / --move-secs arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --hz)         HZ_DURATION="$2"; shift 2 ;;
        --msgs)       MSG_COUNT="$2";   shift 2 ;;
        --move-secs)  MOVE_SECS="$2";   shift 2 ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

TOPICS=(
    "/cmd_vel_nav"
    "/plan"
    "/camera/image_raw"
)

# Optional explicit message types (passed as positional arg to ros2 topic echo)
declare -A TOPIC_TYPE
TOPIC_TYPE["/cmd_vel_nav"]="geometry_msgs/msg/TwistStamped"

# ── helpers ───────────────────────────────────────────────────────────────────
divider() { printf '%.0s─' {1..60}; echo; }
header()  { echo; echo "▶  $1"; divider; }

# ── main loop ────────────────────────────────────────────────────────────────
echo
echo "╔══════════════════════════════════════════════════════════╗"
echo "║        ROS2 Topic Quick-Check                            ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo "  Hz sample window : ${HZ_DURATION}s"
echo "  Messages to echo : ${MSG_COUNT}"
echo "  Topics           : ${TOPICS[*]}"

# ── Robot movement check ─────────────────────────────────────────────────────
echo ""
divider
echo "[ Robot movement check — ${MOVE_SECS}s odometry sample ]"
divider

_get_odom_xy() {
    ros2 topic echo --once /odom 2>/dev/null \
        | awk '/pose:/{p=1} p && /x:/{print $2; p=0}' \
    | head -1 || echo "0"
}
_get_odom_y() {
    ros2 topic echo --once /odom 2>/dev/null \
        | awk 'found{print $2; exit} /position:/{found=1} found && /y:/{print $2; exit}' \
    | head -1 || echo "0"
}

X1=$(timeout 3 ros2 topic echo --once /odom 2>/dev/null | awk '/position:/{p=1} p && / x:/{print $2; exit}')
Y1=$(timeout 3 ros2 topic echo --once /odom 2>/dev/null | awk '/position:/{p=1} p && / y:/{print $2; exit}')

if [ -z "$X1" ]; then
    echo "  ✗ /odom not available — is the simulation running?"
else
    echo "  Position at t=0 : x=${X1}  y=${Y1}"
    echo "  Waiting ${MOVE_SECS}s..."
    sleep "$MOVE_SECS"
    X2=$(timeout 3 ros2 topic echo --once /odom 2>/dev/null | awk '/position:/{p=1} p && / x:/{print $2; exit}')
    Y2=$(timeout 3 ros2 topic echo --once /odom 2>/dev/null | awk '/position:/{p=1} p && / y:/{print $2; exit}')
    echo "  Position at t=${MOVE_SECS}s: x=${X2}  y=${Y2}"
    # compute Euclidean distance using awk
    DIST=$(awk -v x1="${X1:-0}" -v y1="${Y1:-0}" -v x2="${X2:-0}" -v y2="${Y2:-0}" \
        'BEGIN { d=sqrt((x2-x1)^2+(y2-y1)^2); printf "%.4f", d }')
    if awk -v d="$DIST" 'BEGIN { exit (d > 0.01) ? 0 : 1 }'; then
        echo "  ✅ Robot is MOVING  (displacement: ${DIST}m in ${MOVE_SECS}s)"
    else
        echo "  ✗ Robot appears STATIONARY  (displacement: ${DIST}m — check navigation stack)"
    fi
fi

for TOPIC in "${TOPICS[@]}"; do

    header "$TOPIC"

    # ── 1. Check the topic type and connections ───────────────────────────────
    echo "[ Info ]"
    if ! ros2 topic info "$TOPIC" 2>/dev/null; then
        echo "  ✗ Topic not found  —  is the robot stack running?"
        echo
        continue
    fi

    # ── 2. Measure publish frequency ─────────────────────────────────────────
    echo
    echo "[ Frequency — ${HZ_DURATION}s sample ]"
    HZ_OUTPUT=$(timeout "$HZ_DURATION" ros2 topic hz "$TOPIC" 2>&1)
    if echo "$HZ_OUTPUT" | grep -q "average rate"; then
        echo "$HZ_OUTPUT" | grep -E "average rate|min|max|std dev"
    else
        echo "  ✗ No messages received in ${HZ_DURATION}s  —  topic may be idle"
    fi

    # ── 3. Print the latest N messages ───────────────────────────────────────
    echo
    echo "[ Latest ${MSG_COUNT} message(s) ]"
    for i in $(seq 1 "$MSG_COUNT"); do
        echo "  --- msg ${i} ---"
        MSG_TYPE="${TOPIC_TYPE[$TOPIC]:-}"
        MSG=$(timeout 3 ros2 topic echo --once "$TOPIC" $MSG_TYPE 2>&1)
        if [ -n "$MSG" ]; then
            echo "$MSG" | head -20
            LINE_COUNT=$(echo "$MSG" | wc -l)
            if [ "$LINE_COUNT" -gt 20 ]; then
                echo "  … ($(( LINE_COUNT - 20 )) more lines)"
            fi
        else
            echo "  ✗ No message received in 3s"
            break
        fi
    done

    echo

done

echo "Done. Run while the robot is active for live data."
echo "Tip: 'ros2 topic list' shows all active topics."
