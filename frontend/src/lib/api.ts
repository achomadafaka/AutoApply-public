const API_ROOT = import.meta.env.VITE_API_ROOT ?? "http://localhost:8000";
const API_BASE = import.meta.env.VITE_API_BASE ?? `${API_ROOT}/v1`;

async function request<T>(url: string, options: RequestInit = {}, timeoutMs = 6000): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
      signal: options.signal ?? controller.signal
    });
  } catch (err) {
    if (controller.signal.aborted) {
      throw new Error("Request timed out", { cause: err });
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
  if (!res.ok) {
    const body = await res.text();
    let message = `Request failed (HTTP ${res.status}).`;
    try {
      const parsed = JSON.parse(body);
      if (typeof parsed?.error?.message === "string") message = parsed.error.message;
    } catch {
      // Avoid displaying a raw HTML error page.
    }
    throw new Error(message);
  }
  return (await res.json()) as T;
}

export function getHealth(): Promise<{ status: string }> {
  return request(`${API_ROOT}/health`);
}

export function getAIHealth() {
  return request(`${API_BASE}/ai/health`);
}

export function listJobs(limit = 5) {
  return request(`${API_BASE}/jobs?limit=${limit}`);
}

export function getSettings(): Promise<{ daily_limit: number }> {
  return request(`${API_BASE}/settings`);
}

export function updateSettings(payload: {
  daily_limit?: number;
}) {
  return request(`${API_BASE}/settings`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function listApplications({
  limit = 20,
  offset = 0,
  state,
  platform
}: {
  limit?: number;
  offset?: number;
  state?: string;
  platform?: string;
} = {}) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (state) params.set("state", state);
  if (platform) params.set("platform", platform);
  return request(`${API_BASE}/applications?${params.toString()}`);
}

export function getApplication(appId: string) {
  return request(`${API_BASE}/applications/${appId}`);
}

export function getApplicationStats() {
  return request(`${API_BASE}/applications/stats`);
}

export function getApplicationHistory(appId: string) {
  return request(`${API_BASE}/applications/${appId}/history`);
}

export function createApplication(payload: {
  job_id: string;
  platform: string;
  mode: string;
}) {
  return request(`${API_BASE}/applications`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getCvWorkspace(): Promise<{ baselines: { id: string; label: string }[]; drafting_protocol_loaded: boolean }> {
  return request(`${API_BASE}/profile/cv-workspace`);
}

export function cvPreviewUrl(resumeId: string) {
  return `${API_BASE}/profile/cv-workspace/${encodeURIComponent(resumeId)}/preview`;
}

export function startApplication(appId: string, workspaceResumeId?: string) {
  return request(`${API_BASE}/applications/${appId}/start`, {
    method: "POST",
    ...(workspaceResumeId ? { body: JSON.stringify({ workspace_resume_id: workspaceResumeId }) } : {})
  });
}

export function completeApplication(appId: string) {
  return request(`${API_BASE}/applications/${appId}/complete`, { method: "POST" });
}

export function pauseApplication(appId: string) {
  return request(`${API_BASE}/applications/${appId}/pause`, { method: "POST" });
}

export function resumeApplication(appId: string) {
  return request(`${API_BASE}/applications/${appId}/resume`, { method: "POST" });
}

export function cancelApplication(appId: string) {
  return request(`${API_BASE}/applications/${appId}/cancel`, { method: "POST" });
}

export function deleteApplication(appId: string) {
  return request(`${API_BASE}/applications/${appId}`, { method: "DELETE" });
}

export function getRecentHistory(limit = 10) {
  return request(`${API_BASE}/applications/history/recent?limit=${limit}`);
}

export async function createJob(payload: {
  source?: string;
  title: string;
  company: string;
  url?: string;
  location?: string;
  description?: string;
  requirements?: string;
}) {
  const res = await fetch(`${API_BASE}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const body = await res.text();
  if (!res.ok) {
    try {
      const parsed = JSON.parse(body);
      if (parsed?.error?.message) {
        throw new Error(parsed.error.message);
      }
    } catch {
      // fallback
    }
    throw new Error(body || `Request failed: ${res.status}`);
  }
  const job = JSON.parse(body);
  const deduped = res.headers.get("X-AutoApply-Deduped") === "true";
  return { job, deduped };
}

export function discoverJobs(payload: {
  remote_only?: boolean;
  keywords?: string[];
  limit?: number;
  sources?: {
    source_type: "greenhouse" | "lever";
    board?: string;
    site?: string;
    region?: string;
    job_url?: string;
  }[];
}) {
  return request(`${API_BASE}/jobs/discover`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function deleteJob(jobId: string) {
  return request(`${API_BASE}/jobs/${jobId}`, { method: "DELETE" });
}

export function analyzeJob(jobId: string, force = false) {
  const suffix = force ? "?force=true" : "";
  return request(`${API_BASE}/jobs/${jobId}/analyze${suffix}`, {
    method: "POST"
  }, 180000);
}

export function getJob(jobId: string) {
  return request(`${API_BASE}/jobs/${jobId}`);
}

export function getJobAnalysis(jobId: string) {
  return request(`${API_BASE}/jobs/${jobId}/analysis`);
}

export function listJobMaterials(jobId: string, opts: { limit?: number; offset?: number; type?: string } = {}) {
  const params = new URLSearchParams();
  params.set("limit", String(opts.limit ?? 50));
  params.set("offset", String(opts.offset ?? 0));
  if (opts.type) params.set("type", opts.type);
  return request(`${API_BASE}/jobs/${jobId}/materials?${params.toString()}`);
}

export function getMaterial(materialId: string) {
  return request(`${API_BASE}/materials/${materialId}`);
}

export function deleteMaterial(materialId: string) {
  return request(`${API_BASE}/materials/${materialId}`, { method: "DELETE" });
}

export function listApplicationArtifacts(
  appId: string,
  opts: { limit?: number; offset?: number; type?: string } = {}
) {
  const params = new URLSearchParams();
  params.set("limit", String(opts.limit ?? 50));
  params.set("offset", String(opts.offset ?? 0));
  if (opts.type) params.set("type", opts.type);
  return request(`${API_BASE}/applications/${appId}/artifacts?${params.toString()}`);
}

export function getArtifactFileUrl(artifactId: string) {
  return `${API_BASE}/artifacts/${artifactId}/file`;
}

export function getMaterialFileUrl(materialId: string) {
  return `${API_BASE}/materials/${materialId}/file`;
}

export function generateMaterials(jobId: string, payload: {
  resume_version_id?: string;
  workspace_resume_id?: string;
  include_cover_letter: boolean;
}) {
  return request(`${API_BASE}/jobs/${jobId}/generate-materials`, {
    method: "POST",
    body: JSON.stringify(payload)
  }, 180000);
}

export function tailorResume(jobId: string, payload: { resume_version_id?: string; workspace_resume_id?: string }) {
  return request(`${API_BASE}/jobs/${jobId}/tailor-resume`, {
    method: "POST",
    body: JSON.stringify(payload)
  }, 180000);
}

export function listSelectors({
  limit = 50,
  offset = 0,
  platform
}: {
  limit?: number;
  offset?: number;
  platform?: string;
} = {}) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (platform) params.set("platform", platform);
  return request(`${API_BASE}/selectors?${params.toString()}`);
}

export function updateProfileAnswers(payload: {
  platform?: string;
  answers: Record<string, string>;
}) {
  return request(`${API_BASE}/profile/answers`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function getProfileAnswers(platform?: string) {
  const suffix = platform ? `?platform=${encodeURIComponent(platform)}` : "";
  return request(`${API_BASE}/profile/answers${suffix}`);
}

export function createSelector(payload: {
  platform: string;
  name: string;
  selectors: string[];
}) {
  return request(`${API_BASE}/selectors`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateSelector(
  selectorId: string,
  payload: { name?: string; selectors?: string[] }
) {
  return request(`${API_BASE}/selectors/${selectorId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function inspectGreenhouse(payload: {
  job_url?: string;
  board_token?: string;
  job_id?: number;
  include_questions?: boolean;
  include_pay_transparency?: boolean;
}) {
  return request(`${API_BASE}/automation/greenhouse/inspect`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function inspectLever(payload: {
  job_url?: string;
  site?: string;
  posting_id?: string;
  region?: string;
  force?: boolean;
  include_apply_fields?: boolean;
  include_selector_drafts?: boolean;
}) {
  return request(`${API_BASE}/automation/lever/inspect`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
