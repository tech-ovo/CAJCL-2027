import React, { useEffect, useRef, useState } from 'react';
import { useCertamen } from '../context/CertamenContext';

// The guest profile's chapter; not a real one, so the field starts empty.
const GUEST_CHAPTER = 'Roma Antiqua Academy';

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
  const [school, setSchool] = useState<string>(user.school === GUEST_CHAPTER ? '' : user.school || '');
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
    setSchool('');
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
          <span className="small muted">{user.school === GUEST_CHAPTER ? 'No chapter' : user.school}</span>
          <span className="tabula__code">{user.stats.totalPoints} pts</span>
        </div>
      </div>

      <form onSubmit={handleLoginSubmit}>
        <div className="field">
          <label htmlFor="profile-name">Name</label>
          <p className="field__help">Only for signing in; the leaderboard ranks chapters, not players.</p>
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
          <p className="field__help">Your XP counts toward this chapter on the leaderboard. Spell it the way your chapter-mates do.</p>
          <input
            id="profile-school"
            type="text"
            value={school}
            onChange={(e) => setSchool(e.target.value)}
            placeholder="University High School"
            required
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
