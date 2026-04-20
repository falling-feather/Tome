import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../api/client';

const SCENARIO_KEYS: Record<string, string> = {
  '*': 'worldBook.scenarioAll', fantasy: 'worldBook.scenarioFantasy',
  scifi: 'worldBook.scenarioScifi', wuxia: 'worldBook.scenarioWuxia',
};
const LAYER_KEYS: Record<string, string> = {
  core: 'worldBook.layerCore', chapter: 'worldBook.layerChapter', ephemeral: 'worldBook.layerEphemeral',
};
const CATEGORY_OPTIONS = ['lore', 'character', 'location', 'faction', 'item', 'rule'];

interface WorldEntry {
  id: number; scenario: string; layer: string; category: string;
  title: string; keywords: string; content: string;
  chapter_min: number; chapter_max: number; priority: number; is_active: boolean;
}

export function AdminWorldBook() {
  const { t } = useTranslation();
  const [entries, setEntries] = useState<WorldEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterScenario, setFilterScenario] = useState('');
  const [filterLayer, setFilterLayer] = useState('');
  const [editing, setEditing] = useState<WorldEntry | null>(null);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkRunning, setBulkRunning] = useState(false);

  const blankEntry: Omit<WorldEntry, 'id'> = {
    scenario: '*', layer: 'core', category: 'lore', title: '', keywords: '',
    content: '', chapter_min: 0, chapter_max: 0, priority: 0, is_active: true,
  };
  const [form, setForm] = useState<any>({ ...blankEntry });

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.getWorldEntries({ scenario: filterScenario, layer: filterLayer, page });
      setEntries(res.entries);
      setTotal(res.total);
    } catch (e: any) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, [page, filterScenario, filterLayer]);

  const handleSave = async () => {
    try {
      if (editing) {
        await api.updateWorldEntry(editing.id, form);
      } else {
        await api.createWorldEntry(form);
      }
      setEditing(null);
      setCreating(false);
      setForm({ ...blankEntry });
      load();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确定删除此条目？')) return;
    try {
      await api.deleteWorldEntry(id);
      load();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const startEdit = (entry: WorldEntry) => {
    setEditing(entry);
    setCreating(false);
    setForm({ ...entry });
  };

  const startCreate = () => {
    setCreating(true);
    setEditing(null);
    setForm({ ...blankEntry });
  };

  const totalPages = Math.ceil(total / 50);

  // 选择状态在分页/筛选切换后重置
  useEffect(() => { setSelectedIds(new Set()); }, [page, filterScenario, filterLayer]);

  const allOnPageSelected = entries.length > 0 && entries.every((e) => selectedIds.has(e.id));
  const togglePageSelection = () => {
    if (allOnPageSelected) {
      const next = new Set(selectedIds);
      entries.forEach((e) => next.delete(e.id));
      setSelectedIds(next);
    } else {
      const next = new Set(selectedIds);
      entries.forEach((e) => next.add(e.id));
      setSelectedIds(next);
    }
  };
  const toggleOne = (id: number) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedIds(next);
  };

  const runBulk = async (action: 'enable' | 'disable' | 'delete') => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    const verb = action === 'enable' ? '启用' : action === 'disable' ? '禁用' : '删除';
    if (!confirm(`确认${verb}选中的 ${ids.length} 条？${action === 'delete' ? '此操作不可撤销。' : ''}`)) return;
    setBulkRunning(true);
    try {
      const r = await api.bulkWorldEntries(ids, action);
      alert(`完成：${verb} ${r.affected} / ${r.requested} 条`);
      setSelectedIds(new Set());
      load();
    } catch (e: any) {
      alert(e.message || '失败');
    } finally {
      setBulkRunning(false);
    }
  };

  return (
    <div className="admin-section">
      <div className="admin-header-row">
        <h2>世界书管理</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={async () => {
              if (!confirm('对所有未生成嵌入的条目批量调用 embeddings API，可能产生少量费用，是否继续？')) return;
              try {
                const r = await api.reembedWorldEntries();
                alert(`完成：处理 ${r.processed} 条，成功 ${r.success} 条，跳过 ${r.skipped} 条`);
                load();
              } catch (e: any) {
                alert(e.message || '失败');
              }
            }}
          >▤ 批量重嵌入</button>
          <button className="btn-primary" onClick={startCreate}>+ 新增条目</button>
        </div>
      </div>

      <div className="admin-filters">
        <select value={filterScenario} onChange={e => { setFilterScenario(e.target.value); setPage(1); }}>
          <option value="">全部场景</option>
          {Object.entries(SCENARIO_KEYS).map(([k, v]) => (
            <option key={k} value={k}>{t(v)}</option>
          ))}
        </select>
        <select value={filterLayer} onChange={e => { setFilterLayer(e.target.value); setPage(1); }}>
          <option value="">全部层级</option>
          {Object.entries(LAYER_KEYS).map(([k, v]) => (
            <option key={k} value={k}>{t(v)}</option>
          ))}
        </select>
        <span className="admin-count">共 {total} 条</span>
        {selectedIds.size > 0 && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, marginLeft: 12 }}>
            <span className="admin-count" style={{ color: 'var(--primary)' }}>已选 {selectedIds.size} 条</span>
            <button className="btn-sm" disabled={bulkRunning} onClick={() => runBulk('enable')}>批量启用</button>
            <button className="btn-sm" disabled={bulkRunning} onClick={() => runBulk('disable')}>批量禁用</button>
            <button className="btn-sm btn-danger" disabled={bulkRunning} onClick={() => runBulk('delete')}>批量删除</button>
            <button className="btn-sm" disabled={bulkRunning} onClick={() => setSelectedIds(new Set())}>清除选择</button>
          </span>
        )}
      </div>

      {(editing || creating) && (
        <div className="world-entry-form">
          <h3>{editing ? `编辑: ${editing.title}` : '新增条目'}</h3>
          <div className="form-grid">
            <label>标题
              <input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
            </label>
            <label>场景
              <select value={form.scenario} onChange={e => setForm({ ...form, scenario: e.target.value })}>
                {Object.entries(SCENARIO_KEYS).map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
              </select>
            </label>
            <label>层级
              <select value={form.layer} onChange={e => setForm({ ...form, layer: e.target.value })}>
                {Object.entries(LAYER_KEYS).map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
              </select>
            </label>
            <label>分类
              <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                {CATEGORY_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
            <label>关键词 (逗号分隔)
              <input value={form.keywords} onChange={e => setForm({ ...form, keywords: e.target.value })} />
            </label>
            <label>优先级
              <input type="number" value={form.priority} onChange={e => setForm({ ...form, priority: parseInt(e.target.value) || 0 })} />
            </label>
            <label>章节范围 (最小)
              <input type="number" value={form.chapter_min} onChange={e => setForm({ ...form, chapter_min: parseInt(e.target.value) || 0 })} />
            </label>
            <label>章节范围 (最大)
              <input type="number" value={form.chapter_max} onChange={e => setForm({ ...form, chapter_max: parseInt(e.target.value) || 0 })} />
            </label>
          </div>
          <label className="form-full">内容
            <textarea rows={5} value={form.content} onChange={e => setForm({ ...form, content: e.target.value })} />
          </label>
          <div className="form-actions">
            <button className="btn-primary" onClick={handleSave}>保存</button>
            <button className="btn-secondary" onClick={() => { setEditing(null); setCreating(false); }}>取消</button>
          </div>
        </div>
      )}

      <table className="admin-table">
        <thead>
          <tr>
            <th style={{ width: 32 }}>
              <input
                type="checkbox"
                checked={allOnPageSelected}
                ref={(el) => {
                  if (el) el.indeterminate = !allOnPageSelected && entries.some((e) => selectedIds.has(e.id));
                }}
                onChange={togglePageSelection}
                aria-label="全选当前页"
              />
            </th>
            <th>标题</th>
            <th>场景</th>
            <th>层级</th>
            <th>分类</th>
            <th>优先级</th>
            <th>章节</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr><td colSpan={8} style={{ textAlign: 'center' }}>加载中...</td></tr>
          ) : entries.map(e => (
            <tr key={e.id} style={{ opacity: e.is_active ? 1 : 0.5 }}>
              <td>
                <input
                  type="checkbox"
                  checked={selectedIds.has(e.id)}
                  onChange={() => toggleOne(e.id)}
                  aria-label={`选择 ${e.title}`}
                />
              </td>
              <td title={e.content}>{e.title}</td>
              <td>{SCENARIO_KEYS[e.scenario] ? t(SCENARIO_KEYS[e.scenario]) : e.scenario}</td>
              <td>{LAYER_KEYS[e.layer] ? t(LAYER_KEYS[e.layer]) : e.layer}</td>
              <td>{e.category}</td>
              <td>{e.priority}</td>
              <td>{e.chapter_min || '-'} ~ {e.chapter_max || '-'}</td>
              <td>
                <button className="btn-sm" onClick={() => startEdit(e)}>编辑</button>
                <button className="btn-sm btn-danger" onClick={() => handleDelete(e.id)}>删除</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {totalPages > 1 && (
        <div className="admin-pagination">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</button>
          <span>{page} / {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>下一页</button>
        </div>
      )}
    </div>
  );
}
