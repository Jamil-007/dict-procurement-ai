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
  documents?: { filename: string; doc_types: string[] }[];
}

/**
 * Response shape of the ref-based `/procurements/{ref}/forms/detect` endpoint
 * (see backend/server.py). A superset of `FormRecommendation`/`DetectResult`
 * so it can stand in for them wherever those are expected (e.g. FormGenerator).
 */
export interface RefFormRecommendation extends FormRecommendation {
  source_doc_types: string[];
  present: string[];
  missing: string[];
}

export interface RefDetectResult {
  doc_types: string[];
  forms: Record<FormKey, RefFormRecommendation>;
}

export interface UploadFormsResult {
  thread_id: string;
  has_docs: boolean;
  filenames: string[];
}

export interface FormFieldValue {
  value: string | null;
  group: FormGroup;
}

export type FormFields = Record<string, FormFieldValue>;

export interface GenerateRequest {
  thread_id: string;
  form_keys: FormKey[];
  overrides?: Partial<Record<FormKey, Record<string, string | null>>>;
}
