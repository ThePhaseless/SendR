import { Injectable, signal } from '@angular/core';

export interface ConfirmDialogOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: 'danger' | 'primary';
}

export interface ConfirmDialogState {
  cancelLabel: string;
  confirmLabel: string;
  message: string;
  title: string;
  tone: 'danger' | 'primary';
}

@Injectable({
  providedIn: 'root',
})
export class ConfirmDialogService {
  readonly dialog = signal<ConfirmDialogState | null>(null);

  private confirmAction: (() => void) | null = null;

  confirm(options: ConfirmDialogOptions, onConfirm: () => void): void {
    this.confirmAction = onConfirm;

    this.dialog.set({
      cancelLabel: options.cancelLabel ?? 'Cancel',
      confirmLabel: options.confirmLabel ?? 'Continue',
      message: options.message,
      title: options.title,
      tone: options.tone ?? 'primary',
    });
  }

  resolve(result: boolean): void {
    this.dialog.set(null);
    const action = this.confirmAction;
    this.confirmAction = null;
    if (result) {
      action?.();
    }
  }
}
