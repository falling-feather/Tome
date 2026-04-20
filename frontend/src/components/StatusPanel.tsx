import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

const STATUS_META: Record<string, { key: string; color: string }> = {
  exploring: { key: 'exploring', color: 'var(--accent)' },
  combat: { key: 'combat', color: 'var(--error)' },
  resting: { key: 'resting', color: 'var(--success)' },
  trading: { key: 'trading', color: 'var(--warning)' },
  dialogue: { key: 'dialogue', color: '#8b5cf6' },
  dead: { key: 'dead', color: 'var(--text-muted)' },
};

type TabKey = 'status' | 'resource' | 'progress';

interface StatusPanelProps {
  state: any;
}

export function StatusPanel({ state }: StatusPanelProps) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabKey>('status');

  if (!state || !state.character_name) return null;

  const hp = state.health || 0;
  const maxHp = state.max_health || 100;
  const hpPercent = Math.round((hp / maxHp) * 100);
  const fatigue = state.fatigue || 0;
  const status = state.status || 'exploring';
  const statusInfo = STATUS_META[status] || STATUS_META.exploring;
  const inventory: string[] = state.inventory || [];
  const questFlags: Record<string, boolean> = state.quest_flags || {};
  const questCount = Object.keys(questFlags).length;

  const tabs: { key: TabKey; label: string; badge?: string | number }[] = [
    { key: 'status', label: t('statusPanel.tabStatus') },
    { key: 'resource', label: t('statusPanel.tabResource'), badge: inventory.length || undefined },
    { key: 'progress', label: t('statusPanel.tabProgress'), badge: questCount || undefined },
  ];

  return (
    <div className="status-panel">
      <div className="status-header">
        <div className="status-character">
          <div className="character-name">{state.character_name}</div>
          <div className="character-meta">
            {state.character_class}{state.current_location ? ` · ${state.current_location}` : ''}
          </div>
        </div>
        <span
          className="status-badge"
          style={{ borderColor: statusInfo.color, color: statusInfo.color }}
        >
          {t(`statusPanel.${statusInfo.key}`)}
        </span>
      </div>

      <div className="status-tabs" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            className={`status-tab${tab === t.key ? ' active' : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
            {t.badge != null && <span className="status-tab-badge">{t.badge}</span>}
          </button>
        ))}
      </div>

      <div className="status-tab-panel" role="tabpanel">
        {tab === 'status' && (
          <>
            <div className="stat-row">
              <span className="stat-label">生命值</span>
              <span
                className="stat-value"
                style={hpPercent <= 25 ? { color: 'var(--error)' } : undefined}
              >
                {hp}/{maxHp}
              </span>
            </div>
            <div className="stat-bar">
              <div
                className={`stat-bar-fill hp ${hpPercent <= 25 ? 'critical' : hpPercent < 50 ? 'low' : ''}`}
                style={{ width: `${hpPercent}%` }}
              />
            </div>

            <div className="stat-row" style={{ marginTop: 12 }}>
              <span className="stat-label">疲劳度</span>
              <span
                className="stat-value"
                style={fatigue >= 80 ? { color: 'var(--error)' } : undefined}
              >
                {fatigue}/100
              </span>
            </div>
            <div className="stat-bar">
              <div
                className={`stat-bar-fill fatigue ${fatigue >= 80 ? 'critical' : fatigue > 60 ? 'low' : ''}`}
                style={{ width: `${fatigue}%` }}
              />
            </div>
          </>
        )}

        {tab === 'resource' && (
          <>
            <div className="stat-row">
              <span className="stat-label">金币</span>
              <span className="stat-value">{state.money || 0}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">物品数</span>
              <span className="stat-value">{inventory.length}</span>
            </div>
            {inventory.length > 0 ? (
              <div className="inventory-list" style={{ marginTop: 8 }}>
                {inventory.map((item, i) => (
                  <span key={i} className="inventory-tag">{item}</span>
                ))}
              </div>
            ) : (
              <div className="status-empty">背包空空如也</div>
            )}
          </>
        )}

        {tab === 'progress' && (
          <>
            <div className="stat-row">
              <span className="stat-label">回合</span>
              <span className="stat-value">{state.turn || 0}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">章节</span>
              <span className="stat-value">第{state.chapter || 1}章</span>
            </div>
            {questCount > 0 ? (
              <>
                <div className="stat-row" style={{ marginTop: 12 }}>
                  <span className="stat-label">任务线索</span>
                  <span className="stat-value">{questCount}</span>
                </div>
                <div className="quest-list">
                  {Object.keys(questFlags).map((flag) => (
                    <div key={flag} className="quest-item">
                      <span className="quest-dot" />
                      <span>{flag.replace(/_/g, ' ')}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="status-empty" style={{ marginTop: 12 }}>暂无线索</div>
            )}
          </>
        )}
      </div>

      {status === 'dead' && (
        <div className="death-notice">
          <div className="death-icon">💀</div>
          <p>你的冒险已经结束</p>
          <p className="death-hint">请创建新的冒险继续</p>
        </div>
      )}
    </div>
  );
}
