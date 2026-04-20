import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
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

export function SettingsPage() {
  const { t } = useTranslation();
  const PROVIDER_INFO: Record<string, { name: string; desc: string; primary: boolean }> = {
    deepseek: { name: 'DeepSeek', desc: t('settings.deepseekDesc'), primary: true },
    siliconflow: { name: t('settings.siliconflowName'), desc: t('settings.siliconflowDesc'), primary: false },
  };
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
      setStatus({ ...status, [provider]: { type: 'success', msg: t('settings.savedOk') } });
    } catch (err: any) {
      setStatus({ ...status, [provider]: { type: 'error', msg: err.message || t('settings.saveFailed') } });
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
      setStatus({ ...status, [provider]: { type: 'success', msg: t('settings.restoredOk') } });
    } catch (err: any) {
      setStatus({ ...status, [provider]: { type: 'error', msg: err.message } });
    }
    setTimeout(() => setStatus((s) => { const n = { ...s }; delete n[provider]; return n; }), 3000);
  };

  if (loading) return <div className="settings-page flex items-center gap-sm"><div className="spinner" /> {t('common.loading')}</div>;

  return (
    <div className="settings-page fade-in">
      <h2>{t('settings.apiTitle')}</h2>
      <p className="text-sm text-muted mb-md">
        {t('settings.apiDesc')}
      </p>

      {Object.entries(PROVIDER_INFO).map(([provider, info]) => {
        const edit = edits[provider] || { provider, api_key: '', base_url: '', model: '' };
        const st = status[provider];

        return (
          <div className="settings-card" key={provider}>
            <h3>
              {info.name}
              <span className={`provider-tag ${info.primary ? '' : 'secondary'}`}>
                {info.primary ? t('settings.primary') : t('settings.backup')}
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
                <label>{t('settings.modelName')}</label>
                <input
                  type="text"
                  value={edit.model}
                  onChange={(e) => handleChange(provider, 'model', e.target.value)}
                  placeholder="model-name"
                />
              </div>
            </div>

            <div className="settings-actions">
              <button className="btn btn-primary btn-sm" onClick={() => handleSave(provider)}>{t('settings.save')}</button>
              <button className="btn btn-sm btn-danger" onClick={() => handleDelete(provider)}>{t('settings.restoreGlobal')}</button>
            </div>

            {st && <div className={`settings-status ${st.type}`}>{st.msg}</div>}
          </div>
        );
      })}

      <h2 style={{ marginTop: 32 }}>{t('settings.soundTitle')}</h2>
      <p className="text-sm text-muted mb-md">{t('settings.soundDesc')}</p>

      <div className="settings-card">
        <div className="settings-toggle-row">
          <div>
            <strong>{t('settings.soundLabel')}</strong>
            <p className="text-sm text-muted">{t('settings.soundHint')}</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              className="btn btn-sm"
              onClick={() => playMessageSound()}
              title={t('settings.soundPreview')}
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
            <strong>{t('settings.notifyLabel')}</strong>
            <p className="text-sm text-muted">{t('settings.notifyHint')}</p>
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
