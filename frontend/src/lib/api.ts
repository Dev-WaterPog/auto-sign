import { getAccessToken } from "@/lib/access-token";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function authHeaders(extra?: Record<string, string>): HeadersInit {
  const token = getAccessToken();
  return { ...extra, ...(token ? { "X-Access-Token": token } : {}) };
}

async function throwIfError(res: Response): Promise<void> {
  if (res.ok) return;
  let detail = `${res.status} ${res.statusText}`;
  try {
    const body = (await res.json()) as { detail?: string };
    if (body.detail) detail = body.detail;
  } catch {
    // response wasn't JSON; fall back to the status text above
  }
  throw new ApiError(res.status, detail);
}

async function parseOrThrow<T>(res: Response): Promise<T> {
  await throwIfError(res);
  return res.json() as Promise<T>;
}

export type UploadedFile = {
  id: string;
  filename: string;
  url: string;
};

export type SignResult = {
  job_id: string;
  download_url: string;
  signature_placed: boolean;
  date_placed: boolean;
};

export async function uploadTemplate(file: File): Promise<UploadedFile> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/api/templates`, { method: "POST", headers: authHeaders(), body: form });
  return parseOrThrow<UploadedFile>(res);
}

export async function uploadSignature(file: File): Promise<UploadedFile> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/api/signatures`, { method: "POST", headers: authHeaders(), body: form });
  return parseOrThrow<UploadedFile>(res);
}

export async function listTemplates(): Promise<UploadedFile[]> {
  const res = await fetch(`${API_URL}/api/templates`, { headers: authHeaders() });
  return parseOrThrow<UploadedFile[]>(res);
}

export async function listSignatures(): Promise<UploadedFile[]> {
  const res = await fetch(`${API_URL}/api/signatures`, { headers: authHeaders() });
  return parseOrThrow<UploadedFile[]>(res);
}

export type SignaturePosition = "right" | "above" | "below";

export async function signDocument(params: {
  templateId: string;
  signatureId: string;
  signatureAnchor?: string;
  dateAnchor?: string;
  dateFormat?: string;
  signaturePosition?: SignaturePosition;
  /** ISO "YYYY-MM-DD"; defaults to today on the backend when omitted. */
  dateValue?: string;
}): Promise<SignResult> {
  const res = await fetch(`${API_URL}/api/sign`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      template_id: params.templateId,
      signature_id: params.signatureId,
      signature_anchor: params.signatureAnchor,
      date_anchor: params.dateAnchor,
      date_format: params.dateFormat ?? "%d/%m/%Y",
      signature_position: params.signaturePosition ?? "right",
      date_value: params.dateValue,
    }),
  });
  return parseOrThrow<SignResult>(res);
}

export function apiUrl(path: string): string {
  return `${API_URL}${path}`;
}

export type SignedDocument = {
  blob: Blob;
  filename: string;
};

async function parseBlobOrThrow(res: Response): Promise<Blob> {
  await throwIfError(res);
  return res.blob();
}

/** Uploads a template PDF + signature PNG directly and gets the signed PDF back in one round trip. */
export async function signDocumentDirect(
  templateFile: File,
  signatureFile: File,
  dateValue?: string,
): Promise<SignedDocument> {
  const form = new FormData();
  form.append("template", templateFile);
  form.append("signature", signatureFile);
  if (dateValue) form.append("date_value", dateValue);

  const res = await fetch(`${API_URL}/api/sign-document`, { method: "POST", headers: authHeaders(), body: form });
  const blob = await parseBlobOrThrow(res);
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "signed-document.pdf";
  return { blob, filename };
}

export type SignedDocumentWithPlacement = SignedDocument & {
  signaturePlaced: boolean;
  datePlaced: boolean;
};

/**
 * Uploads a template PDF + signature PNG, signs by matching `signatureAnchor`
 * text (instead of a `{{signature}}` placeholder) and stamping the signature
 * relative to it, then downloads the result. Useful for real-world forms
 * (e.g. "( Name )" signature lines) that don't contain a placeholder.
 */
export async function signDocumentByAnchor(params: {
  templateFile: File;
  signatureFile: File;
  signatureAnchor: string;
  signaturePosition: SignaturePosition;
  dateValue?: string;
}): Promise<SignedDocumentWithPlacement> {
  const [template, signature] = await Promise.all([
    uploadTemplate(params.templateFile),
    uploadSignature(params.signatureFile),
  ]);

  const result = await signDocument({
    templateId: template.id,
    signatureId: signature.id,
    signatureAnchor: params.signatureAnchor,
    signaturePosition: params.signaturePosition,
    dateValue: params.dateValue,
  });

  const res = await fetch(apiUrl(result.download_url), { headers: authHeaders() });
  const blob = await parseBlobOrThrow(res);

  return {
    blob,
    filename: `signed-${result.job_id}.pdf`,
    signaturePlaced: result.signature_placed,
    datePlaced: result.date_placed,
  };
}
