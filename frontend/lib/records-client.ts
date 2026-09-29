/**
 * Client for the procurement record, knowledge and review endpoints.
 *
 * Separate from api-client.ts, which serves the Procurement Analyst chat.
 */

import type {
  Dimension,
  Finding,
  KnowledgeEntry,
  KnowledgeResponse,
  Procurement,
  ProcurementCreate,
  RunReviewResponse,
} from "@/types/records";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    // FastAPI puts the reason in `detail`; fall back to the status text so the
    // user never sees a bare "failed to fetch".
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* body was not JSON */
    }
    throw new Error(detail || `Request failed (${response.status})`);
  }

  return response.json() as Promise<T>;
}

// --- procurements ---

export const listProcurements = () =>
  request<Procurement[]>("/procurements");

export const getProcurement = (ref: string) =>
  request<Procurement>(`/procurements/${ref}`);

export const createProcurement = (data: ProcurementCreate) =>
  request<Procurement>("/procurements", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const patchProcurement = (ref: string, patch: Partial<ProcurementCreate> & { report_notes?: string }) =>
  request<Procurement>(`/procurements/${ref}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export async function deleteProcurement(ref: string) {
  // 204, so there is no body to parse.
  const response = await fetch(`${API_BASE_URL}/procurements/${ref}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Could not delete ${ref} (${response.status})`);
  }
}

export async function uploadDocuments(ref: string, files: File[]): Promise<Procurement> {
  // One request PER FILE, not one batched request for all of them. Cloud Run's
  // Google Front End caps each request body at 32 MiB, so batching several
  // documents into a single multipart POST 413s in production once the combined
  // size crosses that line — even though every individual file is within the
  // backend's 25 MB per-file limit (which is why batching still worked locally,
  // where there is no such edge cap). Sending one file at a time keeps every
  // request comfortably under the cap.
  //
  // Sequential, not parallel: each call appends to the record's document list
  // and the backend runs a single instance, so concurrent writes to the same
  // record would race. We return the final (fully-updated) record.
  //
  // No doc_types sent — the backend works out the type of each document and
  // setDocumentType corrects it if the inference is wrong.
  let latest: Procurement | undefined;
  for (const file of files) {
    const form = new FormData();
    form.append("files", file);
    latest = await request<Procurement>(`/procurements/${ref}/documents`, {
      method: "POST",
      body: form,
    });
  }
  // No files supplied: return the record unchanged rather than throwing.
  return latest ?? (await getProcurement(ref));
}

export const setDocumentType = (ref: string, documentId: string, docType: string) =>
  request<Procurement>(`/procurements/${ref}/documents/${documentId}`, {
    method: "PATCH",
    body: JSON.stringify({ doc_type: docType }),
  });

export const deleteDocument = (ref: string, documentId: string) =>
  request<Procurement>(`/procurements/${ref}/documents/${documentId}`, {
    method: "DELETE",
  });

export const finalizeProcurement = (ref: string) =>
  request<{ ref: string; status: string; finalized_at: string | null; finalized_by: string | null }>(
    `/procurements/${ref}/finalize`,
    { method: "POST" }
  );

// --- review ---

export const listDimensions = () => request<Dimension[]>("/review/dimensions");

export const runReview = (ref: string) =>
  request<RunReviewResponse>(`/procurements/${ref}/review`, { method: "POST" });

export const listFindings = (ref: string) =>
  request<Finding[]>(`/procurements/${ref}/findings`);

export const patchFinding = (
  ref: string,
  findingId: string,
  patch: Partial<
    Pick<
      Finding,
      | "severity"
      | "title"
      | "analysis"
      | "recommendation"
      | "decision"
      | "rejection_reason"
      | "rejection_note"
      | "feedback"
    >
  >
) =>
  request<Finding>(`/procurements/${ref}/findings/${findingId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const addComment = (ref: string, findingId: string, text: string) =>
  request<Finding>(`/procurements/${ref}/findings/${findingId}/comments`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });

// --- knowledge ---

export function listKnowledge(params: { category?: string; search?: string } = {}) {
  const query = new URLSearchParams();
  if (params.category) query.set("category", params.category);
  if (params.search) query.set("search", params.search);
  const suffix = query.toString() ? `?${query}` : "";
  return request<KnowledgeResponse>(`/knowledge${suffix}`);
}

export const getKnowledgeEntry = (entryId: string) =>
  request<KnowledgeEntry>(`/knowledge/${entryId}`);

/**
 * Direct URLs to the stored PDFs. These are plain <a href> and <iframe src>
 * targets rather than fetches, so the browser handles the download and the
 * built-in viewer. `inline` renders in place instead of prompting a save.
 */
export const documentUrl = (ref: string, documentId: string, inline = false) =>
  `${API_BASE_URL}/procurements/${ref}/documents/${documentId}/download${
    inline ? "?inline=true" : ""
  }`;

export const knowledgeUrl = (entryId: string, inline = false) =>
  `${API_BASE_URL}/knowledge/${entryId}/download${inline ? "?inline=true" : ""}`;
