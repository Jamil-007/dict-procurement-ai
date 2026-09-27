// Form types for procurement document generation

export type FormKey =
  | 'ppmp'
  | 'market'
  | 'app'
  | 'contract'
  | 'bidform'
  | 'price_local'
  | 'price_abroad'
  | 'bsd'
  | 'oss'
  | 'psd';

export type FormGroup = 'A_rich' | 'B_annex';

export interface FormCatalogItem {
  key: FormKey;
  name: string;
  group: FormGroup;
  ext: string;
  fill_level: 'rich' | 'annex';
}

export interface FormRecommendation {
  available: boolean;
  recommended: boolean;
  reason: string;
}

export interface DetectResult {
  doc_types: string[];
  forms: Record<FormKey, FormRecommendation>;
}

export interface FormFieldValue {
  value: string | null;
  group: FormGroup;
}

export type FormFields = Record<string, FormFieldValue>;

export interface GenerateRequest {
  thread_id: string;
  form_keys: FormKey[];
  overrides?: Record<FormKey, Record<string, string | null>>;
}
