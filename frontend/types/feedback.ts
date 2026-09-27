// Feedback types for the AI Feedback Bank

export interface FeedbackItem {
  feature: string;
  context_key: string;
  field_path?: string | null;
  thread_id: string;
  signal_type: 'implicit' | 'explicit';
  ai_value?: string | null;
  corrected_value?: string | null;
  rating?: 'up' | 'down' | null;
  note?: string | null;
  source_ref?: string | null;
  input_context?: string | null;
  metadata?: Record<string, unknown>;
}
