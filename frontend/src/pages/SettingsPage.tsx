import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import {
  isSoundEnabled, setSoundEnabled,
  isNotificationEnabled, setNotificationEnabled,
  requestNotificationPermission, playMessageSound,
} from '../utils/sound';
import '../styles/settings.css';

interface KeyConfig {
  provider: string;
  api_key: string;
  base_url: string;
  model: string;
}

const PROVIDER_INFO: Record<string, { name: string; desc: string; primary: boolean }> = {
  deepseek: { name: 'DeepSeek', desc: '优先使用，高质量中文对话模型', primary: true },
  siliconflow: { name: '硅基流动', desc: '备用 API，支持多种模型', primary: false },
};

export function SettingsPage() {
  const [keys, setKeys] = useState<KeyConfig[]>([]);
  const [edits, setEdits] = useState<Record<string, KeyConfig>>({});
  const [status, setStatus] = useState<Record<string, { type: string; msg: string }>>({});
  const [loading, setLoading] = useState(true);
  const [soundOn, setSoundOn] = useState(isSoundEnabled());
  const [notifyOn, setNotifyOn] = useState(isNotificationEnabled());

  useEffect(() => {
    api.getApiKeys()
      .then((data) => {
        setKeys(data.keys);
        const editMap: Record<string, KeyConfig> = {};
        data.keys.forEach((k) => { editMap[k.provider] = { ...k }; });
        setEdits(editMap);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (provider: string, field: keyof KeyConfig, value: string) => {
    setEdits((prev) => ({
      ...prev,
      [provider]: { ...prev[provider], [field]: value },
    }));
  };

  const handleSave = async (provider: string) => {
    const data = edits[provider];
    if (!data) return;
    try {
      await api.updateApiKey(data);
      setStatus({ ...status, [provider]: { type: 'success', msg: '保存成功' } });
    } catch (err: any) {
      setStatus({ ...status, [provider]: { type: 'error', msg: err.message || '保存失败' } });
    }
    setTimeout(() => setStatus((s) => { const n = { ...s }; delete n[provider]; return n; }), 3000);
  };

  const handleDelete = async (provider: string) => {
    try {
      await api.deleteApiKey(provider);
      setEdits((prev) => ({
        ...prev,
        [provider]: { ...prev[provider], api_key: '' },
      }));
      setStatus({ ...status, [provider]: { type: 'success', msg: '已恢复全局配置' } });
    } catch (err: any) {
      setStatus({ ...status, [provider]: { type: 'error', msg: err.message } });
    }
    setTimeout(() => setStatus((s) => { const n = { ...s }; delete n[provider]; return n; }), 3000);
  };

  if (loading) return <div className="settings-page flex items-center gap-sm"><div className="spinner" /> 加载中...</div>;

  return (
    <div className="settings-page fade-in">
      <h2>API 配置</h2>
      <p className="text-sm text-muted mb-md">
        配置 LLM 提供商的 API Key。留空时将使用系统全局配置。
      </p>

      {Object.entries(PROVIDER_INFO).map(([provider, info]) => {
        const edit = edits[provider] || { provider, api_key: '', base_url: '', model: '' };
        const st = status[provider];

        return (
          <div className="settings-card" key={provider}>
            <h3>
              {info.name}
              <span className={`provider-tag ${info.primary ? '' : 'secondary'}`}>
                {info.primary ? '优先' : '备用'}
              </span>
            </h3>
            <p>{info.desc}</p>

            <div className="settings-fields">
              <div className="settings-field">
                <label>API Key</label>
                <input
                  type="password"
                  value={edit.api_key}
                  onChange={(e) => handleChange(provider, 'api_key', e.target.value)}
                  placeholder="sk-..."
                />
              </div>
              <div className="settings-field">
                <label>Base URL</label>
                <input
                  type="text"
                  value={edit.base_url}
                  onChange={(e) => handleChange(provider, 'base_url', e.target.value)}
                  placeholder="https://api.example.com"
                />
              </div>
              <div className="settings-field">
                <label>模型名称</label>
                <input
                  type="text"
                  value={edit.model}
                  onChange={(e) => handleChange(provider, 'model', e.target.value)}
                  placeholder="model-name"
                />
              </div>
            </div>

            <div className="settings-actions">
              <button className="btn btn-primary btn-sm" onClick={() => handleSave(provider)}>保存</button>
              <button className="btn btn-sm btn-danger" onClick={() => handleDelete(provider)}>恢复全局</button>
            </div>

            {st && <div className={`settings-status ${st.type}`}>{st.msg}</div>}
          </div>
        );
      })}

      <h2 style={{ marginTop: 32 }}>声音与通知</h2>
      <p className="text-sm text-muted mb-md">控制游戏中的音效和浏览器通知。</p>

      <div className="settings-card">
        <div className="settings-toggle-row">
          <div>
            <strong>消息提示音</strong>
            <p className="text-sm text-muted">AI 回复完成时播放提示音</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              className="btn btn-sm"
              onClick={() => playMessageSound()}
              title="试听"
            >
              🔊
            </button>
            <label className="toggle-switch">
              <input
                type="checkbox"
                checked={soundOn}
                onChange={(e) => { setSoundOn(e.target.checked); setSoundEnabled(e.target.checked); }}
              />
              <span className="toggle-slider" />
            </label>
          </div>
        </div>

        <div className="settings-toggle-row" style={{ marginTop: 16 }}>
          <div>
            <strong>浏览器通知</strong>
            <p className="text-sm text-muted">页面不在前台时发送桌面通知</p>
          </div>
          <label className="toggle-switch">
            <input
              type="checkbox"
              checked={notifyOn}
              onChange={async (e) => {
                if (e.target.checked) {
                  const granted = await requestNotificationPermission();
                  if (!granted) return;
                }
                setNotifyOn(e.target.checked);
                setNotificationEnabled(e.target.checked);
              }}
            />
            <span className="toggle-slider" />
          </label>
        </div>
      </div>
    </div>
  );
}
