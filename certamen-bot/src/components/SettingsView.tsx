import React, { useState, useEffect } from 'react';
import { useCertamen } from '../context/CertamenContext';
import { pingTurso } from '../services/tursoService';

const Setting: React.FC<{ name: string; help: string; htmlFor?: string; children: React.ReactNode }> = ({
  name,
  help,
  htmlFor,
  children,
}) => (
  <div className="setting">
    <div>
      <p className="setting__name">{htmlFor ? <label htmlFor={htmlFor}>{name}</label> : name}</p>
      <p className="setting__help">{help}</p>
    </div>
    <div className="setting__control">{children}</div>
  </div>
);

export const SettingsView: React.FC = () => {
  const { settings, updateSettings, resetUserStats } = useCertamen();
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [testStatus, setTestStatus] = useState<{ message?: string; isError?: boolean } | null>(null);
  const [isTesting, setIsTesting] = useState<boolean>(false);

  useEffect(() => {
    if ('speechSynthesis' in window) {
      const loadVoices = () => {
        setVoices(window.speechSynthesis.getVoices());
      };
      loadVoices();
      window.speechSynthesis.onvoiceschanged = loadVoices;
    }
  }, []);

  const handleTestTurso = async () => {
    if (!settings.tursoUrl) {
      setTestStatus({ message: 'Enter a Turso Database URL first.', isError: true });
      return;
    }
    setIsTesting(true);
    setTestStatus(null);
    const res = await pingTurso(settings.tursoUrl, settings.tursoAuthToken);
    setIsTesting(false);
    if (res.success) {
      setTestStatus({ message: res.message || 'Connected successfully!', isError: false });
    } else {
      setTestStatus({ message: res.error || 'Connection failed.', isError: true });
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p className="small muted">Saved on this device.</p>
        </div>
      </div>

      <h2>Reading</h2>
      <div className="settings">
        <Setting name="Reader" help="Read the question as text on screen, or have it spoken aloud.">
          <span className="seg">
            <button
              type="button"
              className="btn btn--small"
              aria-pressed={settings.readerMode === 'visual'}
              onClick={() => updateSettings({ readerMode: 'visual' })}
            >
              Text
            </button>
            <button
              type="button"
              className="btn btn--small"
              aria-pressed={settings.readerMode === 'audio'}
              onClick={() => updateSettings({ readerMode: 'audio' })}
            >
              Voice
            </button>
          </span>
        </Setting>

        <Setting name="Text pace" help="How quickly the question appears on screen." htmlFor="set-pace">
          <input
            id="set-pace"
            type="range"
            min="20"
            max="90"
            step="5"
            value={110 - settings.readingSpeed}
            onChange={(e) => updateSettings({ readingSpeed: 110 - Number(e.target.value) })}
          />
          <span className="mono small">
            {settings.readingSpeed <= 30 ? 'Fast' : settings.readingSpeed <= 55 ? 'Normal' : 'Slow'}
          </span>
        </Setting>

        <Setting name="Voice pace" help="How quickly the spoken moderator reads." htmlFor="set-rate">
          <input
            id="set-rate"
            type="range"
            min="0.75"
            max="1.5"
            step="0.05"
            value={settings.speechRate || 1.0}
            onChange={(e) => updateSettings({ speechRate: Number(e.target.value) })}
          />
          <span className="mono small">{(settings.speechRate || 1.0).toFixed(2)}×</span>
        </Setting>

        {voices.length > 0 && (
          <Setting name="Voice" help="Which of this device's voices reads the questions." htmlFor="set-voice">
            <select
              id="set-voice"
              value={settings.selectedVoiceURI || ''}
              onChange={(e) => updateSettings({ selectedVoiceURI: e.target.value })}
            >
              <option value="">System default</option>
              {voices
                .filter((v) => v.lang.startsWith('en') || v.lang.startsWith('la') || v.lang.startsWith('it'))
                .map((v) => (
                  <option key={v.voiceURI} value={v.voiceURI}>
                    {v.name} ({v.lang})
                  </option>
                ))}
            </select>
          </Setting>
        )}
      </div>

      <h2>Scoring & Effects</h2>
      <div className="settings">
        <Setting name="Answer time" help="Seconds to answer after you buzz.">
          <span className="seg">
            {[3, 5, 8, 10].map((sec) => (
              <button
                key={sec}
                type="button"
                className="btn btn--small"
                aria-pressed={settings.timerDuration === sec}
                onClick={() => updateSettings({ timerDuration: sec })}
              >
                {sec} s
              </button>
            ))}
          </span>
        </Setting>

        <Setting name="Power buzz" help="Fifteen points instead of ten for buzzing before the question is finished.">
          <label className="check">
            <input
              type="checkbox"
              checked={settings.powerBuzzEnabled}
              onChange={(e) => updateSettings({ powerBuzzEnabled: e.target.checked })}
            />
            {settings.powerBuzzEnabled ? 'On' : 'Off'}
          </label>
        </Setting>

        <Setting name="Sounds" help="A tone on the buzz, and on a right or wrong answer.">
          <label className="check">
            <input
              type="checkbox"
              checked={settings.soundEnabled}
              onChange={(e) => updateSettings({ soundEnabled: e.target.checked })}
            />
            {settings.soundEnabled ? 'On' : 'Off'}
          </label>
        </Setting>

        <Setting name="Confetti" help="Celebrate correct answers with a burst of confetti.">
          <label className="check">
            <input
              type="checkbox"
              checked={settings.confettiEnabled !== false}
              onChange={(e) => updateSettings({ confettiEnabled: e.target.checked })}
            />
            {settings.confettiEnabled !== false ? 'On' : 'Off'}
          </label>
        </Setting>
      </div>

      <h2>Database (Turso)</h2>
      <div className="settings">
        <Setting
          name="Turso Database URL"
          help="The URL for your separate Turso database (libsql://... or https://...)."
          htmlFor="set-turso-url"
        >
          <input
            id="set-turso-url"
            type="text"
            value={settings.tursoUrl}
            onChange={(e) => updateSettings({ tursoUrl: e.target.value.trim() })}
            placeholder="libsql://your-db-name.turso.io"
          />
        </Setting>

        <Setting
          name="Turso Auth Token"
          help="The auth token for your Turso database. Leave blank if your database is public."
          htmlFor="set-turso-token"
        >
          <input
            id="set-turso-token"
            type="password"
            value={settings.tursoAuthToken}
            onChange={(e) => updateSettings({ tursoAuthToken: e.target.value.trim() })}
            placeholder="eyJhbGciOi..."
          />
        </Setting>

        <Setting
          name="Connection Test"
          help="Verify the database connection and initialize tables."
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <button
              type="button"
              className="btn btn--small"
              onClick={handleTestTurso}
              disabled={isTesting}
            >
              {isTesting && <span className="btn__spinner" aria-hidden="true" />}
              {isTesting ? 'Testing' : 'Test connection'}
            </button>
            {testStatus && (
              <span className={`small ${testStatus.isError ? 'danger' : 'status-done'}`}>
                {testStatus.message}
              </span>
            )}
          </div>
        </Setting>

        <Setting name="Reset" help="Clear your scores and answer history on this device. This cannot be undone.">
          <button
            type="button"
            className="btn btn--danger"
            onClick={() => {
              if (confirm('Reset all statistics and question history?')) resetUserStats();
            }}
          >
            Reset my data
          </button>
        </Setting>
      </div>
    </>
  );
};
