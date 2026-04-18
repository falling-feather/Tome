import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

export function AdminDashboard() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getAdminStats().then(setStats).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center gap-sm"><div className="spinner" /> 加载中...</div>;
  if (!stats) return <div>加载失败</div>;

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
