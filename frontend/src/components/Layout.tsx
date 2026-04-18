import React from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';

export function Layout() {
  return (
    <div className="app-layout">
      <Header />
      <div className="app-body">
        <Outlet />
      </div>
    </div>
  );
}
