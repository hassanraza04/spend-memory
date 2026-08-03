export function formatMoney(amountMinor: number, currency: string): string {
  const formatter = new Intl.NumberFormat(undefined, { style: "currency", currency });
  const fractionDigits = formatter.resolvedOptions().maximumFractionDigits ?? 0;
  return formatter.format(amountMinor / 10 ** fractionDigits);
}
