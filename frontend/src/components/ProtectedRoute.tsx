import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../stores/auth';

export function ProtectedRoute({ children, adminOnly = false }: { children: React.ReactNode; adminOnly?: boolean }) {
  const { token, isAdmin, loading } = useAuth();

  if (loading) {
    return <div className="flex items-center justify-center" style={{ height: '100vh' }}><div className="spinner" /></div>;
  }

  if (!token) return <Navigate to="/login" replace />;
  if (adminOnly && !isAdmin) return <Navigate to="/game" replace />;

  return <>{children}</>;
}
