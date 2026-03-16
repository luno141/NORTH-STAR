export function parseBackendTimestamp(value: string): Date {
  if (!value) return new Date(NaN);

  const hasZone = /(?:Z|[+-]\d{2}:\d{2})$/.test(value);
  const normalized = hasZone ? value : `${value}Z`;
  return new Date(normalized);
}

export function formatBackendTimestamp(value: string): string {
  const date = parseBackendTimestamp(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    fractionalSecondDigits: 3,
    hour12: true,
    timeZoneName: "short"
  }).format(date);
}
