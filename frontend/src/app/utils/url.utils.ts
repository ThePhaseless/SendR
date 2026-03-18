export function resolveAppUrl(path: string): string {
  if (typeof document === "undefined") {
    return path;
  }

  const normalizedPath = path.replace(/^\/+/, "");
  return new URL(normalizedPath, document.baseURI).toString();
}
