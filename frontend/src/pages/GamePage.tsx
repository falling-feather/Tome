import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Sidebar } from '../components/Sidebar';
import { GameChat } from '../components/GameChat';
import { StatusPanel } from '../components/StatusPanel';
import { api } from '../api/client';
import '../styles/game.css';

const SCENARIO_VALUES = [
  { value: 'fantasy', key: 'gameSetup.scenarioFantasy' },
  { value: 'scifi', key: 'gameSetup.scenarioScifi' },
  { value: 'wuxia', key: 'gameSetup.scenarioWuxia' },
];

// 注意：职业 value 是提交给后端的标识符，保持中文字面量（见 docs/05 数据约定）。
// i18n-ignore
const CLASS_VALUES = ['战士', '法师', '盗贼', '游侠', '吟游诗人']; // i18n-ignore

export function GamePage() {
  const { t } = useTranslation();
  const [sessions, setSessions] = useState<any[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [gameState, setGameState] = useState<any>({});
  const [showNewDialog, setShowNewDialog] = useState(false);
  const [customStories, setCustomStories] = useState<any[]>([]);
  const [mobileSidebar, setMobileSidebar] = useState(false);
  const [mobileStatus, setMobileStatus] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [newGame, setNewGame] = useState({
    title: '新的冒险',
    scenario: 'fantasy',
    character_name: '旅行者',
    character_class: '战士',
    story_id: null as number | null,
  });

  const showError = (msg: string) => {
    setError(msg);
    setTimeout(() => setError(null), 4000);
  };

  const loadSessions = useCallback(async () => {
    try {
      const data = await api.listSessions();
      setSessions(data.sessions);
    } catch (e: any) {
      showError(e.message || '加载会话列表失败');
    }
  }, []);

  const loadStories = useCallback(async () => {
    try {
      const data = await api.listStories();
      setCustomStories(data.stories.filter((s: any) => s.status === 'ready'));
    } catch {}
  }, []);

  useEffect(() => {
    Promise.all([loadSessions(), loadStories()]).finally(() => setLoading(false));
  }, [loadSessions, loadStories]);

  const selectSession = async (id: string) => {
    setActiveSessionId(id);
    setMobileSidebar(false);
    try {
      const data = await api.getSession(id);
      setMessages(data.messages);
      setGameState(data.state || {});
    } catch (e: any) {
      showError(e.message || '加载会话失败');
    }
  };

  const createSession = async () => {
    try {
      const payload: any = { ...newGame };
      if (payload.story_id) {
        payload.scenario = 'custom';
      } else {
        delete payload.story_id;
      }
      const session = await api.createSession(payload);
      setShowNewDialog(false);
      await loadSessions();
      await selectSession(session.id);
    } catch (e: any) {
      showError(e.message || '创建会话失败');
    }
  };

  const confirmDelete = (id: string) => setDeleteTarget(id);

  const exportSession = async (id: string) => {
    try {
      await api.exportSession(id);
    } catch (e: any) {
      showError(e.message || '导出失败');
    }
  };

  const renameSession = async (id: string, title: string) => {
    try {
      await api.renameSession(id, title);
      setSessions((prev) => prev.map((s) => (s.id === id ? { ...s, title } : s)));
    } catch (e: any) {
      showError(e.message || '重命名失败');
    }
  };

  const deleteSession = async () => {
    if (!deleteTarget) return;
    const id = deleteTarget;
    setDeleteTarget(null);
    try {
      await api.deleteSession(id);
      if (activeSessionId === id) {
        setActiveSessionId(null);
        setMessages([]);
        setGameState({});
      }
      await loadSessions();
    } catch (e: any) {
      showError(e.message || '删除失败');
    }
  };

  const handleMessagesUpdate = (updatedMessages: any[], state?: any) => {
    setMessages(updatedMessages);
    if (state) {
      setGameState(state);
      // Update session in sidebar
      setSessions((prev) =>
        prev.map((s) => (s.id === activeSessionId ? { ...s, state } : s))
      );
    }
  };

  return (
    <>
      {error && (
        <div className="toast-error" onClick={() => setError(null)}>
          {error}
        </div>
      )}

      <Sidebar
        sessions={sessions}
        activeId={activeSessionId}
        onSelect={selectSession}
        onNew={() => { setShowNewDialog(true); setMobileSidebar(false); }}
        onDelete={confirmDelete}
        onExport={exportSession}
        onRename={renameSession}
        className={mobileSidebar ? 'mobile-open' : ''}
      />

      <div className="app-content">
        {loading ? (
          <div className="no-session">
            <div className="icon pulse">📖</div>
            <p>加载中...</p>
          </div>
        ) : activeSessionId ? (
          <GameChat sessionId={activeSessionId} messages={messages} onMessagesUpdate={handleMessagesUpdate} />
        ) : (
          <div className="no-session">
            <div className="icon">📖</div>
            <p>选择一个冒险或创建新游戏</p>
            <button className="btn btn-primary" onClick={() => setShowNewDialog(true)}>开始新冒险</button>
          </div>
        )}
        <div className="mobile-toggle-bar">
          <button onClick={() => { setMobileSidebar(!mobileSidebar); setMobileStatus(false); }}>☰ 会话</button>
          <button onClick={() => { setMobileStatus(!mobileStatus); setMobileSidebar(false); }}>📊 状态</button>
        </div>
      </div>

      <div className={`app-right-panel${mobileStatus ? ' mobile-open' : ''}`}>
        <StatusPanel state={gameState} />
      </div>

      {(mobileSidebar || mobileStatus) && (
        <div className="mobile-backdrop active" onClick={() => { setMobileSidebar(false); setMobileStatus(false); }} />
      )}

      {showNewDialog && (
        <div className="dialog-overlay" onClick={() => setShowNewDialog(false)}>
          <div className="dialog" onClick={(e) => e.stopPropagation()}>
            <h2>创建新冒险</h2>
            <div className="form-field">
              <label>冒险名称</label>
              <input
                type="text"
                value={newGame.title}
                onChange={(e) => setNewGame({ ...newGame, title: e.target.value })}
              />
            </div>
            <div className="form-field">
              <label>世界设定</label>
              <select
                value={newGame.story_id ? 'custom' : newGame.scenario}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === 'custom') {
                    // 不做任何操作，让用户在下面选择具体故事
                    setNewGame({ ...newGame, story_id: customStories[0]?.id || null });
                  } else {
                    setNewGame({ ...newGame, scenario: val, story_id: null });
                  }
                }}
              >
                {SCENARIO_VALUES.map((s) => (
                  <option key={s.value} value={s.value}>{t(s.key)}</option>
                ))}
                {customStories.length > 0 && (
                  <option value="custom">自编故事</option>
                )}
              </select>
            </div>
            {newGame.story_id !== null && customStories.length > 0 && (
              <div className="form-field">
                <label>选择故事</label>
                <select
                  value={newGame.story_id || ''}
                  onChange={(e) => setNewGame({ ...newGame, story_id: Number(e.target.value) })}
                >
                  {customStories.map((s: any) => (
                    <option key={s.id} value={s.id}>{s.title}</option>
                  ))}
                </select>
              </div>
            )}
            <div className="form-field">
              <label>角色名称</label>
              <input
                type="text"
                value={newGame.character_name}
                onChange={(e) => setNewGame({ ...newGame, character_name: e.target.value })}
              />
            </div>
            <div className="form-field">
              <label>角色职业</label>
              <select
                value={newGame.character_class}
                onChange={(e) => setNewGame({ ...newGame, character_class: e.target.value })}
              >
                {CLASS_VALUES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div className="dialog-actions">
              <button className="btn" onClick={() => setShowNewDialog(false)}>取消</button>
              <button className="btn btn-primary" onClick={createSession}>开始冒险</button>
            </div>
          </div>
        </div>
      )}

      {deleteTarget && (
        <div className="dialog-overlay" onClick={() => setDeleteTarget(null)}>
          <div className="dialog" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 360 }}>
            <h2>确认删除</h2>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              此操作将永久删除该冒险及所有对话记录，无法恢复。
            </p>
            <div className="dialog-actions">
              <button className="btn" onClick={() => setDeleteTarget(null)}>取消</button>
              <button className="btn btn-danger" onClick={deleteSession}>删除</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
