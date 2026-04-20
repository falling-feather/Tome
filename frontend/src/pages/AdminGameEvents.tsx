import React, { useEffect, useState } from 'react';
import { api } from '../api/client';

interface GameEvent {
  id: number;
  event_key: string;
  category: string;
  title: string;
  description: string;
  conditions: any;
  base_weight: number;
  cooldown_turns: number;
  effects: any;
  scenarios: string[];
}

const CATEGORY_OPTIONS = ['plot', 'combat', 'social', 'discovery', 'random', 'meta'];
const SCENARIO_OPTIONS = ['fantasy', 'scifi', 'wuxia'];

const blank: Omit<GameEvent, 'id'> = {
  event_key: '',
  category: 'plot',
  title: '',
  description: '',
  conditions: {},
  base_weight: 1.0,
  cooldown_turns: 3,
  effects: {},
  scenarios: [],
};

function jsonField(value: any): string {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return '{}';
  }
}

export function AdminGameEvents() {
  const [events, setEvents] = useState<GameEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterCategory, setFilterCategory] = useState('');
  const [filterScenario, setFilterScenario] = useState('');
  const [editing, setEditing] = useState<GameEvent | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<any>({ ...blank });
  const [conditionsText, setConditionsText] = useState('{}');
  const [effectsText, setEffectsText] = useState('{}');
  const [error, setError] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkRunning, setBulkRunning] = useState(false);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.getGameEvents({ category: filterCategory, scenario: filterScenario });
      setEvents(res.events);
    } catch (e: any) {
      setError(e.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [filterCategory, filterScenario]);
  useEffect(() => { setSelectedIds(new Set()); }, [filterCategory, filterScenario]);

  const allOnPageSelected = events.length > 0 && events.every((e) => selectedIds.has(e.id));
  const toggleAll = () => {
    if (allOnPageSelected) {
      const next = new Set(selectedIds);
      events.forEach((e) => next.delete(e.id));
      setSelectedIds(next);
    } else {
      const next = new Set(selectedIds);
      events.forEach((e) => next.add(e.id));
      setSelectedIds(next);
    }
  };
  const toggleOne = (id: number) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedIds(next);
  };
  const handleBulkDelete = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    if (!confirm(`确定批量删除 ${ids.length} 条事件？此操作不可恢复。`)) return;
    setBulkRunning(true);
    try {
      const res = await api.bulkGameEvents(ids, 'delete');
      alert(`已删除 ${res.affected}/${res.requested} 条`);
      setSelectedIds(new Set());
      await load();
    } catch (e: any) {
      alert(e.message || '批量删除失败');
    } finally {
      setBulkRunning(false);
    }
  };

  const startEdit = (ev: GameEvent) => {
    setEditing(ev);
    setCreating(false);
    setForm({ ...ev, scenarios: ev.scenarios || [] });
    setConditionsText(jsonField(ev.conditions));
    setEffectsText(jsonField(ev.effects));
  };

  const startCreate = () => {
    setCreating(true);
    setEditing(null);
    setForm({ ...blank });
    setConditionsText('{}');
    setEffectsText('{}');
  };

  const cancel = () => {
    setEditing(null);
    setCreating(false);
    setError('');
  };

  const handleSave = async () => {
    setError('');
    let conditions: any;
    let effects: any;
    try {
      conditions = JSON.parse(conditionsText || '{}');
    } catch {
      setError('conditions JSON 不合法');
      return;
    }
    try {
      effects = JSON.parse(effectsText || '{}');
    } catch {
      setError('effects JSON 不合法');
      return;
    }

    const payload = {
      ...form,
      conditions,
      effects,
      base_weight: Number(form.base_weight) || 0,
      cooldown_turns: Number(form.cooldown_turns) || 0,
    };

    try {
      if (editing) {
        await api.updateGameEvent(editing.id, payload);
      } else {
        await api.createGameEvent(payload);
      }
      cancel();
      load();
    } catch (e: any) {
      setError(e.message || '保存失败');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确定删除该事件？此操作不可恢复。')) return;
    try {
      await api.deleteGameEvent(id);
      load();
    } catch (e: any) {
      alert(e.message || '删除失败');
    }
  };

  const toggleScenario = (s: string) => {
    const current: string[] = form.scenarios || [];
    setForm({
      ...form,
      scenarios: current.includes(s) ? current.filter(x => x !== s) : [...current, s],
    });
  };

  return (
    <div className="admin-section">
      <div className="admin-header-row">
        <h2>事件池管理</h2>
        <button className="btn-primary" onClick={startCreate}>+ 新增事件</button>
      </div>

      <div className="admin-filters">
        <select value={filterCategory} onChange={e => setFilterCategory(e.target.value)}>
          <option value="">全部分类</option>
          {CATEGORY_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={filterScenario} onChange={e => setFilterScenario(e.target.value)}>
          <option value="">全部场景</option>
          {SCENARIO_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <span className="admin-count">共 {events.length} 条</span>
      </div>

      {selectedIds.size > 0 && (
        <div className="admin-filters" style={{ marginTop: 8 }}>
          <span className="admin-count" style={{ color: 'var(--primary)' }}>已选 {selectedIds.size} 条</span>
          <button className="btn-danger" disabled={bulkRunning} onClick={handleBulkDelete}>批量删除</button>
          <button disabled={bulkRunning} onClick={() => setSelectedIds(new Set())}>清除选择</button>
        </div>
      )}

      {error && <div className="admin-error">{error}</div>}

      {(editing || creating) && (
        <div className="world-entry-form">
          <h3>{editing ? `编辑: ${editing.title || editing.event_key}` : '新增事件'}</h3>
          <div className="form-grid">
            <label>事件 Key
              <input value={form.event_key} onChange={e => setForm({ ...form, event_key: e.target.value })} placeholder="例：fantasy_meet_merchant" />
            </label>
            <label>分类
              <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                {CATEGORY_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
            <label>标题
              <input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
            </label>
            <label>基础权重
              <input type="number" step="0.1" value={form.base_weight} onChange={e => setForm({ ...form, base_weight: e.target.value })} />
            </label>
            <label>冷却回合
              <input type="number" value={form.cooldown_turns} onChange={e => setForm({ ...form, cooldown_turns: e.target.value })} />
            </label>
            <label className="full-width">描述
              <textarea rows={2} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
            </label>
            <label className="full-width">适用场景
              <div className="scenario-toggles">
                {SCENARIO_OPTIONS.map(s => (
                  <label key={s} className="checkbox-inline">
                    <input
                      type="checkbox"
                      checked={(form.scenarios || []).includes(s)}
                      onChange={() => toggleScenario(s)}
                    />
                    {s}
                  </label>
                ))}
                <span className="hint">不勾选则全部场景通用</span>
              </div>
            </label>
            <label className="full-width">触发条件 (JSON)
              <textarea rows={4} value={conditionsText} onChange={e => setConditionsText(e.target.value)} spellCheck={false} />
            </label>
            <label className="full-width">效果 (JSON)
              <textarea rows={4} value={effectsText} onChange={e => setEffectsText(e.target.value)} spellCheck={false} />
            </label>
          </div>
          <div className="form-actions">
            <button className="btn-primary" onClick={handleSave}>保存</button>
            <button onClick={cancel}>取消</button>
          </div>
        </div>
      )}

      {loading ? <div className="admin-loading">加载中...</div> : (
        <table className="admin-table">
          <thead>
            <tr>
              <th style={{ width: 32 }}>
                <input
                  type="checkbox"
                  checked={allOnPageSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = !allOnPageSelected && events.some((e) => selectedIds.has(e.id));
                  }}
                  onChange={toggleAll}
                />
              </th>
              <th>ID</th><th>Key</th><th>分类</th><th>标题</th><th>权重</th><th>冷却</th><th>场景</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            {events.map(ev => (
              <tr key={ev.id}>
                <td>
                  <input
                    type="checkbox"
                    checked={selectedIds.has(ev.id)}
                    onChange={() => toggleOne(ev.id)}
                  />
                </td>
                <td>{ev.id}</td>
                <td><code>{ev.event_key}</code></td>
                <td>{ev.category}</td>
                <td>{ev.title}</td>
                <td>{ev.base_weight}</td>
                <td>{ev.cooldown_turns}</td>
                <td>{(ev.scenarios || []).join(', ') || '*'}</td>
                <td>
                  <button onClick={() => startEdit(ev)}>编辑</button>
                  <button className="btn-danger" onClick={() => handleDelete(ev.id)}>删除</button>
                </td>
              </tr>
            ))}
            {events.length === 0 && (
              <tr><td colSpan={9} className="admin-empty">暂无事件</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
