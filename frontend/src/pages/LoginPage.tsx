import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../stores/auth';
import '../styles/login.css';

export function LoginPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('请填写用户名和密码');
      return;
    }
    setError('');
    setLoading(true);
    try {
      if (mode === 'login') {
        await login(username, password);
      } else {
        await register(username, password);
      }
      // Check if admin to redirect
      const isAdmin = localStorage.getItem('isAdmin') === 'true';
      navigate(isAdmin ? '/admin' : '/game', { replace: true });
    } catch (err: any) {
      setError(err.message || '操作失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <h1>不 存 在 之 书</h1>
          <div className="sub">Inkless — AI Interactive Narrative</div>
        </div>

        <div className="login-tabs">
          <button className={`login-tab ${mode === 'login' ? 'active' : ''}`} onClick={() => { setMode('login'); setError(''); }}>
            登录
          </button>
          <button className={`login-tab ${mode === 'register' ? 'active' : ''}`} onClick={() => { setMode('register'); setError(''); }}>
            注册
          </button>
        </div>

        {error && <div className="login-error">{error}</div>}

        <form className="login-form" onSubmit={handleSubmit}>
          <div className="form-field">
            <label>用户名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="输入用户名"
              autoComplete="username"
              autoFocus
            />
          </div>
          <div className="form-field">
            <label>密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="输入密码"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? <span className="spinner" /> : (mode === 'login' ? '登录' : '注册')}
          </button>
        </form>

        <div className="login-footer">
          {mode === 'login'
            ? <span>没有账号？<a onClick={() => setMode('register')}>注册新账号</a></span>
            : <span>已有账号？<a onClick={() => setMode('login')}>返回登录</a></span>
          }
        </div>
      </div>
    </div>
  );
}
