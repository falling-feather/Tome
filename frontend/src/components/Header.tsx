import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../stores/auth';
import { setLanguage } from '../i18n';

function getInitialTheme(): 'light' | 'dark' {
  const saved = localStorage.getItem('theme');
  if (saved === 'dark' || saved === 'light') return saved;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function Header() {
  const { username, isAdmin, logout } = useAuth();
  const location = useLocation();
  const { t, i18n } = useTranslation();
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
  const toggleLang = () => setLanguage(i18n.language === 'zh-CN' ? 'en-US' : 'zh-CN');

  return (
    <header className="app-header">
      <div className="header-left">
        <button className="mobile-menu-btn" onClick={() => setMobileNav(!mobileNav)} aria-label={t('nav.menu')}>
          {mobileNav ? '✕' : '☰'}
        </button>
        <div className="header-logo">
          <span className="logo-icon">📖</span>
          {t('app.title')}
        </div>
        <nav className={`header-nav${mobileNav ? ' mobile-open' : ''}`}>
          {isAdmin ? (
            <>
              <Link to="/admin" className={isActive('/admin')}>{t('nav.console')}</Link>
              <Link to="/game" className={isActive('/game')}>{t('nav.adventure')}</Link>
            </>
          ) : (
            <Link to="/game" className={isActive('/game')}>{t('nav.adventure')}</Link>
          )}
          <Link to="/stories" className={isActive('/stories')}>{t('nav.stories')}</Link>
          <Link to="/settings" className={isActive('/settings')}>{t('nav.settings')}</Link>
        </nav>
      </div>
      <div className="header-right">
        <button
          className="btn btn-ghost btn-sm theme-toggle"
          onClick={toggleLang}
          title={i18n.language === 'zh-CN' ? t('header.switchToEnglish') : t('header.switchToChinese')}
        >
          {i18n.language === 'zh-CN' ? 'EN' : '中'}
        </button>
        <button
          className="btn btn-ghost btn-sm theme-toggle"
          onClick={toggleTheme}
          title={theme === 'light' ? t('header.themeToDark') : t('header.themeToLight')}
        >
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
        <div className="header-user">
          <span className="user-avatar">{username?.[0]?.toUpperCase() || 'U'}</span>
          <span>{username}</span>
          {isAdmin && <span className="badge badge-blue">{t('header.admin')}</span>}
        </div>
        <button className="btn btn-ghost btn-sm" onClick={logout}>{t('nav.logout')}</button>
      </div>
      {mobileNav && <div className="mobile-backdrop active" onClick={() => setMobileNav(false)} />}
    </header>
  );
}
