import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './stores/auth';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Layout } from './components/Layout';
import { LoginPage } from './pages/LoginPage';
import { GamePage } from './pages/GamePage';
import { SettingsPage } from './pages/SettingsPage';
import { AdminLayout } from './pages/AdminLayout';
import { AdminDashboard } from './pages/AdminDashboard';
import { AdminLogs } from './pages/AdminLogs';
import { AdminUsers } from './pages/AdminUsers';
import { AdminWorldBook } from './pages/AdminWorldBook';
import { AdminGameEvents } from './pages/AdminGameEvents';
import { StoryPage } from './pages/StoryPage';

function AppRoutes() {
  const { token, isAdmin } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={token ? <Navigate to={isAdmin ? '/admin' : '/game'} replace /> : <LoginPage />} />

      {/* Normal user layout */}
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/game" element={<GamePage />} />
        <Route path="/stories" element={<StoryPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>

      {/* Admin layout */}
      <Route path="/admin" element={<ProtectedRoute adminOnly><AdminLayout /></ProtectedRoute>}>
        <Route index element={<AdminDashboard />} />
        <Route path="logs" element={<AdminLogs />} />
        <Route path="users" element={<AdminUsers />} />
        <Route path="worldbook" element={<AdminWorldBook />} />
        <Route path="events" element={<AdminGameEvents />} />
      </Route>

      <Route path="*" element={<Navigate to={token ? (isAdmin ? '/admin' : '/game') : '/login'} replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
