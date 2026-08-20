export type ImportResult = {
  document_id: string;
  run_id: string;
  transaction_count: number;
  was_already_imported: boolean;
  parser_id: string;
  parser_version: string;
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
export type WorkspaceContext = {
  firstTransactionDate: string | null;
  lastTransactionDate: string | null;
  latestMonthStart: string | null;
  latestMonthEnd: string | null;
  accounts: { account: string; currencies: string[] }[];
};

export type Transaction = {
  transaction_id: string;
  transaction_date: string;
  account: string | null;
  description: string;
  currency: string;
  amount_minor: number;
  direction: Direction;
  merchant_id?: string | null;
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
export type SearchResult = Page<Transaction> & { query: string; lens: CurrencyFlow[] };
export type Counterparty = { counterparty_id: string; label: string };
export type Evidence = Record<string, string | number>;
export type MerchantEvidence = { transaction_id: string; merchant_id: string | null; merchant_name: string | null; status: string; confidence: number; method: string; evidence: Evidence };
export type Category = { category_id: string; label: string; lens: CurrencyFlow[] };
export type PeoplePlace = { key: string; label: string; kind: "person" | "place" | "unresolved"; status: "confirmed" | "unresolved"; transactionCount: number; lastActivityDate: string; flows: CurrencyFlow[]; recentTransactionIds: string[] };
export type RecurringCandidate = { candidate_id: string; label: string; cadence: string; status: string; confidence: number; evidence: Evidence; transaction_ids: string[]; expected_next_start: string; expected_next_end: string; currency: string; amount_min_minor: number; amount_max_minor: number; observation_count: number };
export type ReviewCandidate = { candidate_id: string; kind: "duplicate" | "unusual_spend"; status: string; confidence: number; evidence: Evidence; transaction_ids: string[]; currency: string; amount_minor: number; observation_count: number; date_distance_days: number | null };
export type PeriodContribution = { label: string; amount_minor: number; before_transaction_ids: string[]; after_transaction_ids: string[] };
export type PeriodExplanation = { before_net_amount_minor: number; after_net_amount_minor: number; difference_net_amount_minor: number; contribution_total_minor: number; remainder_minor: number; text: string; contributions: PeriodContribution[]; before_transaction_ids: string[]; after_transaction_ids: string[] };

export class ApiClientError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

export function localErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiClientError ? `${fallback} ${error.message}` : fallback;
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

  async getWorkspaceContext(): Promise<WorkspaceContext> {
    return this.request<WorkspaceContext>("/workspace-context");
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

  async listMerchants(scope: TransactionScope = {}): Promise<Page<MerchantEvidence>> { return this.request<Page<MerchantEvidence>>(`/merchants${query(scope)}`); }
  async listPeoplePlaces(scope: TransactionScope = {}): Promise<Page<PeoplePlace>> { return this.request<Page<PeoplePlace>>(`/people-places${query(scope)}`); }
  async listCategories(scope: TransactionScope = {}): Promise<Page<Category>> { return this.request<Page<Category>>(`/categories${query(scope)}`); }
  async listRecurring(scope: TransactionScope = {}): Promise<Page<RecurringCandidate>> { return this.request<Page<RecurringCandidate>>(`/recurring${query(scope)}`); }
  async listReview(scope: TransactionScope = {}): Promise<Page<ReviewCandidate>> { return this.request<Page<ReviewCandidate>>(`/review${query(scope)}`); }
  async correctMerchant(merchantId: string, descriptor: string): Promise<{ status: "saved" }> { return this.request<{ status: "saved" }>(`/merchants/${merchantId}`, json("PATCH", { descriptor })); }
  async getComparison(scope: TransactionScope): Promise<PeriodExplanation> { return this.request<PeriodExplanation>(`/comparisons${query(scope)}`); }
  transactionsExportUrl(scope: TransactionScope = {}): string { return `${this.baseUrl}/exports/transactions.csv${query(scope)}`; }

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
