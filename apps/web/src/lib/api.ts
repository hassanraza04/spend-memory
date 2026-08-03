export type ImportResult = {
  document_id: string;
  run_id: string;
  transaction_count: number;
  was_already_imported: boolean;
};

export type LocalDataResult = { status: "deleted" | "reset" };

export class ApiClientError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

export class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl = "/api/v1") {
    this.baseUrl = baseUrl;
  }

  async importStatement(file: File): Promise<ImportResult> {
    const body = new FormData();
    body.set("file", file);
    return this.request<ImportResult>("/imports", { method: "POST", body });
  }

  async resetDemo(): Promise<LocalDataResult> {
    return this.request<LocalDataResult>("/demo/reset", { method: "POST" });
  }

  async deleteLocalData(): Promise<LocalDataResult> {
    return this.request<LocalDataResult>("/local-data", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmation: "DELETE LOCAL DATA" }),
    });
  }

  private async request<T>(path: string, init?: Parameters<typeof fetch>[1]): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, init);
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { error?: { code?: string; message?: string } } | null;
      throw new ApiClientError(payload?.error?.code ?? "request_failed", payload?.error?.message ?? "The local request could not be completed.");
    }
    return response.json() as Promise<T>;
  }
}
