import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

export function AdminLogs() {
  const [logs, setLogs] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterAction, setFilterAction] = useState('');
  const [filterUser, setFilterUser] = useState('');
  const [loading, setLoading] = useState(true);
  const pageSize = 30;

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getAdminLogs({ page, page_size: pageSize, action: filterAction, username: filterUser });
      setLogs(data.logs);
      setTotal(data.total);
    } catch {}
    setLoading(false);
  }, [page, filterAction, filterUser]);

  useEffect(() => { loadLogs(); }, [loadLogs]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="fade-in">
      <h2 className="admin-section-title">操作日志</h2>

      <div className="log-filters">
        <input
          type="text"
          placeholder="按用户名筛选..."
          value={filterUser}
          onChange={(e) => { setFilterUser(e.target.value); setPage(1); }}
        />
        <select
          value={filterAction}
          onChange={(e) => { setFilterAction(e.target.value); setPage(1); }}
        >
          <option value="">全部操作</option>
          <option value="login">登录</option>
          <option value="login_failed">登录失败</option>
          <option value="register">注册</option>
          <option value="create_session">创建会话</option>
          <option value="delete_session">删除会话</option>
          <option value="game_action">游戏操作</option>
          <option value="update_apikey">更新API</option>
        </select>
        <button className="btn btn-sm" onClick={loadLogs}>刷新</button>
      </div>

      {loading ? (
        <div className="flex items-center gap-sm"><div className="spinner" /> 加载中...</div>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>时间</th>
                  <th>用户</th>
                  <th>操作</th>
                  <th>详情</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id}>
                    <td className="mono">{l.id}</td>
                    <td className="mono text-xs text-muted" style={{ whiteSpace: 'nowrap' }}>
                      {new Date(l.created_at).toLocaleString('zh-CN')}
                    </td>
                    <td>{l.username || '-'}</td>
                    <td>
                      <span className={`badge ${
                        l.action === 'login' ? 'badge-green' :
                        l.action === 'login_failed' ? 'badge-red' :
                        l.action === 'register' ? 'badge-blue' : ''
                      }`}>
                        {l.action}
                      </span>
                    </td>
                    <td className="text-sm" style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {l.detail}
                    </td>
                    <td className="mono text-xs text-muted">{l.ip_address}</td>
                  </tr>
                ))}
                {logs.length === 0 && (
                  <tr><td colSpan={6} style={{ textAlign: 'center', padding: 24 }} className="text-muted">暂无日志</td></tr>
                )}
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
