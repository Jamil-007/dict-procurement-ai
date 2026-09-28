'use client';
import { useState, useCallback } from 'react';
import { apiClient } from '@/lib/api-client';
import type { FeedbackItem } from '@/types/feedback';

export type Rating = 'up' | 'down' | null;
type RatingState = Record<string, Record<string, { rating: Rating; note: string }>>;

export function useFeedbackCapture() {
  const [ratings, setRatings] = useState<RatingState>({});
  const setRating = useCallback((key: string, field: string, rating: Rating) => {
    setRatings((prev) => ({ ...prev, [key]: { ...prev[key], [field]: { rating, note: prev[key]?.[field]?.note ?? '' } } }));
  }, []);
  const setNote = useCallback((key: string, field: string, note: string) => {
    setRatings((prev) => ({ ...prev, [key]: { ...prev[key], [field]: { rating: prev[key]?.[field]?.rating ?? null, note } } }));
  }, []);
  const submit = useCallback((items: FeedbackItem[]) => {
    if (items.length) void apiClient.submitFeedback(items); // best-effort, never blocks
  }, []);
  return { ratings, setRating, setNote, submit };
}
