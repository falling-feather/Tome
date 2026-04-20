import React from 'react';

interface Point {
  hour: string;
  requests: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

interface Props {
  points: Point[];
  hours: number;
  metric: 'tokens' | 'cost' | 'requests';
}

export function LlmTrendChart({ points, hours, metric }: Props) {
  const W = 720;
  const H = 160;
  const PAD_L = 44;
  const PAD_R = 12;
  const PAD_T = 16;
  const PAD_B = 28;
  const innerW = W - PAD_L - PAD_R;
  const innerH = H - PAD_T - PAD_B;

  // 构造完整 N 小时 bucket（含空时段）
  const now = new Date();
  now.setMinutes(0, 0, 0);
  const buckets: { hour: Date; v: number }[] = [];
  const map = new Map<string, Point>();
  points.forEach((p) => map.set(new Date(p.hour).toISOString(), p));
  for (let i = hours - 1; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 3600_000);
    const key = d.toISOString();
    const p = map.get(key);
    let v = 0;
    if (p) {
      if (metric === 'tokens') v = p.input_tokens + p.output_tokens;
      else if (metric === 'cost') v = p.cost_usd;
      else v = p.requests;
    }
    buckets.push({ hour: d, v });
  }

  const max = Math.max(1, ...buckets.map((b) => b.v));
  const barW = innerW / buckets.length;

  const yLabel = (val: number) => {
    if (metric === 'cost') return '$' + val.toFixed(val < 1 ? 3 : 2);
    if (val >= 1000) return (val / 1000).toFixed(1) + 'K';
    return String(Math.round(val));
  };

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: H, display: 'block' }}>
      {/* y 轴 */}
      <line x1={PAD_L} y1={PAD_T} x2={PAD_L} y2={PAD_T + innerH} stroke="var(--border-light)" />
      {/* x 轴 */}
      <line x1={PAD_L} y1={PAD_T + innerH} x2={PAD_L + innerW} y2={PAD_T + innerH} stroke="var(--border-light)" />
      {/* y 刻度 */}
      {[1, 0.5, 0].map((r) => {
        const y = PAD_T + innerH * (1 - r);
        return (
          <g key={r}>
            <line x1={PAD_L} y1={y} x2={PAD_L + innerW} y2={y} stroke="var(--border-light)" strokeDasharray="2,3" opacity={0.5} />
            <text x={PAD_L - 6} y={y + 4} textAnchor="end" fontSize="10" fill="var(--text-muted)" fontFamily="var(--font-mono)">
              {yLabel(max * r)}
            </text>
          </g>
        );
      })}
      {/* 柱状 */}
      {buckets.map((b, i) => {
        const h = (b.v / max) * innerH;
        const x = PAD_L + i * barW + 1;
        const y = PAD_T + innerH - h;
        return (
          <rect
            key={i}
            x={x}
            y={y}
            width={Math.max(1, barW - 2)}
            height={h}
            fill="var(--accent)"
            opacity={b.v > 0 ? 0.85 : 0.15}
          >
            <title>
              {b.hour.toLocaleString('zh-CN')} — {yLabel(b.v)}
            </title>
          </rect>
        );
      })}
      {/* x 标签：开头/中间/末尾 */}
      {[0, Math.floor(buckets.length / 2), buckets.length - 1].map((i) => {
        const b = buckets[i];
        const x = PAD_L + i * barW + barW / 2;
        return (
          <text key={i} x={x} y={H - 8} textAnchor="middle" fontSize="10" fill="var(--text-muted)" fontFamily="var(--font-mono)">
            {b.hour.getHours().toString().padStart(2, '0')}:00
          </text>
        );
      })}
    </svg>
  );
}
