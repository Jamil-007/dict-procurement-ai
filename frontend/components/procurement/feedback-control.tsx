'use client';
import React, { useState } from 'react';

interface FeedbackControlProps {
  rating: 'up' | 'down' | null;
  note: string;
  onRate: (r: 'up' | 'down' | null) => void;
  onNote: (n: string) => void;
}

export function FeedbackControl({ rating, note, onRate, onNote }: FeedbackControlProps) {
  const [expanded, setExpanded] = useState(false);
  const shown = rating !== null || expanded;
  return (
    <div className="relative">
      <div className="flex items-center gap-1">
        <button
          type="button"
          aria-label="Feedback"
          onClick={() => setExpanded(true)}
          className={`${shown ? 'hidden' : 'block group-hover:hidden group-focus-within:hidden'} text-zinc-300 hover:text-zinc-500 px-1.5 leading-none rounded-md`}
        >⋯</button>
        <div className={`items-center gap-1 ${shown ? 'flex' : 'hidden group-hover:flex group-focus-within:flex'}`}>
          <button
            type="button"
            aria-label="Correct"
            onClick={() => onRate(rating === 'up' ? null : 'up')}
            className={`w-7 h-6 grid place-items-center rounded-md border text-xs transition ${
              rating === 'up' ? 'bg-green-50 border-green-600 text-green-700' : 'bg-white border-zinc-200 text-zinc-400 hover:border-zinc-400'
            }`}
          >👍</button>
          <button
            type="button"
            aria-label="Wrong"
            onClick={() => onRate(rating === 'down' ? null : 'down')}
            className={`w-7 h-6 grid place-items-center rounded-md border text-xs transition ${
              rating === 'down' ? 'bg-amber-50 border-amber-600 text-amber-700' : 'bg-white border-zinc-200 text-zinc-400 hover:border-zinc-400'
            }`}
          >👎</button>
        </div>
      </div>
      {rating === 'down' && (
        <textarea
          value={note}
          onChange={(e) => onNote(e.target.value)}
          placeholder="What's wrong? (optional)"
          className="mt-2 w-full border border-zinc-300 rounded-md px-2.5 py-2 text-[13px] focus:outline-none focus:border-black"
        />
      )}
    </div>
  );
}
