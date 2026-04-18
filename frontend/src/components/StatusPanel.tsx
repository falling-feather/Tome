import React from 'react';

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  exploring: { label: '探索中', color: 'var(--accent)' },
  combat: { label: '战斗中', color: 'var(--error)' },
  resting: { label: '休息中', color: 'var(--success)' },
  trading: { label: '交易中', color: 'var(--warning)' },
  dialogue: { label: '对话中', color: '#8b5cf6' },
  dead: { label: '已死亡', color: 'var(--text-muted)' },
};

interface StatusPanelProps {
  state: any;
}

export function StatusPanel({ state }: StatusPanelProps) {
  if (!state || !state.character_name) return null;

  const hp = state.health || 0;
  const maxHp = state.max_health || 100;
  const hpPercent = Math.round((hp / maxHp) * 100);
  const fatigue = state.fatigue || 0;
  const status = state.status || 'exploring';
  const statusInfo = STATUS_LABELS[status] || STATUS_LABELS.exploring;
  const inventory: string[] = state.inventory || [];
  const questFlags: Record<string, boolean> = state.quest_flags || {};

  return (
    <div className="status-panel">
      <div className="status-section">
        <h4>角色</h4>
        <div className="stat-row">
          <span className="stat-label">名称</span>
          <span className="stat-value">{state.character_name}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">职业</span>
          <span className="stat-value">{state.character_class}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">位置</span>
          <span className="stat-value">{state.current_location}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">状态</span>
          <span className="stat-value">
            <span className="status-badge" style={{ borderColor: statusInfo.color, color: statusInfo.color }}>
              {statusInfo.label}
            </span>
          </span>
        </div>
      </div>

      <div className="status-section">
        <h4>状态</h4>
        <div className="stat-row">
          <span className="stat-label">生命值</span>
          <span className="stat-value" style={hpPercent <= 25 ? { color: 'var(--error)' } : undefined}>{hp}/{maxHp}</span>
        </div>
        <div className="stat-bar">
          <div className={`stat-bar-fill hp ${hpPercent <= 25 ? 'critical' : hpPercent < 50 ? 'low' : ''}`} style={{ width: `${hpPercent}%` }} />
        </div>

        <div className="stat-row" style={{ marginTop: 8 }}>
          <span className="stat-label">疲劳度</span>
          <span className="stat-value" style={fatigue >= 80 ? { color: 'var(--error)' } : undefined}>{fatigue}/100</span>
        </div>
        <div className="stat-bar">
          <div className={`stat-bar-fill fatigue ${fatigue >= 80 ? 'critical' : fatigue > 60 ? 'low' : ''}`} style={{ width: `${fatigue}%` }} />
        </div>
      </div>

      <div className="status-section">
        <h4>资源</h4>
        <div className="stat-row">
          <span className="stat-label">金币</span>
          <span className="stat-value">{state.money || 0}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">物品</span>
          <span className="stat-value">{inventory.length}</span>
        </div>
        {inventory.length > 0 && (
          <div className="inventory-list">
            {inventory.slice(0, 6).map((item, i) => (
              <span key={i} className="inventory-tag">{item}</span>
            ))}
            {inventory.length > 6 && <span className="inventory-tag more">+{inventory.length - 6}</span>}
          </div>
        )}
      </div>

      <div className="status-section">
        <h4>进度</h4>
        <div className="stat-row">
          <span className="stat-label">回合</span>
          <span className="stat-value">{state.turn || 0}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">章节</span>
          <span className="stat-value">第{state.chapter || 1}章</span>
        </div>
      </div>

      {Object.keys(questFlags).length > 0 && (
        <div className="status-section">
          <h4>任务线索</h4>
          <div className="quest-list">
            {Object.keys(questFlags).slice(0, 5).map((flag) => (
              <div key={flag} className="quest-item">
                <span className="quest-dot" />
                <span>{flag.replace(/_/g, ' ')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

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
