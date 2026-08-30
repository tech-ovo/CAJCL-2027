import React, { useState, useEffect } from 'react';
import { useCertamen } from '../context/CertamenContext';
import { Sliders, Cloud, AlertTriangle } from 'lucide-react';

export const SettingsView: React.FC = () => {
  const { settings, updateSettings, resetUserStats } = useCertamen();
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);

  useEffect(() => {
    if ('speechSynthesis' in window) {
      const loadVoices = () => {
        setVoices(window.speechSynthesis.getVoices());
      };
      loadVoices();
      window.speechSynthesis.onvoiceschanged = loadVoices;
    }
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* Header */}
      <div className="pb-3 border-b border-sky-200/80">
        <h2 className="text-xl font-display font-bold text-slate-900 flex items-center gap-2">
          <Sliders className="w-5 h-5 text-sky-600" />
          <span>Certamen Configuration</span>
        </h2>
        <div className="text-xs text-slate-500 font-editorial italic">
          Configure reader speed, timer duration, speech synthesis, and cloud backend
        </div>
      </div>

      {/* Settings Card */}
      <div className="classical-card-elevated rounded-3xl divide-y divide-sky-100 overflow-hidden text-xs shadow-md">
        {/* Practice Mode */}
        <div className="p-4 sm:p-5 flex items-center justify-between gap-4">
          <div>
            <div className="text-slate-900 font-semibold">Moderator Practice Mode</div>
            <div className="text-slate-500 font-editorial text-sm">Choose between reading visual text or speech moderator audio</div>
          </div>
          <div className="flex items-center gap-1 bg-sky-50 p-1 rounded-xl border border-sky-200">
            <button
              onClick={() => updateSettings({ readerMode: 'visual' })}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                settings.readerMode === 'visual'
                  ? 'bg-sky-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Visual
            </button>
            <button
              onClick={() => updateSettings({ readerMode: 'audio' })}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                settings.readerMode === 'audio'
                  ? 'bg-sky-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Audio Speech
            </button>
          </div>
        </div>

        {/* Typewriter Speed */}
        <div className="p-4 sm:p-5 flex items-center justify-between gap-4">
          <div>
            <div className="text-slate-900 font-semibold">Typewriter Pace</div>
            <div className="text-slate-500 font-editorial text-sm">Speed at which visual question text reveals on screen</div>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min="20"
              max="90"
              step="5"
              value={settings.readingSpeed}
              onChange={(e) => updateSettings({ readingSpeed: Number(e.target.value) })}
              className="w-32 accent-sky-600 cursor-pointer"
            />
            <span className="text-sky-900 font-bold w-16 text-right">
              {settings.readingSpeed <= 30 ? 'Fast' : settings.readingSpeed <= 55 ? 'Normal' : 'Slow'}
            </span>
          </div>
        </div>

        {/* Audio Speech Rate */}
        <div className="p-4 sm:p-5 flex items-center justify-between gap-4">
          <div>
            <div className="text-slate-900 font-semibold">Speech Modulation Speed</div>
            <div className="text-slate-500 font-editorial text-sm">Moderator speech synthesis rate</div>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min="0.75"
              max="1.5"
              step="0.05"
              value={settings.speechRate || 1.0}
              onChange={(e) => updateSettings({ speechRate: Number(e.target.value) })}
              className="w-32 accent-sky-600 cursor-pointer"
            />
            <span className="text-sky-900 font-bold w-12 text-right">
              {(settings.speechRate || 1.0).toFixed(2)}x
            </span>
          </div>
        </div>

        {/* Speech Voice */}
        {voices.length > 0 && (
          <div className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="text-slate-900 font-semibold">Moderator Voice Engine</div>
              <div className="text-slate-500 font-editorial text-sm">Select synthesis voice profile</div>
            </div>
            <select
              value={settings.selectedVoiceURI || ''}
              onChange={(e) => updateSettings({ selectedVoiceURI: e.target.value })}
              className="bg-white border border-sky-200 text-slate-900 rounded-xl px-3 py-2 text-xs outline-none max-w-xs focus:border-sky-500 shadow-xs"
            >
              <option value="">System Default Voice</option>
              {voices
                .filter((v) => v.lang.startsWith('en') || v.lang.startsWith('la') || v.lang.startsWith('it'))
                .map((v) => (
                  <option key={v.voiceURI} value={v.voiceURI}>
                    {v.name} ({v.lang})
                  </option>
                ))}
            </select>
          </div>
        )}

        {/* Response Timer Duration */}
        <div className="p-4 sm:p-5 flex items-center justify-between gap-4">
          <div>
            <div className="text-slate-900 font-semibold">Buzzer Countdown Timer</div>
            <div className="text-slate-500 font-editorial text-sm">Seconds allotted to submit answer after buzz</div>
          </div>
          <div className="flex items-center gap-1.5 bg-sky-50 p-1 rounded-xl border border-sky-200">
            {[3, 5, 8, 10].map((sec) => (
              <button
                key={sec}
                onClick={() => updateSettings({ timerDuration: sec })}
                className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  settings.timerDuration === sec
                    ? 'bg-sky-600 text-white shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {sec}s
              </button>
            ))}
          </div>
        </div>

        {/* Sound FX */}
        <div className="p-4 sm:p-5 flex items-center justify-between gap-4">
          <div>
            <div className="text-slate-900 font-semibold">Buzzer Audio FX</div>
            <div className="text-slate-500 font-editorial text-sm">Synthesizer tones on buzz, correct, and incorrect</div>
          </div>
          <button
            onClick={() => updateSettings({ soundEnabled: !settings.soundEnabled })}
            className={`px-4 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              settings.soundEnabled
                ? 'bg-sky-600 text-white shadow-xs'
                : 'bg-slate-100 text-slate-500 border border-slate-200'
            }`}
          >
            {settings.soundEnabled ? 'Active' : 'Muted'}
          </button>
        </div>

        {/* Power Buzz Rule */}
        <div className="p-4 sm:p-5 flex items-center justify-between gap-4">
          <div>
            <div className="text-slate-900 font-semibold">Power Buzz (+15 pts)</div>
            <div className="text-slate-500 font-editorial text-sm">Grants 15 points instead of 10 for early buzzes</div>
          </div>
          <button
            onClick={() => updateSettings({ powerBuzzEnabled: !settings.powerBuzzEnabled })}
            className={`px-4 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              settings.powerBuzzEnabled
                ? 'bg-sky-600 text-white shadow-xs'
                : 'bg-slate-100 text-slate-500 border border-slate-200'
            }`}
          >
            {settings.powerBuzzEnabled ? 'Active' : 'Off'}
          </button>
        </div>

        {/* Google Apps Script Endpoint */}
        <div className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="text-slate-900 font-semibold flex items-center gap-1.5">
              <Cloud className="w-4 h-4 text-sky-600" />
              <span>Google Apps Script Endpoint</span>
            </div>
            <div className="text-slate-500 font-editorial text-sm">Cloud Web App backend deployment URL</div>
          </div>
          <input
            type="url"
            value={settings.appsScriptUrl}
            onChange={(e) => updateSettings({ appsScriptUrl: e.target.value.trim() })}
            placeholder="https://script.google.com/macros/s/.../exec"
            className="w-full sm:w-80 bg-white border border-sky-200 focus:border-sky-500 rounded-xl px-3 py-2 text-xs text-slate-900 placeholder-slate-400 outline-none shadow-xs"
          />
        </div>

        {/* Reset Local Data */}
        <div className="p-4 sm:p-5 flex items-center justify-between gap-4">
          <div>
            <div className="text-rose-700 font-semibold flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-rose-600" />
              <span>Reset Local Data</span>
            </div>
            <div className="text-slate-500 font-editorial text-sm">Clear local session attempt history and scores</div>
          </div>
          <button
            onClick={() => {
              if (confirm('Reset all statistics and question history?')) {
                resetUserStats();
              }
            }}
            className="px-4 py-1.5 rounded-xl text-rose-700 hover:bg-rose-50 border border-rose-200 text-xs font-bold transition-all cursor-pointer shadow-xs"
          >
            Reset Data
          </button>
        </div>
      </div>
    </div>
  );
};
