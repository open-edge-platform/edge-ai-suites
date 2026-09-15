interface Props {
  remaining: number; // seconds left until auto-reset
  total: number; // full countdown window in seconds
}

// Compact ring that depletes as the auto-reset countdown runs down.
export default function SessionResetTimer({ remaining, total }: Props) {
  const size = 34;
  const stroke = 3;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const progress = total > 0 ? Math.max(0, Math.min(1, remaining / total)) : 0;
  const offset = c * (1 - progress);

  return (
    <div
      title={`New session starts in ${remaining}s`}
      className="relative shrink-0"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#E5E7EB" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#0068B5"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.25s linear" }}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-semibold tabular-nums text-intel-blue">
        {remaining}
      </span>
    </div>
  );
}
