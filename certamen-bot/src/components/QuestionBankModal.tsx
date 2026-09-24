import React, { useState } from 'react';
import { useCertamen } from '../context/CertamenContext';
import { Category, DifficultyLevel, Question } from '../types/certamen';
import { FormattedText } from './FormattedText';
import { CATEGORY_NAMES } from './BuzzerArena';

const CATEGORIES = (Object.entries(CATEGORY_NAMES) as [Category, string][])
  .map(([id, label]) => ({ id, label }));
const PAGE = 50;
const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export const QuestionBankManager: React.FC = () => {
  const { questions, deleteCustomQuestion, addCustomQuestion, importQuestions, syncQuestionsFromCloud, isSyncing } = useCertamen();

  const [isAdding, setIsAdding] = useState<boolean>(false);
  const [importStatus, setImportStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<Category | 'all'>('all');
  const [selectedDifficulty, setSelectedDifficulty] = useState<DifficultyLevel | 'all'>('all');
  const [shown, setShown] = useState<number>(PAGE);

  // Form State
  const [newCategory, setNewCategory] = useState<Category>('grammar');
  const [newDifficulty, setNewDifficulty] = useState<DifficultyLevel>('novice');
  const [newTossup, setNewTossup] = useState<string>('');
  const [newAnswers, setNewAnswers] = useState<string>('');
  const [newExplanation, setNewExplanation] = useState<string>('');
  const [newBoni1Prompt, setNewBoni1Prompt] = useState<string>('');
  const [newBoni1Answers, setNewBoni1Answers] = useState<string>('');
  const [newBoni2Prompt, setNewBoni2Prompt] = useState<string>('');
  const [newBoni2Answers, setNewBoni2Answers] = useState<string>('');

  const filteredQuestions = questions.filter((q) => {
    if (selectedCategory !== 'all' && q.category !== selectedCategory) return false;
    if (selectedDifficulty !== 'all' && q.difficulty !== selectedDifficulty) return false;
    if (searchQuery) {
      const qLower = searchQuery.toLowerCase();
      const inTossup = q.tossup.toLowerCase().includes(qLower);
      const inAnswers = q.answers.some((a) => a.toLowerCase().includes(qLower));
      const inExpl = (q.explanation || '').toLowerCase().includes(qLower);
      return inTossup || inAnswers || inExpl;
    }
    return true;
  });

  const handleCreateQuestion = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTossup.trim() || !newAnswers.trim()) return;

    const parsedAnswers = newAnswers
      .split(',')
      .map((a) => a.trim())
      .filter(Boolean);

    const boniList = [];
    if (newBoni1Prompt.trim() && newBoni1Answers.trim()) {
      boniList.push({
        boniNumber: 1 as const,
        prompt: newBoni1Prompt.trim(),
        answers: newBoni1Answers.split(',').map((a) => a.trim()).filter(Boolean),
        points: 5,
      });
    }
    if (newBoni2Prompt.trim() && newBoni2Answers.trim()) {
      boniList.push({
        boniNumber: 2 as const,
        prompt: newBoni2Prompt.trim(),
        answers: newBoni2Answers.split(',').map((a) => a.trim()).filter(Boolean),
        points: 5,
      });
    }

    const newQ: Question = {
      id: `custom_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
      category: newCategory,
      difficulty: newDifficulty,
      tossup: newTossup.trim(),
      answers: parsedAnswers,
      boni: boniList.length > 0 ? boniList : undefined,
      explanation: newExplanation.trim() || undefined,
      source: 'Custom',
    };

    addCustomQuestion(newQ);
    setIsAdding(false);

    setNewTossup('');
    setNewAnswers('');
    setNewExplanation('');
    setNewBoni1Prompt('');
    setNewBoni1Answers('');
    setNewBoni2Prompt('');
    setNewBoni2Answers('');
  };

  const handleExportJSON = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(questions, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `uhsjcl_certamen_bank_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const inputEl = e.target;
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const json = JSON.parse(event.target?.result as string);
        if (Array.isArray(json)) {
          const count = importQuestions(json);
          setImportStatus(`Imported ${count} questions.`);
          setTimeout(() => setImportStatus(''), 3000);
        }
      } catch (err) {
        setImportStatus('That file is not valid JSON, so nothing was imported.');
      } finally {
        inputEl.value = '';
      }
    };
    reader.readAsText(file);
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Questions</h1>
          <p className="small muted">{questions.length} questions in the bank</p>
        </div>
        <div className="btn-row" style={{ margin: 0 }}>
          <button type="button" className="btn btn--primary" onClick={() => setIsAdding(!isAdding)}
            aria-expanded={isAdding}>
            {isAdding ? 'Close the form' : 'Add a question'}
          </button>
          <button
            type="button"
            className="btn"
            disabled={isSyncing}
            title="Fetch the latest questions from the Turso database"
            onClick={async () => {
              const count = await syncQuestionsFromCloud();
              setImportStatus(`Synced ${count} questions from Turso.`);
              setTimeout(() => setImportStatus(''), 3000);
            }}
          >
            {isSyncing && <span className="btn__spinner" aria-hidden="true" />}
            {isSyncing ? 'Syncing' : 'Sync from Turso'}
          </button>
          <button type="button" className="btn btn--quiet" onClick={handleExportJSON}>
            Export JSON
          </button>
          <label className="btn btn--quiet">
            Import JSON
            <input type="file" accept=".json,application/json" onChange={handleImportFile} className="visually-hidden" />
          </label>
        </div>
      </div>

      {importStatus && <p className="status-note" role="status">{importStatus}</p>}

      {isAdding && (
        <form onSubmit={handleCreateQuestion} className="panel" style={{ marginBottom: 'var(--space-6)' }}>
          <h2>New question</h2>
          <div className="grid">
            <div className="field span-6">
              <label htmlFor="q-subject">Subject</label>
              <select id="q-subject" value={newCategory} onChange={(e) => setNewCategory(e.target.value as Category)}>
                {CATEGORIES.map(({ id, label }) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </select>
            </div>
            <div className="field span-6">
              <label htmlFor="q-level">Level</label>
              <select id="q-level" value={newDifficulty} onChange={(e) => setNewDifficulty(e.target.value as DifficultyLevel)}>
                <option value="novice">Novice</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
              </select>
            </div>
          </div>

          <div className="field field--wide">
            <label htmlFor="q-tossup">Tossup <span className="field__required">Required</span></label>
            <textarea
              id="q-tossup"
              rows={3}
              value={newTossup}
              onChange={(e) => setNewTossup(e.target.value)}
              placeholder="Translate into English: 'Puer puellam videt.'"
              required
              style={{ minHeight: '5rem' }}
            />
          </div>

          <div className="field field--wide">
            <label htmlFor="q-answers">Accepted answers <span className="field__required">Required</span></label>
            <p className="field__help">Separate them with commas.</p>
            <input
              id="q-answers"
              type="text"
              value={newAnswers}
              onChange={(e) => setNewAnswers(e.target.value)}
              placeholder="The boy sees the girl, A boy sees a girl"
              required
            />
          </div>

          <div className="field field--wide">
            <label htmlFor="q-note">Note</label>
            <p className="field__help">Shown after the answer: a translation, or why the answer is what it is.</p>
            <input
              id="q-note"
              type="text"
              value={newExplanation}
              onChange={(e) => setNewExplanation(e.target.value)}
            />
          </div>

          <div className="btn-row">
            <button type="submit" className="btn btn--primary">Save to the bank</button>
            <button type="button" className="btn btn--quiet" onClick={() => setIsAdding(false)}>Cancel</button>
          </div>
        </form>
      )}

      <div className="search">
        <label className="visually-hidden" htmlFor="bank-search">Search the bank</label>
        <input
          id="bank-search"
          type="search"
          placeholder="Search questions or answers"
          value={searchQuery}
          onChange={(e) => { setSearchQuery(e.target.value); setShown(PAGE); }}
        />
      </div>

      <div className="tabs" role="group" aria-label="Subject">
        {[{ id: 'all' as const, label: 'All' }, ...CATEGORIES].map(({ id, label }) => (
          <button
            key={id}
            type="button"
            className={`tabs__tab${selectedCategory === id ? ' is-current' : ''}`}
            aria-pressed={selectedCategory === id}
            onClick={() => { setSelectedCategory(id); setShown(PAGE); }}
          >
            {label}
          </button>
        ))}
      </div>

      {filteredQuestions.length === 0 ? (
        <div className="empty">
          <h3>No questions match</h3>
          <p style={{ margin: '0 auto' }}>Try a different subject, or clear the search.</p>
        </div>
      ) : (
        <>
          <p className="count-note">
            Showing {Math.min(shown, filteredQuestions.length)} of {filteredQuestions.length}
          </p>
          <div className="catalog-items">
            {filteredQuestions.slice(0, shown).map((q, idx) => (
              <div key={q.id || idx} className="catalog-item" style={{ display: 'block' }}>
                <div className="entry__head">
                  <p className="label">
                    {CATEGORY_NAMES[q.category] ?? q.category} &middot; {capitalise(q.difficulty)}
                    {q.id.startsWith('custom_') && <> &middot; Yours</>}
                  </p>
                  {q.id.startsWith('custom_') && (
                    <button
                      type="button"
                      className="btn btn--danger btn--small"
                      onClick={() => {
                        if (confirm('Delete this question?')) deleteCustomQuestion(q.id);
                      }}
                    >
                      Delete
                    </button>
                  )}
                </div>
                <p className="entry__text"><FormattedText text={q.tossup} /></p>
                <p className="entry__answers">Answer: {q.answers.join(' · ')}</p>
              </div>
            ))}
          </div>
          {filteredQuestions.length > shown && (
            <button type="button" className="btn more" onClick={() => setShown(shown + PAGE)}>
              Show {Math.min(PAGE, filteredQuestions.length - shown)} more
            </button>
          )}
        </>
      )}
    </>
  );
};
