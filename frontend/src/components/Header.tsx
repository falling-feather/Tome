import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../stores/auth';
import { setLanguage } from '../i18n';

type Theme = 'light' | 'dark' | 'sepia';
type Font = 'sans' | 'serif' | 'cn' | 'mono';

const THEME_CYCLE: Theme[] = ['light', 'dark', 'sepia'];
const THEME_ICONS: Record<Theme, string> = { light: '☀️', dark: '🌙', sepia: '📜' };

function getInitialTheme(): Theme {
  const saved = localStorage.getItem('theme');
  if (saved === 'dark' || saved === 'light' || saved === 'sepia') return saved;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function getInitialFont(): Font {
  const saved = localStorage.getItem('inkless-font');
  if (saved === 'sans' || saved === 'serif' || saved === 'cn' || saved === 'mono') return saved;
  return 'sans';
}

export function Header() {
  const { username, isAdmin, logout } = useAuth();
  const location = useLocation();
  const { t, i18n } = useTranslation();
  const [mobileNav, setMobileNav] = useState(false);
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const [font, setFont] = useState<Font>(getInitialFont);
  const [fontMenu, setFontMenu] = useState(false);
  const fontMenuRef = useRef<HTMLDivElement>(null);

  const isActive = (path: string) => location.pathname.startsWith(path) ? 'active' : '';

  useEffect(() => { setMobileNav(false); }, [location.pathname]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.setAttribute('data-font', font);
    localStorage.setItem('inkless-font', font);
  }, [font]);

  useEffect(() => {
    if (!fontMenu) return;
    const onClick = (e: MouseEvent) => {
      if (fontMenuRef.current && !fontMenuRef.current.contains(e.target as Node)) {
        setFontMenu(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [fontMenu]);

  const cycleTheme = () => {
    const i = THEME_CYCLE.indexOf(theme);
    setTheme(THEME_CYCLE[(i + 1) % THEME_CYCLE.length]);
  };
  const themeTitle = theme === 'light'
    ? t('header.themeToDark')
    : theme === 'dark'
      ? t('header.themeToSepia')
      : t('header.themeToLight');

  const toggleLang = () => setLanguage(i18n.language === 'zh-CN' ? 'en-US' : 'zh-CN');

  const fonts: { key: Font; labelKey: string }[] = [
    { key: 'sans', labelKey: 'header.fontSans' },
    { key: 'serif', labelKey: 'header.fontSerif' },
    { key: 'cn', labelKey: 'header.fontCn' },
    { key: 'mono', labelKey: 'header.fontMono' },
  ];

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
        <div className="font-switcher" ref={fontMenuRef} style={{ position: 'relative' }}>
          <button
            className="btn btn-ghost btn-sm theme-toggle"
            onClick={() => setFontMenu(v => !v)}
            title={t('header.font')}
            aria-haspopup="menu"
            aria-expanded={fontMenu}
          >
            Aa
          </button>
          {fontMenu && (
            <div
              role="menu"
              className="font-menu"
              style={{
                position: 'absolute',
                top: 'calc(100% + 4px)',
                right: 0,
                background: 'var(--bg-card)',
                border: '1px solid var(--border-light)',
                borderRadius: 'var(--radius-md)',
                boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
                minWidth: 200,
                zIndex: 1000,
                overflow: 'hidden',
              }}
            >
              {fonts.map(f => (
                <button
                  key={f.key}
                  role="menuitemradio"
                  aria-checked={font === f.key}
                  onClick={() => { setFont(f.key); setFontMenu(false); }}
                  style={{
                    display: 'block',
                    width: '100%',
                    padding: '8px 12px',
                    border: 'none',
                    background: font === f.key ? 'var(--accent-subtle)' : 'transparent',
                    color: 'var(--text-primary)',
                    textAlign: 'left',
                    cursor: 'pointer',
                    fontSize: 13,
                  }}
                >
                  {font === f.key ? '✓ ' : '  '}{t(f.labelKey)}
                </button>
              ))}
            </div>
          )}
        </div>
        <button
          className="btn btn-ghost btn-sm theme-toggle"
          onClick={cycleTheme}
          title={themeTitle}
        >
          {THEME_ICONS[theme]}
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
