import React, { useState, useEffect } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { Header } from '../components/Header';
import '../styles/admin.css';

export function AdminLayout() {
  const location = useLocation();
  const isActive = (path: string) => location.pathname === path ? 'active' : '';

  return (
    <div className="app-layout">
      <Header />
      <div className="admin-body">
        <nav className="admin-sidebar">
          <Link to="/admin" className={`admin-nav-item ${isActive('/admin')}`}>
            ▣ 概览
          </Link>
          <Link to="/admin/logs" className={`admin-nav-item ${isActive('/admin/logs')}`}>
            ▤ 操作日志
          </Link>
          <Link to="/admin/users" className={`admin-nav-item ${isActive('/admin/users')}`}>
            ▥ 用户管理
          </Link>
          <Link to="/admin/worldbook" className={`admin-nav-item ${isActive('/admin/worldbook')}`}>
            ▦ 世界书
          </Link>
        </nav>
        <main className="admin-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
