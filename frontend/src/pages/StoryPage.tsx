import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import '../styles/story.css';

interface Story {
  id: number;
  title: string;
  status: string;
  error_msg?: string;
  parsed_data?: {
    characters?: { name: string; description: string; personality: string; speaking_style: string }[];
    locations?: { name: string; description: string }[];
    plot_summary?: string;
    world_rules?: string;
  };
  created_at: string;
}

export function StoryPage() {
  const [stories, setStories] = useState<Story[]>([]);
  const [showImport, setShowImport] = useState(false);
  const [importTitle, setImportTitle] = useState('');
  const [importContent, setImportContent] = useState('');
  const [importing, setImporting] = useState(false);
  const [selectedStory, setSelectedStory] = useState<Story | null>(null);
  const [error, setError] = useState('');

  const loadStories = useCallback(async () => {
    try {
      const data = await api.listStories();
      setStories(data.stories);
    } catch {}
  }, []);

  useEffect(() => { loadStories(); }, [loadStories]);

  // 轮询 parsing 状态的故事
  useEffect(() => {
    const hasPending = stories.some(s => s.status === 'pending' || s.status === 'parsing');
    if (!hasPending) return;
    const timer = setInterval(loadStories, 3000);
    return () => clearInterval(timer);
  }, [stories, loadStories]);

  const handleImport = async () => {
    if (!importContent.trim()) return;
    setImporting(true);
    setError('');
    try {
      await api.importStory({
        title: importTitle.trim() || '未命名故事',
        content: importContent,
      });
      setShowImport(false);
      setImportTitle('');
      setImportContent('');
      await loadStories();
    } catch (err: any) {
      setError(err.message || '导入失败');
    } finally {
      setImporting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteStory(id);
      if (selectedStory?.id === id) setSelectedStory(null);
      await loadStories();
    } catch {}
  };

  const viewStory = async (id: number) => {
    try {
      const story = await api.getStory(id);
      setSelectedStory(story);
    } catch {}
  };

  const statusLabel = (status: string) => {
    switch (status) {
      case 'pending': return '等待解析';
      case 'parsing': return '正在解析...';
      case 'ready': return '已就绪';
      case 'error': return '解析失败';
      default: return status;
    }
  };

  const statusClass = (status: string) => {
    switch (status) {
      case 'ready': return 'badge-green';
      case 'error': return 'badge-red';
      case 'parsing': return 'badge-blue';
      default: return '';
    }
  };

  return (
    <div className="story-page">
      <div className="story-header">
        <h2>自编故事</h2>
        <p className="story-desc">导入你喜欢的故事或小说，AI 将自动解析角色与世界设定，供冒险使用。</p>
        <button className="btn btn-primary" onClick={() => setShowImport(true)}>导入新故事</button>
      </div>

      <div className="story-list">
        {stories.length === 0 && (
          <div className="story-empty">暂无故事，点击上方按钮导入</div>
        )}
        {stories.map(s => (
          <div
            key={s.id}
            className={`story-card ${selectedStory?.id === s.id ? 'active' : ''}`}
            onClick={() => viewStory(s.id)}
          >
            <div className="story-card-header">
              <span className="story-title">{s.title}</span>
              <span className={`badge ${statusClass(s.status)}`}>{statusLabel(s.status)}</span>
            </div>
            <div className="story-card-meta">
              {new Date(s.created_at).toLocaleString('zh-CN')}
            </div>
            {s.status === 'error' && s.error_msg && (
              <div className="story-error">{s.error_msg}</div>
            )}
            <button className="btn btn-ghost btn-sm story-delete" onClick={(e) => { e.stopPropagation(); handleDelete(s.id); }}>
              删除
            </button>
          </div>
        ))}
      </div>

      {selectedStory?.parsed_data && (
        <div className="story-detail">
          <h3>{selectedStory.title}</h3>
          {selectedStory.parsed_data.plot_summary && (
            <div className="detail-section">
              <h4>剧情概述</h4>
              <p>{selectedStory.parsed_data.plot_summary}</p>
            </div>
          )}
          {selectedStory.parsed_data.world_rules && (
            <div className="detail-section">
              <h4>世界设定</h4>
              <p>{selectedStory.parsed_data.world_rules}</p>
            </div>
          )}
          {selectedStory.parsed_data.characters && selectedStory.parsed_data.characters.length > 0 && (
            <div className="detail-section">
              <h4>角色 ({selectedStory.parsed_data.characters.length})</h4>
              <div className="detail-grid">
                {selectedStory.parsed_data.characters.map((c, i) => (
                  <div key={i} className="detail-card">
                    <div className="detail-card-name">{c.name}</div>
                    <div className="detail-card-desc">{c.description}</div>
                    <div className="detail-card-tags">
                      <span>{c.personality}</span>
                      <span>{c.speaking_style}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {selectedStory.parsed_data.locations && selectedStory.parsed_data.locations.length > 0 && (
            <div className="detail-section">
              <h4>地点 ({selectedStory.parsed_data.locations.length})</h4>
              <div className="detail-grid">
                {selectedStory.parsed_data.locations.map((l, i) => (
                  <div key={i} className="detail-card">
                    <div className="detail-card-name">{l.name}</div>
                    <div className="detail-card-desc">{l.description}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {showImport && (
        <div className="dialog-overlay" onClick={() => setShowImport(false)}>
          <div className="dialog story-import-dialog" onClick={(e) => e.stopPropagation()}>
            <h2>导入故事</h2>
            {error && <div className="login-error">{error}</div>}
            <div className="form-field">
              <label>故事标题</label>
              <input
                type="text"
                value={importTitle}
                onChange={(e) => setImportTitle(e.target.value)}
                placeholder="故事名称（可选，AI会自动识别）"
              />
            </div>
            <div className="form-field">
              <label>故事内容</label>
              <textarea
                className="story-textarea"
                value={importContent}
                onChange={(e) => setImportContent(e.target.value)}
                placeholder="粘贴故事/小说内容（至少50字，最多5万字）..."
                rows={12}
              />
              <div className="story-char-count">{importContent.length} / 50000 字</div>
            </div>
            <div className="dialog-actions">
              <button className="btn" onClick={() => setShowImport(false)}>取消</button>
              <button
                className="btn btn-primary"
                onClick={handleImport}
                disabled={importing || importContent.trim().length < 50}
              >
                {importing ? <span className="spinner" /> : '开始导入'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
