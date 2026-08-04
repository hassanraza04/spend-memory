import type { ReactNode } from "react";

export function RecordChart({ title, values }: Readonly<{ title: string; values: readonly { label: string; value: ReactNode }[] }>) {
  return <figure className="record-chart" aria-label={title}>
    <figcaption>{title}</figcaption>
    <table><caption className="visually-hidden">{title}</caption><thead><tr><th scope="col">Item</th><th scope="col">Value</th></tr></thead><tbody>{values.map((value) => <tr key={value.label}><th scope="row">{value.label}</th><td>{value.value}</td></tr>)}</tbody></table>
    <p className="chart-alternative">Text chart: each row keeps the server-provided value separate. Amounts are not combined in your browser.</p>
  </figure>;
}

export function EvidenceList({ values }: Readonly<{ values: Record<string, string | number> }>) {
  return <dl className="candidate-evidence">{Object.entries(values).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{`${key}: ${value}`}</dd></div>)}</dl>;
}
