import { parseApiDate } from './date.utils';

/** Map MIME type prefixes to emojis */
const MIME_PREFIX_EMOJI: Record<string, string> = {
  application: '📦',
  audio: '🎵',
  font: '🔤',
  image: '🖼️',
  text: '📝',
  video: '🎬',
};

/** Map file extensions to emojis (overrides MIME prefix) */
const EXT_EMOJI: Record<string, string> = {
  '7z': '🗜️',
  bat: '🖥️',
  bz2: '🗜️',
  c: '⚙️',
  cpp: '⚙️',
  css: '🎨',
  csv: '📊',
  db: '🗄️',
  dmg: '💿',
  doc: '📘',
  docx: '📘',
  env: '🔒',
  exe: '⚙️',
  go: '🐹',
  gz: '🗜️',
  html: '🌐',
  ini: '📋',
  iso: '💿',
  java: '☕',
  js: '⚙️',
  json: '📋',
  key: '🔑',
  log: '📝',
  md: '📝',
  pdf: '📕',
  pem: '🔑',
  php: '🐘',
  ppt: '📙',
  pptx: '📙',
  py: '🐍',
  rar: '🗜️',
  rb: '💎',
  rs: '🦀',
  sh: '🖥️',
  sql: '🗄️',
  sqlite: '🗄️',
  svg: '🖼️',
  tar: '🗜️',
  toml: '📋',
  ts: '⚙️',
  txt: '📝',
  xls: '📊',
  xlsx: '📊',
  xml: '📋',
  xz: '🗜️',
  yaml: '📋',
  yml: '📋',
  zip: '🗜️',
};

/** Return an emoji for a given MIME type string */
export function mimeToEmoji(mime: string): string {
  const ext = mime.split('/').pop()?.toLowerCase() ?? '';
  if (EXT_EMOJI[ext]) {
    return EXT_EMOJI[ext];
  }
  const [prefix] = mime.split('/');
  return MIME_PREFIX_EMOJI[prefix] ?? '📄';
}

/** Return an emoji for a filename based on its extension */
export function filenameToEmoji(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  if (EXT_EMOJI[ext]) {
    return EXT_EMOJI[ext];
  }
  return '📄';
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return bytes + ' B';
  }
  if (bytes < 1024 * 1024) {
    return (bytes / 1024).toFixed(1) + ' KB';
  }
  const mb = bytes / (1024 * 1024);
  if (mb >= 2048) {
    return Math.floor(mb / 1024) + ' GB';
  }
  return mb.toFixed(1) + ' MB';
}

export function extractDownloadToken(downloadUrl: string): string {
  const parts = downloadUrl.split('/');
  return parts.at(-1) ?? parts.at(-2) ?? '';
}

export function isExpired(expiresAt: string): boolean {
  return parseApiDate(expiresAt).getTime() < Date.now();
}

export { resolveAppUrl } from './url.utils';
