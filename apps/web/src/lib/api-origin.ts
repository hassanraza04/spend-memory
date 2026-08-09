const localOrigins = new Set([
  "http://127.0.0.1:8000",
  "http://localhost:8000",
  "http://[::1]:8000",
  "http://api:8000",
]);

export function localApiOrigin(value = process.env.SPEND_MEMORY_API_URL): string {
  const origin = value ?? "http://127.0.0.1:8000";
  if (!localOrigins.has(origin)) throw new Error("SPEND_MEMORY_API_URL must be a local API origin");
  return origin;
}
