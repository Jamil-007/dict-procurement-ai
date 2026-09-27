'use client';

import { Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { FormReview } from '@/components/procurement/form-review';
import type { FormKey } from '@/types/forms';

function ReviewPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const threadId = searchParams.get('session');
  const formKeysParam = searchParams.get('forms');

  if (!threadId || !formKeysParam) {
    return (
      <div className="max-w-[980px] mx-auto px-5 py-10">
        <div className="text-zinc-600 text-sm">
          Missing session or forms parameters. Please go back and try again.
        </div>
        <button
          onClick={() => router.push('/')}
          className="mt-4 px-4 py-2 text-sm font-medium rounded-md border border-zinc-300 bg-white hover:bg-zinc-50"
        >
          Go back
        </button>
      </div>
    );
  }

  const formKeys = formKeysParam.split(',') as FormKey[];

  return (
    <div>
      <div className="sticky top-0 z-10 bg-white/90 backdrop-blur-sm border-b border-zinc-200">
        <div className="max-w-[980px] mx-auto px-5 py-4 flex items-center justify-between gap-4">
          <div className="flex flex-col gap-0.5">
            <span className="text-base font-semibold tracking-tight">Review & download</span>
            <span className="text-xs text-zinc-600">
              Fields not found in your documents are marked [TBD] — nothing is invented. Edit any
              field before downloading.
            </span>
          </div>
          <button
            onClick={() => router.push('/')}
            className="px-4 py-2 text-sm font-medium text-zinc-600 hover:text-black transition-all"
          >
            Back
          </button>
        </div>
      </div>

      <div className="max-w-[980px] mx-auto px-5 py-6 pb-24">
        <FormReview threadId={threadId} formKeys={formKeys} />
      </div>
    </div>
  );
}

export default function ReviewPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-[980px] mx-auto px-5 py-10">
          <div className="text-zinc-500 text-sm">Loading...</div>
        </div>
      }
    >
      <ReviewPageContent />
    </Suspense>
  );
}
