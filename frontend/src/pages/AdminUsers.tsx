import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import { useAuth } from '../stores/auth';

export function AdminUsers() {
  const { username: selfName } = useAuth();
  const [users, setUsers] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkRunning, setBulkRunning] = useState(false);
  const pageSize = 50;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getAdminUsers({ page });
      setUsers(data.users);
      setTotal(data.total);
    } catch {}
    setLoading(false);
  }, [page]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setSelectedIds(new Set()); }, [page]);

  const totalPages = Math.ceil(total / pageSize);

  const selectableUsers = users.filter((u) => u.username !== selfName);
  const allOnPageSelected = selectableUsers.length > 0 && selectableUsers.every((u) => selectedIds.has(u.id));
  const toggleAll = () => {
    if (allOnPageSelected) {
      const next = new Set(selectedIds);
      selectableUsers.forEach((u) => next.delete(u.id));
      setSelectedIds(next);
    } else {
      const next = new Set(selectedIds);
      selectableUsers.forEach((u) => next.add(u.id));
      setSelectedIds(next);
    }
  };
  const toggleOne = (id: number) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedIds(next);
  };
  const runBulk = async (action: 'promote' | 'demote') => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    const verb = action === 'promote' ? '设为管理员' : '取消管理员';
    if (!confirm(`确定将 ${ids.length} 位用户${verb}？`)) return;
    setBulkRunning(true);
    try {
      const res = await api.bulkUsers(ids, action);
      alert(`已${verb} ${res.affected}/${res.requested} 位`);
      setSelectedIds(new Set());
      await load();
    } catch (e: any) {
      alert(e.message || '批量操作失败');
    } finally {
      setBulkRunning(false);
    }
  };

  return (
    <div className="fade-in">
      <h2 className="admin-section-title">用户管理</h2>
      {loading ? (
        <div className="flex items-center gap-sm"><div className="spinner" /> 加载中...</div>
      ) : (
        <>
          {selectedIds.size > 0 && (
            <div className="admin-filters" style={{ marginBottom: 8 }}>
              <span className="admin-count" style={{ color: 'var(--primary)' }}>已选 {selectedIds.size} 位</span>
              <button className="btn btn-sm btn-primary" disabled={bulkRunning} onClick={() => runBulk('promote')}>设为管理员</button>
              <button className="btn btn-sm" disabled={bulkRunning} onClick={() => runBulk('demote')}>取消管理员</button>
              <button className="btn btn-sm" disabled={bulkRunning} onClick={() => setSelectedIds(new Set())}>清除选择</button>
            </div>
          )}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th style={{ width: 32 }}>
                    <input
                      type="checkbox"
                      checked={allOnPageSelected}
                      ref={(el) => {
                        if (el) el.indeterminate = !allOnPageSelected && selectableUsers.some((u) => selectedIds.has(u.id));
                      }}
                      onChange={toggleAll}
                      disabled={selectableUsers.length === 0}
                    />
                  </th>
                  <th>ID</th>
                  <th>用户名</th>
                  <th>角色</th>
                  <th>注册时间</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(u.id)}
                        onChange={() => toggleOne(u.id)}
                        disabled={u.username === selfName}
                        title={u.username === selfName ? '不能选择自己' : ''}
                      />
                    </td>
                    <td className="mono">{u.id}</td>
                    <td>{u.username}</td>
                    <td>
                      {u.is_admin
                        ? <span className="badge badge-blue">管理员</span>
                        : <span className="badge">用户</span>}
                    </td>
                    <td className="mono text-muted text-xs">{new Date(u.created_at).toLocaleString('zh-CN')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination">
            <span className="page-info">共 {total} 条 · 第 {page}/{totalPages || 1} 页</span>
            <div className="page-btns">
              <button className="btn btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
              <button className="btn btn-sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一页</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
