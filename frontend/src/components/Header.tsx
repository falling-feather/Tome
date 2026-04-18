import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../stores/auth';

function getInitialTheme(): 'light' | 'dark' {
  const saved = localStorage.getItem('theme');
  if (saved === 'dark' || saved === 'light') return saved;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function Header() {
  const { username, isAdmin, logout } = useAuth();
  const location = useLocation();
  const [mobileNav, setMobileNav] = useState(false);
  const [theme, setTheme] = useState<'light' | 'dark'>(getInitialTheme);

  const isActive = (path: string) => location.pathname.startsWith(path) ? 'active' : '';

  // Close mobile nav on route change
  useEffect(() => { setMobileNav(false); }, [location.pathname]);

  // Apply theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => t === 'light' ? 'dark' : 'light');

  return (
    <header className="app-header">
      <div className="header-left">
        <button className="mobile-menu-btn" onClick={() => setMobileNav(!mobileNav)} aria-label="菜单">
          {mobileNav ? '✕' : '☰'}
        </button>
        <div className="header-logo">
          <span className="logo-icon">📖</span>
          不存在之书
        </div>
        <nav className={`header-nav${mobileNav ? ' mobile-open' : ''}`}>
          {isAdmin ? (
            <>
              <Link to="/admin" className={isActive('/admin')}>控制台</Link>
              <Link to="/game" className={isActive('/game')}>冒险</Link>
            </>
          ) : (
            <Link to="/game" className={isActive('/game')}>冒险</Link>
          )}
          <Link to="/stories" className={isActive('/stories')}>自编故事</Link>
          <Link to="/settings" className={isActive('/settings')}>设置</Link>
        </nav>
      </div>
      <div className="header-right">
        <button
          className="btn btn-ghost btn-sm theme-toggle"
          onClick={toggleTheme}
          title={theme === 'light' ? '切换暗色模式' : '切换亮色模式'}
        >
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
        <div className="header-user">
          <span className="user-avatar">{username?.[0]?.toUpperCase() || 'U'}</span>
          <span>{username}</span>
          {isAdmin && <span className="badge badge-blue">管理员</span>}
        </div>
        <button className="btn btn-ghost btn-sm" onClick={logout}>退出</button>
      </div>
      {mobileNav && <div className="mobile-backdrop active" onClick={() => setMobileNav(false)} />}
    </header>
  );
}
