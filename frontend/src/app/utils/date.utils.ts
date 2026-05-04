const ISO_WITHOUT_TIMEZONE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/;

export function normalizeApiDateString(value: string): string {
  return ISO_WITHOUT_TIMEZONE.test(value) ? `${value}Z` : value;
}

export function parseApiDate(value: string): Date {
  return new Date(normalizeApiDateString(value));
}

export function getApiDateTime(value: string): number {
  return parseApiDate(value).getTime();
}
