type DebugRow = { description: string; sourceRow: number };

const canonicalHeader = "transaction_id,posted_date,account_id,currency,amount_minor,description,transaction_type";

export async function parserDebugFor(file: File): Promise<DebugRow[]> {
  if (!file.name.toLowerCase().endsWith(".csv")) return [];
  const lines = (await textFrom(file)).replace(/\r/g, "").split("\n");
  if (lines[0] !== canonicalHeader) return [];
  return lines.slice(1).flatMap((line, index) => {
    const fields = line.split(",");
    return fields.length === 7 && /^SYN-\d{5}$/.test(fields[0])
      ? [{ description: fields[5], sourceRow: index + 2 }]
      : [];
  });
}

function textFrom(file: File): Promise<string> {
  if (typeof file.text === "function") return file.text();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

export function ParserDebug({ rows }: Readonly<{ rows: DebugRow[] }>) {
  return (
    <section className="parser-debug" aria-labelledby="parser-debug-title">
      <h2 id="parser-debug-title">Preview before import</h2>
      {rows.length > 0 ? <ul>{rows.map((row) => <li key={row.sourceRow}>{row.description} <span>Source row {row.sourceRow}</span></li>)}</ul> : <p>No synthetic rows were detected. The import will check this file safely.</p>}
      <p>Preview only. Import validates this file again and never corrects rows automatically.</p>
    </section>
  );
}
