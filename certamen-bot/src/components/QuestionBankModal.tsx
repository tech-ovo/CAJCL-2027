import React, { useState } from 'react';
import { useCertamen } from '../context/CertamenContext';
import { Category, DifficultyLevel, Question } from '../types/certamen';
import {
  Search,
  Trash2,
  CheckCircle2,
  Plus,
  Download,
  Upload,
  RefreshCw,
  X,
  BookOpen,
} from 'lucide-react';
import { FormattedText } from './FormattedText';

const CATEGORIES: { id: Category; label: string }[] = [
  { id: 'grammar', label: 'Grammar' },
  { id: 'mythology', label: 'Mythology' },
  { id: 'history', label: 'History' },
  { id: 'culture', label: 'Culture' },
  { id: 'literature', label: 'Literature' },
];

export const QuestionBankManager: React.FC = () => {
  const { questions, deleteCustomQuestion, addCustomQuestion, importQuestions, syncQuestionsFromCloud, isSyncing } = useCertamen();

  const [isAdding, setIsAdding] = useState<boolean>(false);
  const [importStatus, setImportStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<Category | 'all'>('all');
  const [selectedDifficulty, setSelectedDifficulty] = useState<DifficultyLevel | 'all'>('all');

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
          setImportStatus(`Imported ${count} questions`);
          setTimeout(() => setImportStatus(''), 3000);
        }
      } catch (err) {
        setImportStatus('Error parsing JSON');
      } finally {
        inputEl.value = '';
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-sky-200/80">
        <div>
          <h2 className="text-xl font-display font-bold text-slate-900 flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-sky-600" />
            <span>Question Treasury</span>
          </h2>
          <div className="text-xs text-slate-500 font-editorial italic">{questions.length} questions available in bank</div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsAdding(!isAdding)}
            className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>{isAdding ? 'Cancel' : 'Add Question'}</span>
          </button>

          <button
            onClick={async () => {
              const count = await syncQuestionsFromCloud();
              setImportStatus(`Successfully synced ${count} questions`);
              setTimeout(() => setImportStatus(''), 3000);
            }}
            disabled={isSyncing}
            className="px-3.5 py-2 rounded-xl bg-white hover:bg-sky-50 text-slate-700 hover:text-sky-900 text-xs font-semibold border border-sky-200 flex items-center gap-1.5 transition-all disabled:opacity-50 cursor-pointer shadow-xs"
            title="Sync from Google Sheets Cloud"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-sky-600 ${isSyncing ? 'animate-spin' : ''}`} />
            <span>Sync Cloud</span>
          </button>

          <button
            onClick={handleExportJSON}
            className="p-2 rounded-xl bg-white hover:bg-sky-50 text-slate-600 hover:text-sky-900 border border-sky-200 transition-all cursor-pointer shadow-xs"
            title="Export JSON Question Bank"
          >
            <Download className="w-4 h-4" />
          </button>

          <label
            className="p-2 rounded-xl bg-white hover:bg-sky-50 text-slate-600 hover:text-sky-900 border border-sky-200 cursor-pointer transition-all shadow-xs"
            title="Import JSON Question Bank"
          >
            <Upload className="w-4 h-4" />
            <input type="file" accept=".json,application/json" onChange={handleImportFile} className="hidden" />
          </label>
        </div>
      </div>

      {/* Status Alert */}
      {importStatus && (
        <div className="bg-sky-100 border border-sky-300 text-sky-900 text-xs px-4 py-2.5 rounded-2xl flex items-center gap-2 shadow-xs">
          <CheckCircle2 className="w-4 h-4 text-sky-700 shrink-0" />
          <span className="font-medium">{importStatus}</span>
        </div>
      )}

      {/* Add Question Collapsible Form */}
      {isAdding && (
        <div className="classical-card-elevated rounded-3xl p-6 space-y-4">
          <form onSubmit={handleCreateQuestion} className="space-y-4">
            <div className="flex items-center justify-between text-xs font-bold text-slate-900 pb-2 border-b border-sky-100">
              <span className="font-display uppercase tracking-wider">Draft New Certamen Question</span>
              <button
                type="button"
                onClick={() => setIsAdding(false)}
                className="text-slate-400 hover:text-slate-700 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-slate-700 font-semibold mb-1">Subject</label>
                <select
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value as Category)}
                  className="w-full bg-white border border-sky-200 rounded-xl px-3 py-2 text-xs text-slate-900 outline-none focus:border-sky-500"
                >
                  {CATEGORIES.map(({ id, label }) => (
                    <option key={id} value={id}>{label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[11px] text-slate-700 font-semibold mb-1">Difficulty</label>
                <select
                  value={newDifficulty}
                  onChange={(e) => setNewDifficulty(e.target.value as DifficultyLevel)}
                  className="w-full bg-white border border-sky-200 rounded-xl px-3 py-2 text-xs text-slate-900 outline-none focus:border-sky-500"
                >
                  <option value="novice">Novice</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-[11px] text-slate-700 font-semibold mb-1">Tossup Question Text</label>
              <textarea
                rows={2}
                value={newTossup}
                onChange={(e) => setNewTossup(e.target.value)}
                placeholder="e.g. Translate into English: 'Puer puellam videt.'"
                required
                className="w-full bg-white border border-sky-200 focus:border-sky-500 rounded-xl p-3 text-xs text-slate-900 outline-none font-editorial text-sm"
              />
            </div>

            <div>
              <label className="block text-[11px] text-slate-700 font-semibold mb-1">
                Accepted Answers (comma separated)
              </label>
              <input
                type="text"
                value={newAnswers}
                onChange={(e) => setNewAnswers(e.target.value)}
                placeholder="e.g. The boy sees the girl, A boy sees a girl"
                required
                className="w-full bg-white border border-sky-200 focus:border-sky-500 rounded-xl px-3 py-2 text-xs text-slate-900 outline-none"
              />
            </div>

            <div>
              <label className="block text-[11px] text-slate-700 font-semibold mb-1">Explanation or Notes (Optional)</label>
              <input
                type="text"
                value={newExplanation}
                onChange={(e) => setNewExplanation(e.target.value)}
                placeholder="Optional notes or grammatical breakdown"
                className="w-full bg-white border border-sky-200 rounded-xl px-3 py-2 text-xs text-slate-900 outline-none"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsAdding(false)}
                className="px-4 py-2 rounded-xl text-xs text-slate-600 hover:text-slate-900 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2 rounded-xl bg-sky-600 hover:bg-sky-700 text-white font-bold text-xs shadow-sm transition-all cursor-pointer"
              >
                Save to Bank
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Filter & Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-sky-200/80">
        {/* Search Input */}
        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search questions or answers..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-white border border-sky-200 focus:border-sky-500 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 placeholder-slate-400 outline-none transition-all shadow-xs"
          />
        </div>

        {/* Categories */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            onClick={() => setSelectedCategory('all')}
            className={`px-3 py-1 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
              selectedCategory === 'all'
                ? 'bg-sky-600 text-white shadow-sm'
                : 'text-slate-600 hover:bg-sky-50'
            }`}
          >
            All
          </button>
          {CATEGORIES.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setSelectedCategory(id)}
              className={`px-3 py-1 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                selectedCategory === id
                  ? 'bg-sky-600 text-white shadow-sm'
                  : 'text-slate-600 hover:bg-sky-50'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Questions List */}
      <div className="space-y-2.5 max-h-[600px] overflow-y-auto pr-1">
        {filteredQuestions.length === 0 ? (
          <div className="py-16 text-center text-xs text-slate-500 font-editorial italic text-base">
            No questions match the current filter.
          </div>
        ) : (
          filteredQuestions.map((q, idx) => (
            <div
              key={q.id || idx}
              className="p-4 rounded-2xl bg-white border border-sky-100 hover:border-sky-300 transition-all space-y-2.5 text-xs shadow-xs"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] uppercase font-bold text-sky-900 px-2 py-0.5 rounded-full bg-sky-50 border border-sky-200">
                    {q.category}
                  </span>
                  <span className="text-slate-300">•</span>
                  <span className="capitalize text-slate-500 font-medium">{q.difficulty}</span>
                </div>

                {q.id.startsWith('custom_') && (
                  <button
                    onClick={() => {
                      if (confirm('Delete this custom question?')) {
                        deleteCustomQuestion(q.id);
                      }
                    }}
                    className="text-slate-400 hover:text-rose-600 p-1 transition-colors cursor-pointer"
                    title="Delete question"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              <div className="text-slate-900 font-editorial text-sm sm:text-base leading-relaxed">
                <FormattedText text={q.tossup} />
              </div>

              <div className="flex flex-wrap gap-1.5 pt-0.5">
                {q.answers.map((ans, aIdx) => (
                  <span
                    key={aIdx}
                    className="px-2.5 py-0.5 rounded-lg bg-sky-50 text-sky-950 border border-sky-200 font-medium text-[11px]"
                  >
                    {ans}
                  </span>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
