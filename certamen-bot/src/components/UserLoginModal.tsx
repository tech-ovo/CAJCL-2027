import React, { useEffect, useRef, useState } from 'react';
import { useCertamen } from '../context/CertamenContext';

interface UserLoginModalProps {
  isOpen: boolean;
  onClose: () => void;
}

/* A native <dialog>, as on the convention site: the browser handles the focus
 * trap, Escape and the backdrop. */
export const UserLoginModal: React.FC<UserLoginModalProps> = ({ isOpen, onClose }) => {
  const { user, loginUser, logoutUser, isSyncing } = useCertamen();
  const dialogRef = useRef<HTMLDialogElement>(null);

  const [username, setUsername] = useState<string>(user.username);
  const [pin, setPin] = useState<string>(user.pin);
  const [school, setSchool] = useState<string>(user.school || 'University High School');
  const [message, setMessage] = useState<string>('');

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (isOpen && !dialog.open) dialog.showModal();
    if (!isOpen && dialog.open) dialog.close();
  }, [isOpen]);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) return;

    setMessage('Saving your profile…');
    const success = await loginUser(username.trim(), pin.trim(), school.trim());
    if (success) {
      setMessage('Saved.');
      setTimeout(() => {
        onClose();
        setMessage('');
      }, 500);
    } else {
      setMessage('Your profile could not be saved. Check your connection and try again.');
    }
  };

  const handleLogout = () => {
    logoutUser();
    setUsername('Discipulus');
    setPin('1234');
    setSchool('University High School');
    setMessage('Signed out. You are playing as a guest.');
  };

  return (
    <dialog
      ref={dialogRef}
      className="dialog"
      aria-labelledby="profile-title"
      onClose={onClose}
      onClick={(e) => {
        // A click on the backdrop lands on the dialog element itself, but so
        // does one on its padding; only the first is outside the box.
        if (e.target !== dialogRef.current) return;
        const box = dialogRef.current.getBoundingClientRect();
        const inside = e.clientX >= box.left && e.clientX <= box.right
          && e.clientY >= box.top && e.clientY <= box.bottom;
        if (!inside) onClose();
      }}
    >
      <button type="button" className="btn btn--quiet btn--small dialog__close" onClick={onClose}>
        Close
      </button>
      <h2 id="profile-title">Your profile</h2>

      <div className="tabula">
        <p className="label">Playing as</p>
        <p className="tabula__name">{user.username}</p>
        <div className="tabula__row">
          <span className="small muted">{user.school || 'University High School'}</span>
          <span className="tabula__code">{user.stats.totalPoints} pts</span>
        </div>
      </div>

      <form onSubmit={handleLoginSubmit}>
        <div className="field">
          <label htmlFor="profile-name">Name</label>
          <p className="field__help">Shown on the leaderboard.</p>
          <input
            id="profile-name"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoComplete="nickname"
          />
        </div>

        <div className="field">
          <label htmlFor="profile-pin">PIN</label>
          <p className="field__help">Four to six digits, so nobody else can post scores under your name.</p>
          <input
            id="profile-pin"
            type="password"
            inputMode="numeric"
            maxLength={6}
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            required
            className="mono"
          />
        </div>

        <div className="field">
          <label htmlFor="profile-school">Chapter</label>
          <input
            id="profile-school"
            type="text"
            value={school}
            onChange={(e) => setSchool(e.target.value)}
            placeholder="University High School"
          />
        </div>

        {message && <p className="status-note" role="status">{message}</p>}

        <div className="btn-row">
          <button type="submit" className="btn btn--primary" disabled={isSyncing}>
            {isSyncing && <span className="btn__spinner" aria-hidden="true" />}
            Save profile
          </button>
          <button type="button" className="btn btn--small nav__signout" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </form>
    </dialog>
  );
};
