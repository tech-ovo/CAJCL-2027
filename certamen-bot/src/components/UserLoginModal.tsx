import React, { useState } from 'react';
import { useCertamen } from '../context/CertamenContext';
import { X, LogOut, ShieldCheck } from 'lucide-react';

interface UserLoginModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const UserLoginModal: React.FC<UserLoginModalProps> = ({ isOpen, onClose }) => {
  const { user, loginUser, logoutUser, isSyncing } = useCertamen();

  const [username, setUsername] = useState<string>(user.username);
  const [pin, setPin] = useState<string>(user.pin);
  const [school, setSchool] = useState<string>(user.school || 'University High School');
  const [message, setMessage] = useState<string>('');

  if (!isOpen) return null;

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) return;

    setMessage('Synchronizing cloud profile...');
    const success = await loginUser(username.trim(), pin.trim(), school.trim());
    if (success) {
      setMessage('Profile saved to UHSJCL Cloud!');
      setTimeout(() => {
        onClose();
      }, 500);
    } else {
      setMessage('Error updating profile.');
    }
  };

  const handleLogout = () => {
    logoutUser();
    setUsername('Discipulus');
    setPin('1234');
    setSchool('University High School');
    setMessage('Session reset');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
      <div className="classical-card-elevated rounded-3xl max-w-sm w-full shadow-2xl p-6 space-y-4 text-xs">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-sky-100">
          <span className="font-display font-bold text-slate-900 text-sm tracking-wider">
            Scholar Profile
          </span>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-sky-50 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Current user summary */}
        <div className="p-3.5 rounded-2xl bg-sky-50 border border-sky-200 flex items-center justify-between shadow-xs">
          <div>
            <div className="font-bold text-slate-900 text-sm">{user.username}</div>
            <div className="text-xs text-slate-600 font-editorial italic">
              {user.school || 'University High School'} • <span className="font-semibold text-sky-800 not-italic">{user.stats.totalPoints} pts</span>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="p-2 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
            title="Reset session"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleLoginSubmit} className="space-y-3.5 pt-1">
          <div>
            <label className="block text-[11px] text-slate-700 font-semibold mb-1">
              Scholar Name / Handle
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              placeholder="e.g. Cicero, Caesar, Tullia"
              className="w-full bg-white border border-sky-200 focus:border-sky-500 rounded-xl px-3 py-2 text-xs text-slate-900 outline-none transition-all shadow-xs"
            />
          </div>

          <div>
            <label className="block text-[11px] text-slate-700 font-semibold mb-1">
              Security PIN (4-6 digits)
            </label>
            <input
              type="password"
              maxLength={6}
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              required
              placeholder="••••"
              className="w-full bg-white border border-sky-200 focus:border-sky-500 rounded-xl px-3 py-2 text-xs text-slate-900 outline-none tracking-widest transition-all shadow-xs"
            />
          </div>

          <div>
            <label className="block text-[11px] text-slate-700 font-semibold mb-1">
              School / JCL Chapter
            </label>
            <input
              type="text"
              value={school}
              onChange={(e) => setSchool(e.target.value)}
              placeholder="e.g. University High School JCL"
              className="w-full bg-white border border-sky-200 focus:border-sky-500 rounded-xl px-3 py-2 text-xs text-slate-900 outline-none transition-all shadow-xs"
            />
          </div>

          {message && (
            <div className="text-xs text-sky-800 text-center font-medium pt-1">
              {message}
            </div>
          )}

          <div className="pt-2">
            <button
              type="submit"
              disabled={isSyncing}
              className="w-full py-3 bg-sky-600 hover:bg-sky-700 text-white font-bold text-xs rounded-xl shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <ShieldCheck className="w-4 h-4 text-white" />
              <span>Save & Sync Profile</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
