export type WorkspaceView = "this-month" | "all-activity" | "people-places" | "patterns" | "compare" | "data";

export type WorkspaceState = {
  after?: string;
  before?: string;
  account?: string;
  currency?: string;
  query?: string;
  merchant?: string;
  category?: string;
  counterparty?: string;
  status?: string;
  state?: string;
  direction?: string;
  amountMinMinor?: string;
  amountMaxMinor?: string;
  sort?: string;
  order?: string;
  limit?: string;
  offset?: string;
  selected?: string;
};

const stateKeys = [
  "after",
  "before",
  "account",
  "currency",
  "q",
  "merchant",
  "category",
  "counterparty",
  "status",
  "state",
  "direction",
  "amount_min_minor",
  "amount_max_minor",
  "sort",
  "order",
  "limit",
  "offset",
  "selected",
] as const;

const fieldForKey = {
  after: "after",
  before: "before",
  account: "account",
  currency: "currency",
  q: "query",
  merchant: "merchant",
  category: "category",
  counterparty: "counterparty",
  status: "status",
  state: "state",
  direction: "direction",
  amount_min_minor: "amountMinMinor",
  amount_max_minor: "amountMaxMinor",
  sort: "sort",
  order: "order",
  limit: "limit",
  offset: "offset",
  selected: "selected",
} as const;

const views: readonly WorkspaceView[] = ["this-month", "all-activity", "people-places", "patterns", "compare", "data"];

export function workspaceStateFrom(params: URLSearchParams): WorkspaceState {
  return stateKeys.reduce<WorkspaceState>((state, key) => {
    const value = params.get(key);
    if (value) state[fieldForKey[key]] = value;
    return state;
  }, {});
}

export function toWorkspaceHref(state: WorkspaceState, view: WorkspaceView): string {
  const params = new URLSearchParams({ view });
  for (const key of stateKeys) {
    const field = fieldForKey[key];
    const value = state[field];
    if (value) params.set(key, value);
  }
  return `?${params.toString()}`;
}

export function mergeWorkspaceState(state: WorkspaceState, patch: Partial<WorkspaceState>): WorkspaceState {
  const next = { ...state, ...patch };
  for (const key of Object.keys(next) as (keyof WorkspaceState)[]) {
    if (!next[key]) delete next[key];
  }
  return next;
}

export function withDefaultMonthRange(state: WorkspaceState, today = new Date()): WorkspaceState {
  if (state.after || state.before) return state;
  const date = (year: number, month: number, day: number) => `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  const year = today.getFullYear();
  const month = today.getMonth();
  return { ...state, after: date(year, month, 1), before: date(year, month + 1, 1) };
}

export function workspaceViewFrom(params: URLSearchParams): WorkspaceView {
  const view = params.get("view");
  return views.includes(view as WorkspaceView) ? (view as WorkspaceView) : "this-month";
}
