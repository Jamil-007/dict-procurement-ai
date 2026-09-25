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

export function uploadDocuments(
  ref: string,
  files: File[],
  docTypes: string[]
) {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  // Positional against `files` — the backend falls back to "Other".
  docTypes.forEach((type) => form.append("doc_types", type));
  return request<Procurement>(`/procurements/${ref}/documents`, {
    method: "POST",
    body: form,
  });
}

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
  patch: Partial<Pick<Finding, "severity" | "title" | "analysis" | "recommendation" | "decision" | "feedback">>
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
