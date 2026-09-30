/**
 * What the ingest layer can read, mirrored from `backend/ingest/loaders.py`.
 *
 * Filtering is by extension, not MIME type. Browsers report `.docx` and
 * `.xlsx` inconsistently — sometimes the full OpenXML type, sometimes
 * `application/octet-stream`, sometimes an empty string — so a MIME check
 * silently drops files the backend would have accepted.
 */
export const SUPPORTED_UPLOAD_EXTENSIONS = [
  '.pdf',
  '.docx',
  '.xlsx',
  '.xlsm',
  '.txt',
  '.md',
] as const;

export const UPLOAD_ACCEPT = SUPPORTED_UPLOAD_EXTENSIONS.join(',');

/** Matches MAX_UPLOAD_FILES on the backend. */
export const MAX_UPLOAD_FILES = 50;

export function isSupportedUpload(file: File): boolean {
  const name = file.name.toLowerCase();
  return SUPPORTED_UPLOAD_EXTENSIONS.some((ext) => name.endsWith(ext));
}

export function filterSupportedFiles(files: FileList | File[]): {
  accepted: File[];
  rejected: File[];
} {
  const accepted: File[] = [];
  const rejected: File[] = [];
  for (const file of Array.from(files)) {
    (isSupportedUpload(file) ? accepted : rejected).push(file);
  }
  return { accepted, rejected };
}

/** Human-readable list for error messages and empty states. */
export const SUPPORTED_UPLOAD_LABEL = 'PDF, Word, Excel or text';
