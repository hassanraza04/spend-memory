export type ImportResult = {
  document_id: string;
  run_id: string;
  transaction_count: number;
  was_already_imported: boolean;
};

export type LocalDataResult = { status: "deleted" | "reset" };

export type Direction = "debit" | "credit";

export type CurrencyFlow = {
  currency: string;
  sent_minor: number;
  received_minor: number;
  net_minor: number;
  transaction_count: number;
};

export type TrendBucket = CurrencyFlow & { period_start: string };

export type WorkspaceLens = { lens: CurrencyFlow[]; trend: TrendBucket[] };

export type Transaction = {
  transaction_id: string;
  transaction_date: string;
  account: string | null;
  description: string;
  currency: string;
  amount_minor: number;
  direction: Direction;
  merchant: string | null;
  category: string;
  counterparty: string | null;
  state: string;
  source: {
    document: string;
    ordinal: number;
    page: number | null;
    row: number | null;
    text: string;
    extraction_confidence: number;
  };
};

export type Page<T> = { items: T[]; limit: number; offset: number; total: number };
export type TransactionScope = Record<string, string | undefined>;
export type SearchResult = { query: string; items: Transaction[]; lens: CurrencyFlow[] };
export type Counterparty = { counterparty_id: string; label: string };

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

  async listTransactions(scope: TransactionScope = {}): Promise<Page<Transaction>> {
    return this.request<Page<Transaction>>(`/transactions${query(scope)}`);
  }

  async getLens(scope: TransactionScope = {}): Promise<WorkspaceLens> {
    return this.request<WorkspaceLens>(`/lens${query(scope)}`);
  }

  async searchTransactions(scope: TransactionScope): Promise<SearchResult> {
    return this.request<SearchResult>(`/search${query(scope)}`);
  }

  async createCounterparty(label: string): Promise<Counterparty> {
    return this.request<Counterparty>("/counterparties", json("POST", { label }));
  }

  async assignCounterparty(counterpartyId: string, transactionIds: string[]): Promise<{ lens: CurrencyFlow[] }> {
    return this.request<{ lens: CurrencyFlow[] }>(`/counterparties/${counterpartyId}/transactions`, json("POST", { transaction_ids: transactionIds }));
  }

  async confirmCounterpartyAlias(counterpartyId: string, descriptor: string): Promise<{ status: "saved" }> {
    return this.request<{ status: "saved" }>(`/counterparties/${counterpartyId}`, json("PATCH", { descriptor }));
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

function query(scope: TransactionScope): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(scope)) if (value) params.set(key, value);
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}

function json(method: string, body: object): Parameters<typeof fetch>[1] {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}
