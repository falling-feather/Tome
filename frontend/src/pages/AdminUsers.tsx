import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

export function AdminUsers() {
  const [users, setUsers] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
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

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="fade-in">
      <h2 className="admin-section-title">用户管理</h2>
      {loading ? (
        <div className="flex items-center gap-sm"><div className="spinner" /> 加载中...</div>
      ) : (
        <>
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
                {users.map((u) => (
                  <tr key={u.id}>
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
