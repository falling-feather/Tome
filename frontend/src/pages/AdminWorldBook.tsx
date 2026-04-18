import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

const SCENARIO_LABELS: Record<string, string> = {
  '*': '通用', fantasy: '奇幻', scifi: '科幻', wuxia: '武侠',
};
const LAYER_LABELS: Record<string, string> = {
  core: '核心', chapter: '章节', ephemeral: '临时',
};
const CATEGORY_OPTIONS = ['lore', 'character', 'location', 'faction', 'item', 'rule'];

interface WorldEntry {
  id: number; scenario: string; layer: string; category: string;
  title: string; keywords: string; content: string;
  chapter_min: number; chapter_max: number; priority: number; is_active: boolean;
}

export function AdminWorldBook() {
  const [entries, setEntries] = useState<WorldEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterScenario, setFilterScenario] = useState('');
  const [filterLayer, setFilterLayer] = useState('');
  const [editing, setEditing] = useState<WorldEntry | null>(null);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(false);

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

  return (
    <div className="admin-section">
      <div className="admin-header-row">
        <h2>世界书管理</h2>
        <button className="btn-primary" onClick={startCreate}>+ 新增条目</button>
      </div>

      <div className="admin-filters">
        <select value={filterScenario} onChange={e => { setFilterScenario(e.target.value); setPage(1); }}>
          <option value="">全部场景</option>
          {Object.entries(SCENARIO_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <select value={filterLayer} onChange={e => { setFilterLayer(e.target.value); setPage(1); }}>
          <option value="">全部层级</option>
          {Object.entries(LAYER_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <span className="admin-count">共 {total} 条</span>
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
                {Object.entries(SCENARIO_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label>层级
              <select value={form.layer} onChange={e => setForm({ ...form, layer: e.target.value })}>
                {Object.entries(LAYER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
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
            <tr><td colSpan={7} style={{ textAlign: 'center' }}>加载中...</td></tr>
          ) : entries.map(e => (
            <tr key={e.id} style={{ opacity: e.is_active ? 1 : 0.5 }}>
              <td title={e.content}>{e.title}</td>
              <td>{SCENARIO_LABELS[e.scenario] || e.scenario}</td>
              <td>{LAYER_LABELS[e.layer] || e.layer}</td>
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
