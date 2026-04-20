import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../api/client';
import { LlmTrendChart } from '../components/LlmTrendChart';

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

function CostAlertBanner({ alerts }: { alerts: any }) {
  const { t } = useTranslation();
  const items: { label: string; data: any }[] = [
    { label: t('admin.alertDaily'), data: alerts.daily },
    { label: t('admin.alertMonthly'), data: alerts.monthly },
  ];
  const visible = items.filter((it) => it.data && it.data.level !== 'off' && it.data.level !== 'ok');
  if (visible.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
      {visible.map((it) => {
        const bg = it.data.level === 'breached' ? 'rgba(220, 38, 38, 0.12)' : 'rgba(245, 158, 11, 0.12)';
        const border = it.data.level === 'breached' ? 'var(--error)' : 'var(--warning)';
        const color = it.data.level === 'breached' ? 'var(--error)' : 'var(--warning)';
        const pct = Math.round(it.data.ratio * 100);
        return (
          <div
            key={it.label}
            style={{
              padding: '10px 14px',
              border: `1px solid ${border}`,
              background: bg,
              color,
              borderRadius: 'var(--radius-sm)',
              fontSize: 13,
            }}
          >
            <strong>{it.label} {t('admin.alertLlmCost')}</strong>
            {' '}
            {it.data.level === 'breached' ? t('admin.alertBreached') : t('admin.alertWarn')}:
            <span className="mono"> ${it.data.used_usd.toFixed(4)}</span> /
            <span className="mono"> ${it.data.limit_usd.toFixed(4)}</span>
            {' '}({pct}%, {t('admin.alertRemaining')} <span className="mono">${it.data.remaining_usd.toFixed(4)}</span>)
          </div>
        );
      })}
    </div>
  );
}

export function AdminDashboard() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [trend, setTrend] = useState<any>(null);
  const [trendMetric, setTrendMetric] = useState<'tokens' | 'cost' | 'requests'>('tokens');
  const [trendHours, setTrendHours] = useState<number>(24);
  const [trendLoading, setTrendLoading] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
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

  // 切换时间范围
  useEffect(() => {
    if (loading) return;
    setTrendLoading(true);
    api.getLlmTrend(trendHours)
      .then((t) => setTrend(t))
      .catch(() => {})
      .finally(() => setTrendLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trendHours]);

  // 关闭菜单
  useEffect(() => {
    if (!menuOpen) return;
    const handler = () => setMenuOpen(false);
    window.addEventListener('click', handler);
    return () => window.removeEventListener('click', handler);
  }, [menuOpen]);

  if (loading) return <div className="flex items-center gap-sm"><div className="spinner" /> {t('common.loading')}</div>;
  if (!stats) return <div>{t('common.loadFailed')}</div>;

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
      {health && health.cost_alerts && (
        <CostAlertBanner alerts={health.cost_alerts} />
      )}
      <h2 className="admin-section-title">{t('admin.overview')}</h2>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-title">{t('admin.kpiTotalUsers')}</div>
          <div className="stat-number">{stats.total_users}</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">{t('admin.kpiSessions')}</div>
          <div className="stat-number">{stats.total_sessions}</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">{t('admin.kpiMessages')}</div>
          <div className="stat-number">{stats.total_messages}</div>
        </div>
        <div className="stat-card">
          <div className="stat-title">日志条目</div>
          <div className="stat-number">{stats.total_logs}</div>
        </div>
      </div>

      {health && (
        <>
          <h3 className="admin-section-title">{t('admin.llmSection')}</h3>
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
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 24, gap: 8, flexWrap: 'wrap' }}>
            <h3 className="admin-section-title" style={{ margin: 0 }}>
              {t('admin.trendTitle', { label: trendHours >= 24 ? t('admin.rangeDay', { n: Math.round(trendHours / 24) }) : t('admin.rangeHour', { n: trendHours }) })}
              {trendLoading && <span className="admin-meta" style={{ marginLeft: 8 }}>{t('admin.trendLoading')}</span>}
            </h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <div className="log-filters" style={{ margin: 0 }}>
                {[
                  { v: 24, label: '24h' },
                  { v: 24 * 7, label: '7d' },
                  { v: 24 * 30, label: '30d' },
                ].map((o) => (
                  <button
                    key={o.v}
                    className={trendHours === o.v ? 'btn btn-primary' : 'btn'}
                    onClick={() => setTrendHours(o.v)}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
              <div className="log-filters" style={{ margin: 0 }}>
                <button
                  className={trendMetric === 'tokens' ? 'btn btn-primary' : 'btn'}
                  onClick={() => setTrendMetric('tokens')}
                >
                  {t('admin.metricTokens')}
                </button>
                <button
                  className={trendMetric === 'cost' ? 'btn btn-primary' : 'btn'}
                  onClick={() => setTrendMetric('cost')}
                >
                  {t('admin.metricCost')}
                </button>
                <button
                  className={trendMetric === 'requests' ? 'btn btn-primary' : 'btn'}
                  onClick={() => setTrendMetric('requests')}
                >
                  {t('admin.metricRequests')}
                </button>
              </div>
              <div style={{ position: 'relative' }} onClick={(e) => e.stopPropagation()}>
                <button
                  className="btn"
                  onClick={() => setMenuOpen((v) => !v)}
                  aria-label={t('common.more')}
                  title={t('common.more')}
                >
                  ⋯
                </button>
                {menuOpen && (
                  <div
                    style={{
                      position: 'absolute',
                      right: 0,
                      top: 'calc(100% + 4px)',
                      background: 'var(--bg-elevated)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-sm)',
                      boxShadow: 'var(--shadow-md)',
                      padding: 4,
                      minWidth: 180,
                      zIndex: 50,
                    }}
                  >
                    {[
                      { label: t('admin.menuExportCsv'), act: () => api.exportLlmUsage(Math.max(1, Math.round(trendHours / 24)), 'csv') },
                      { label: t('admin.menuExportJson'), act: () => api.exportLlmUsage(Math.max(1, Math.round(trendHours / 24)), 'json') },
                      {
                        label: t('admin.menuCopyJson'),
                        act: async () => {
                          await navigator.clipboard.writeText(JSON.stringify(trend, null, 2));
                          alert(t('admin.menuCopied'));
                        },
                      },
                      { label: t('common.refresh'), act: () => { setTrendHours((h) => h); api.getLlmTrend(trendHours).then(setTrend).catch(() => {}); } },
                    ].map((it) => (
                      <button
                        key={it.label}
                        className="btn"
                        style={{ display: 'block', width: '100%', textAlign: 'left', background: 'transparent', border: 'none', padding: '6px 10px' }}
                        onClick={() => { setMenuOpen(false); Promise.resolve(it.act()).catch((e) => alert(String(e))); }}
                      >
                        {it.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
          <div className="card" style={{ padding: 12, marginTop: 8 }}>
            <LlmTrendChart points={trend.points} hours={trend.hours} metric={trendMetric} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
            <span className="admin-meta">{t('admin.exportRecent')}</span>
            {[1, 7, 30].map((d) => (
              <button
                key={`csv-${d}`}
                className="btn"
                onClick={() => api.exportLlmUsage(d, 'csv').catch((e) => alert(String(e)))}
              >
                {t('admin.exportNDayCsv', { n: d })}
              </button>
            ))}
            {[1, 7, 30].map((d) => (
              <button
                key={`json-${d}`}
                className="btn"
                onClick={() => api.exportLlmUsage(d, 'json').catch((e) => alert(String(e)))}
              >
                {t('admin.exportNDayJson', { n: d })}
              </button>
            ))}
          </div>
        </>
      )}

      <h3 className="admin-section-title">{t('admin.recentUsers')}</h3>
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
