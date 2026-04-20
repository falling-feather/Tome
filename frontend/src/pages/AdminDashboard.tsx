import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { LlmTrendChart } from '../components/LlmTrendChart';

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

export function AdminDashboard() {
  const [stats, setStats] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [trend, setTrend] = useState<any>(null);
  const [trendMetric, setTrendMetric] = useState<'tokens' | 'cost' | 'requests'>('tokens');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getAdminStats().catch(() => null),
      api.getAdminHealth().catch(() => null),
      api.getLlmTrend(24).catch(() => null),
    ]).then(([s, h, t]) => {
      setStats(s);
      setHealth(h);
      setTrend(t);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="flex items-center gap-sm"><div className="spinner" /> 加载中...</div>;
  if (!stats) return <div>加载失败</div>;

  const counters = (health && health.metrics && health.metrics.counters) || {};
  const timings = (health && health.metrics && health.metrics.timings) || {};
  const llmIn = counters.llm_input_chars || 0;
  const llmOut = counters.llm_output_chars || 0;
  const llmTokens = counters.llm_tokens_est || 0;
  const llmRequests = counters.llm_requests || 0;
  const llmFailures = (counters.llm_total_failures || 0) + (counters.llm_completion_failures || 0);
  const llmStreamTiming = timings.llm_stream_ms;
  const llmCost = health && health.llm_cost;

  return (
    <div className="fade-in">
      <h2 className="admin-section-title">系统概览</h2>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-title">注册用户</div>
          <div className="stat-number">{stats.total_users}</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">游戏会话</div>
          <div className="stat-number">{stats.total_sessions}</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">消息总数</div>
          <div className="stat-number">{stats.total_messages}</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">日志条目</div>
          <div className="stat-number">{stats.total_logs}</div>
        </div>
      </div>

      {health && (
        <>
          <h3 className="admin-section-title">LLM 调用指标</h3>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-title">总请求</div>
              <div className="stat-number">{formatNumber(llmRequests)}</div>
              {llmFailures > 0 && (
                <div className="stat-sub" style={{ color: 'var(--error)' }}>
                  失败 {formatNumber(llmFailures)}
                </div>
              )}
            </div>
            <div className="stat-card">
              <div className="stat-title">输入字符</div>
              <div className="stat-number">{formatNumber(llmIn)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-title">输出字符</div>
              <div className="stat-number">{formatNumber(llmOut)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-title">Token 估算</div>
              <div className="stat-number">{formatNumber(llmTokens)}</div>
              <div className="stat-sub text-muted">≈ chars / 3</div>
            </div>
            {llmStreamTiming && (
              <div className="stat-card">
                <div className="stat-title">流式延迟</div>
                <div className="stat-number">{llmStreamTiming.avg_ms}<span style={{ fontSize: 14 }}> ms</span></div>
                <div className="stat-sub text-muted">
                  p50 {llmStreamTiming.p50_ms}{llmStreamTiming.p95_ms != null && ` · p95 ${llmStreamTiming.p95_ms}`} ms
                </div>
              </div>
            )}
            {health.circuit_breakers && (
              <div className="stat-card">
                <div className="stat-title">熔断器</div>
                <div className="stat-number" style={{ fontSize: 18 }}>
                  {health.circuit_breakers.llm_primary?.state || '—'}
                </div>
                <div className="stat-sub text-muted">
                  fallback: {health.circuit_breakers.llm_fallback?.state || '—'}
                </div>
              </div>
            )}
          </div>

          {llmCost && llmCost.models && llmCost.models.length > 0 && (
            <>
              <h3 className="admin-section-title">LLM 费用估算</h3>
              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-title">总费用 (USD)</div>
                  <div className="stat-number">${llmCost.total_cost_usd.toFixed(4)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-title">总费用 (CNY)</div>
                  <div className="stat-number">¥{llmCost.total_cost_cny.toFixed(2)}</div>
                  <div className="stat-sub text-muted">汇率 1 USD = {llmCost.usd_to_cny} CNY</div>
                </div>
                <div className="stat-card">
                  <div className="stat-title">输入 Token</div>
                  <div className="stat-number">{formatNumber(llmCost.total_input_tokens)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-title">输出 Token</div>
                  <div className="stat-number">{formatNumber(llmCost.total_output_tokens)}</div>
                </div>
              </div>

              <div className="table-wrap" style={{ marginTop: 12 }}>
                <table>
                  <thead>
                    <tr>
                      <th>模型</th>
                      <th>请求</th>
                      <th>输入 Token</th>
                      <th>输出 Token</th>
                      <th>USD</th>
                      <th>CNY</th>
                    </tr>
                  </thead>
                  <tbody>
                    {llmCost.models.map((m: any) => (
                      <tr key={m.model}>
                        <td>
                          {m.model}
                          {!m.priced && <span className="badge" style={{ marginLeft: 6 }}>未定价</span>}
                        </td>
                        <td className="mono">{m.requests}</td>
                        <td className="mono">{formatNumber(m.input_tokens)}</td>
                        <td className="mono">{formatNumber(m.output_tokens)}</td>
                        <td className="mono">${m.cost_usd.toFixed(4)}</td>
                        <td className="mono">¥{m.cost_cny.toFixed(4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}

      {trend && trend.points && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 24 }}>
            <h3 className="admin-section-title" style={{ margin: 0 }}>近 {trend.hours}h LLM 调用趋势</h3>
            <div className="log-filters" style={{ margin: 0 }}>
              <button
                className={trendMetric === 'tokens' ? 'btn btn-primary' : 'btn'}
                onClick={() => setTrendMetric('tokens')}
              >
                Token
              </button>
              <button
                className={trendMetric === 'cost' ? 'btn btn-primary' : 'btn'}
                onClick={() => setTrendMetric('cost')}
              >
                费用
              </button>
              <button
                className={trendMetric === 'requests' ? 'btn btn-primary' : 'btn'}
                onClick={() => setTrendMetric('requests')}
              >
                请求数
              </button>
            </div>
          </div>
          <div className="card" style={{ padding: 12, marginTop: 8 }}>
            <LlmTrendChart points={trend.points} hours={trend.hours} metric={trendMetric} />
          </div>
        </>
      )}

      <h3 className="admin-section-title">最近注册用户</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>用户名</th>
              <th>角色</th>
              <th>注册时间</th>
            </tr>
          </thead>
          <tbody>
            {stats.recent_users.map((u: any) => (
              <tr key={u.id}>
                <td className="mono">{u.id}</td>
                <td>{u.username}</td>
                <td>{u.is_admin ? <span className="badge badge-blue">管理员</span> : <span className="badge">普通用户</span>}</td>
                <td className="mono text-muted">{new Date(u.created_at).toLocaleString('zh-CN')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
