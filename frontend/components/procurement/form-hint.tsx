'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const docFormMap = [
  {
    doc: 'Terms of Reference',
    forms: [
      { name: 'PPMP', primary: true },
      { name: 'Contract Form', primary: true },
      { name: 'APP', primary: false },
    ],
  },
  {
    doc: 'Market Study',
    forms: [{ name: 'Market Scoping Form', primary: true }],
  },
  {
    doc: 'Cost Breakdown',
    forms: [
      { name: 'PPMP', primary: false },
      { name: 'APP', primary: false, note: 'budget' },
    ],
  },
  {
    doc: 'Signed Contract',
    forms: [{ name: 'Contract Form', primary: false }],
  },
];

export function FormHint() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="mt-4 border-t border-zinc-100 pt-4">
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        className="flex w-full items-center gap-2 bg-transparent text-left font-medium text-zinc-600 transition-colors hover:text-zinc-900"
      >
        <motion.svg
          className="h-3.5 w-3.5 shrink-0 text-zinc-400"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          animate={{ rotate: isOpen ? 90 : 0 }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
        >
          <path d="M9 6l6 6-6 6" />
        </motion.svg>
        <span className="flex-1 text-[13px]">
          Which document produces which form?{' '}
          <span className="font-normal text-zinc-400">— reference</span>
        </span>
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.28, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="mt-4">
              <div className="overflow-hidden rounded-xl border border-zinc-200">
                {/* Table header */}
                <div className="grid grid-cols-[190px_1fr] gap-4 border-b border-zinc-200 bg-zinc-50 px-4 py-2.5 text-[10.5px] font-semibold uppercase tracking-wider text-zinc-400">
                  <div>Document</div>
                  <div>Forms it produces</div>
                </div>

                {/* Table rows */}
                {docFormMap.map((row, idx) => (
                  <div
                    key={row.doc}
                    className={`grid grid-cols-[190px_1fr] items-baseline gap-4 px-4 py-3.5 ${
                      idx > 0 ? 'border-t border-zinc-100' : ''
                    }`}
                  >
                    <div className="text-[13.5px] font-semibold tracking-tight text-zinc-900">
                      {row.doc}
                    </div>
                    <div className="flex flex-wrap items-baseline gap-0 text-sm text-zinc-500">
                      {row.forms.map((form, formIdx) => (
                        <span key={formIdx} className="flex items-baseline">
                          <span
                            className={`whitespace-nowrap ${
                              form.primary ? 'text-zinc-900' : ''
                            }`}
                          >
                            {form.name}
                          </span>
                          {form.note && (
                            <span className="ml-1.5 text-zinc-400">{form.note}</span>
                          )}
                          {formIdx < row.forms.length - 1 && (
                            <span className="mx-2 text-zinc-400">·</span>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}

                {/* Footer row */}
                <div className="grid grid-cols-[190px_1fr] gap-4 border-t border-zinc-200 bg-zinc-50 px-4 py-3.5">
                  <div className="text-[13.5px] font-semibold tracking-tight text-zinc-700">
                    Bidding annexes
                  </div>
                  <div className="text-sm text-zinc-500">
                    Any upload — issued blank, project header stamped
                  </div>
                </div>
              </div>

              {/* Microtip */}
              <p className="mt-2.5 text-[11.5px] leading-relaxed text-zinc-400">
                Detection reads each file's <b className="font-semibold text-zinc-500">contents</b>,
                not its name. Bold forms are auto-filled & pre-selected; you can always generate{' '}
                <b className="font-semibold text-zinc-500">any</b> form and fill it in manually.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
