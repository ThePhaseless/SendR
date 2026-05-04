import { Injectable, signal } from '@angular/core';

export interface ConfirmDialogOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: 'danger' | 'primary';
}

export interface ConfirmDialogState {
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  tone: 'danger' | 'primary';
}

@Injectable({
  providedIn: 'root',
})
export class ConfirmDialogService {
  readonly dialog = signal<ConfirmDialogState | null>(null);

  private resolver: ((result: boolean) => void) | null = null;

  confirm(options: ConfirmDialogOptions): Promise<boolean> {
    if (this.resolver) {
      this.resolver(false);
      this.resolver = null;
    }

    this.dialog.set({
      cancelLabel: options.cancelLabel ?? 'Cancel',
      confirmLabel: options.confirmLabel ?? 'Continue',
      message: options.message,
      title: options.title,
      tone: options.tone ?? 'primary',
    });

    return new Promise<boolean>((resolve) => {
      this.resolver = resolve;
    });
  }

  resolve(result: boolean): void {
    this.dialog.set(null);
    this.resolver?.(result);
    this.resolver = null;
  }
}
