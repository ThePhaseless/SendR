/** Map MIME type prefixes to emojis */
const MIME_PREFIX_EMOJI: Record<string, string> = {
  image: "🖼️",
  video: "🎬",
  audio: "🎵",
  text: "📝",
  font: "🔤",
  application: "📦",
};

/** Map file extensions to emojis (overrides MIME prefix) */
const EXT_EMOJI: Record<string, string> = {
  pdf: "📕",
  doc: "📘",
  docx: "📘",
  xls: "📊",
  xlsx: "📊",
  ppt: "📙",
  pptx: "📙",
  zip: "🗜️",
  rar: "🗜️",
  "7z": "🗜️",
  tar: "🗜️",
  gz: "🗜️",
  bz2: "🗜️",
  xz: "🗜️",
  json: "📋",
  xml: "📋",
  csv: "📊",
  html: "🌐",
  css: "🎨",
  js: "⚙️",
  ts: "⚙️",
  py: "🐍",
  java: "☕",
  c: "⚙️",
  cpp: "⚙️",
  rs: "🦀",
  go: "🐹",
  rb: "💎",
  php: "🐘",
  sh: "🖥️",
  bat: "🖥️",
  exe: "⚙️",
  dmg: "💿",
  iso: "💿",
  svg: "🖼️",
  md: "📝",
  txt: "📝",
  log: "📝",
  yml: "📋",
  yaml: "📋",
  toml: "📋",
  ini: "📋",
  env: "🔒",
  key: "🔑",
  pem: "🔑",
  sql: "🗄️",
  db: "🗄️",
  sqlite: "🗄️",
};

/** Return an emoji for a given MIME type string */
export function mimeToEmoji(mime: string): string {
  const ext = mime.split("/").pop()?.toLowerCase() ?? "";
  if (EXT_EMOJI[ext]) return EXT_EMOJI[ext];
  const prefix = mime.split("/")[0];
  return MIME_PREFIX_EMOJI[prefix] ?? "📄";
}

/** Return an emoji for a filename based on its extension */
export function filenameToEmoji(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (EXT_EMOJI[ext]) return EXT_EMOJI[ext];
  return "📄";
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return bytes + " B";
  }
  if (bytes < 1024 * 1024) {
    return (bytes / 1024).toFixed(1) + " KB";
  }
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

export function extractDownloadToken(downloadUrl: string): string {
  const parts = downloadUrl.split("/");
  return parts.at(-1) ?? parts.at(-2) ?? "";
}

export function isExpired(expiresAt: string): boolean {
  return new Date(expiresAt) < new Date();
}

export { resolveAppUrl } from "./url.utils";
