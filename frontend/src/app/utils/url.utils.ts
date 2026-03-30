export function resolveAppUrl(path: string): string {
  if (typeof document === "undefined") {
    return path;
  }

  const normalizedPath = path.replace(/^\/+/, "");
  return new URL(normalizedPath, document.baseURI).toString();
}

export function resolveApiUrl(path: string, basePath = ""): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  if (!basePath) {
    return normalizedPath;
  }

  return new URL(normalizedPath, `${basePath.replace(/\/+$/, "")}/`).toString();
}
