import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
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
        title: importTitle.trim() || t('story.untitled'),
        content: importContent,
      });
      setShowImport(false);
      setImportTitle('');
      setImportContent('');
      await loadStories();
    } catch (err: any) {
      setError(err.message || t('story.importFailed'));
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
      case 'pending': return t('story.statusPending');
      case 'parsing': return t('story.statusParsing');
      case 'ready': return t('story.statusReady');
      case 'error': return t('story.statusError');
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
        <h2>{t('story.title')}</h2>
        <p className="story-desc">{t('story.desc')}</p>
        <button className="btn btn-primary" onClick={() => setShowImport(true)}>{t('story.importBtn')}</button>
      </div>

      <div className="story-list">
        {stories.length === 0 && (
          <div className="story-empty">{t('story.empty')}</div>
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
              {t('story.delete')}
            </button>
          </div>
        ))}
      </div>

      {selectedStory?.parsed_data && (
        <div className="story-detail">
          <h3>{selectedStory.title}</h3>
          {selectedStory.parsed_data.plot_summary && (
            <div className="detail-section">
              <h4>{t('story.sectionPlot')}</h4>
              <p>{selectedStory.parsed_data.plot_summary}</p>
            </div>
          )}
          {selectedStory.parsed_data.world_rules && (
            <div className="detail-section">
              <h4>{t('story.sectionWorld')}</h4>
              <p>{selectedStory.parsed_data.world_rules}</p>
            </div>
          )}
          {selectedStory.parsed_data.characters && selectedStory.parsed_data.characters.length > 0 && (
            <div className="detail-section">
              <h4>{t('story.sectionCharacters')} ({selectedStory.parsed_data.characters.length})</h4>
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
              <h4>{t('story.sectionLocations')} ({selectedStory.parsed_data.locations.length})</h4>
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
            <h2>{t('story.importDialogTitle')}</h2>
            {error && <div className="login-error">{error}</div>}
            <div className="form-field">
              <label>{t('story.fieldTitle')}</label>
              <input
                type="text"
                value={importTitle}
                onChange={(e) => setImportTitle(e.target.value)}
                placeholder={t('story.fieldTitlePlaceholder')}
              />
            </div>
            <div className="form-field">
              <label>{t('story.fieldContent')}</label>
              <textarea
                className="story-textarea"
                value={importContent}
                onChange={(e) => setImportContent(e.target.value)}
                placeholder={t('story.contentPlaceholder')}
                rows={12}
              />
              <div className="story-char-count">{t('story.charCount', { n: importContent.length })}</div>
            </div>
            <div className="dialog-actions">
              <button className="btn" onClick={() => setShowImport(false)}>{t('story.cancel')}</button>
              <button
                className="btn btn-primary"
                onClick={handleImport}
                disabled={importing || importContent.trim().length < 50}
              >
                {importing ? <span className="spinner" /> : t('story.startImport')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
