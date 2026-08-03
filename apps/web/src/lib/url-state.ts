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
  state?: string;
  direction?: string;
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
  "state",
  "direction",
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
  state: "state",
  direction: "direction",
  selected: "selected",
} as const;

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
