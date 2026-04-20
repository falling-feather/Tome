import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError(t('login.empty'));
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
      setError(err.message || t('login.failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <h1>{t('login.title')}</h1>
          <div className="sub">{t('login.subtitle')}</div>
        </div>

        <div className="login-tabs">
          <button className={`login-tab ${mode === 'login' ? 'active' : ''}`} onClick={() => { setMode('login'); setError(''); }}>
            {t('login.tabLogin')}
          </button>
          <button className={`login-tab ${mode === 'register' ? 'active' : ''}`} onClick={() => { setMode('register'); setError(''); }}>
            {t('login.tabRegister')}
          </button>
        </div>

        {error && <div className="login-error">{error}</div>}

        <form className="login-form" onSubmit={handleSubmit}>
          <div className="form-field">
            <label>{t('login.usernameLabel')}</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t('login.usernamePlaceholder')}
              autoComplete="username"
              autoFocus
            />
          </div>
          <div className="form-field">
            <label>{t('login.passwordLabel')}</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t('login.passwordPlaceholder')}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? <span className="spinner" /> : (mode === 'login' ? t('login.submit') : t('login.submitRegister'))}
          </button>
        </form>

        <div className="login-footer">
          {mode === 'login'
            ? <span>{t('login.toRegister')} <a onClick={() => setMode('register')}>{t('login.toRegisterAction')}</a></span>
            : <span>{t('login.toLogin')} <a onClick={() => setMode('login')}>{t('login.toLoginAction')}</a></span>
          }
        </div>
      </div>
    </div>
  );
}
