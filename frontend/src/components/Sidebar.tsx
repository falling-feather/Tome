import React, { useState, useRef, useEffect } from 'react';

interface SidebarProps {
  sessions: any[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onExport: (id: string) => void;
  onRename: (id: string, title: string) => void;
  className?: string;
}

export function Sidebar({ sessions, activeId, onSelect, onNew, onDelete, onExport, onRename, className }: SidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingId]);

  const startRename = (id: string, title: string) => {
    setEditingId(id);
    setEditValue(title);
  };

  const commitRename = () => {
    if (editingId && editValue.trim()) {
      onRename(editingId, editValue.trim());
    }
    setEditingId(null);
  };

  return (
    <aside className={`app-sidebar${className ? ' ' + className : ''}`}>
      <div className="sidebar-header">
        <h3>会话</h3>
        <button className="btn btn-sm btn-primary" onClick={onNew}>+ 新游戏</button>
      </div>
      <div className="sidebar-list">
        {sessions.length === 0 ? (
          <div className="sidebar-empty">
            <p>还没有冒险记录</p>
            <p className="text-xs text-muted">点击上方按钮开始</p>
          </div>
        ) : (
          sessions.map((s) => (
            <div
              key={s.id}
              className={`sidebar-item ${s.id === activeId ? 'active' : ''}`}
              onClick={() => onSelect(s.id)}
            >
              {editingId === s.id ? (
                <input
                  ref={inputRef}
                  className="rename-input"
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onBlur={commitRename}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') commitRename();
                    if (e.key === 'Escape') setEditingId(null);
                  }}
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <div
                  className="item-title"
                  onDoubleClick={(e) => { e.stopPropagation(); startRename(s.id, s.title); }}
                  title="双击重命名"
                >
                  {s.title}
                </div>
              )}
              <div className="flex items-center justify-between">
                <span className="item-meta">
                  T{s.state?.turn || 0} · Ch.{s.state?.chapter || 1}
                </span>
                <span>
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ padding: '1px 4px', fontSize: '11px', marginRight: 2 }}
                    onClick={(e) => { e.stopPropagation(); startRename(s.id, s.title); }}
                    title="重命名"
                  >
                    ✏️
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ padding: '1px 4px', fontSize: '11px', marginRight: 2 }}
                    onClick={(e) => { e.stopPropagation(); onExport(s.id); }}
                    title="导出日志"
                  >
                    📥
                  </button>
                  <button
                    className="btn btn-ghost btn-sm btn-danger"
                    style={{ padding: '1px 4px', fontSize: '11px' }}
                    onClick={(e) => { e.stopPropagation(); onDelete(s.id); }}
                    title="删除"
                  >
                    ✕
                  </button>
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
