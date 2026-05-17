import { ScanStatus } from '../api/model';
import type { ScanStatus as ScanStatusValue } from '../api/model';

interface ScanStatusCarrier {
  scan_status?: ScanStatusValue | null;
}

export function aggregateScanStatus(files: ScanStatusCarrier[]): ScanStatusValue | null {
  if (files.length === 0) {
    return null;
  }

  const statuses = new Set(files.map((file) => file.scan_status).filter(Boolean));
  for (const candidate of [
    ScanStatus.infected,
    ScanStatus.failed,
    ScanStatus.scanning,
    ScanStatus.queued,
  ]) {
    if (statuses.has(candidate)) {
      return candidate;
    }
  }

  return ScanStatus.clean;
}

export function isPendingScanStatus(status: ScanStatusValue | null | undefined): boolean {
  return status === ScanStatus.queued || status === ScanStatus.scanning;
}

export function isBlockedScanStatus(status: ScanStatusValue | null | undefined): boolean {
  return status === ScanStatus.infected || status === ScanStatus.failed;
}

export function getScanStatusLabel(status: ScanStatusValue | null | undefined): string {
  if (status === ScanStatus.clean) {
    return 'Scan complete';
  }

  if (status === ScanStatus.failed) {
    return 'Scan failed';
  }

  if (status === ScanStatus.infected) {
    return 'Malware detected';
  }

  if (status === ScanStatus.queued) {
    return 'Queued for scan';
  }

  if (status === ScanStatus.scanning) {
    return 'Scanning in progress';
  }

  return 'Awaiting status';
}

export function getScanStatusDescription(
  status: ScanStatusValue | null | undefined,
  subject: 'file' | 'transfer',
): string {
  if (status === ScanStatus.clean) {
    return `This ${subject} passed malware scanning and is ready to download.`;
  }

  if (status === ScanStatus.failed) {
    return `Malware scanning could not be completed for this ${subject}. Try again later.`;
  }

  if (status === ScanStatus.infected) {
    return `This ${subject} was blocked because malware was detected.`;
  }

  if (status === ScanStatus.queued) {
    return `This ${subject} is queued for malware scanning.`;
  }

  if (status === ScanStatus.scanning) {
    return `This ${subject} is being scanned for malware right now.`;
  }

  return `Malware scan status for this ${subject} is not available yet.`;
}

export function getScanStatusTone(
  status: ScanStatusValue | null | undefined,
): 'danger' | 'neutral' | 'pending' | 'success' {
  if (status === ScanStatus.clean) {
    return 'success';
  }

  if (status === ScanStatus.failed || status === ScanStatus.infected) {
    return 'danger';
  }

  if (status === ScanStatus.queued || status === ScanStatus.scanning) {
    return 'pending';
  }

  return 'neutral';
}
