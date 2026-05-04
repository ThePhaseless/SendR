import { Injectable, signal } from '@angular/core';

export type UiNotificationTone = 'error' | 'info' | 'success' | 'warning';

export interface UiNotificationOptions {
  title: string;
  message?: string;
  tone?: UiNotificationTone;
  durationMs?: number;
  sticky?: boolean;
  dedupeKey?: string;
}

export interface UiNotification extends Required<Omit<UiNotificationOptions, 'dedupeKey'>> {
  id: number;
  dedupeKey?: string;
}

@Injectable({
  providedIn: 'root',
})
export class UiNotificationService {
  readonly notifications = signal<UiNotification[]>([]);

  private nextId = 1;
  private readonly timers = new Map<number, ReturnType<typeof setTimeout>>();

  show(options: UiNotificationOptions): number {
    const tone = options.tone ?? 'info';
    const sticky = options.sticky ?? false;
    const durationMs = sticky ? 0 : (options.durationMs ?? this.defaultDuration(tone));
    const existing = options.dedupeKey
      ? this.notifications().find((notification) => notification.dedupeKey === options.dedupeKey)
      : undefined;
    const id = existing?.id ?? this.nextId++;
    const notification: UiNotification = {
      dedupeKey: options.dedupeKey,
      durationMs,
      id,
      message: options.message ?? '',
      sticky,
      title: options.title,
      tone,
    };

    this.notifications.update((current) => {
      if (existing) {
        return current.map((item) => (item.id === existing.id ? notification : item));
      }
      return [...current, notification];
    });

    this.clearTimer(id);
    if (!sticky && durationMs > 0) {
      const timer = setTimeout(() => {
        this.dismiss(id);
      }, durationMs);
      this.timers.set(id, timer);
    }

    return id;
  }

  error(
    title: string,
    message?: string,
    options: Omit<UiNotificationOptions, 'title' | 'message' | 'tone'> = {},
  ): number {
    return this.show({ ...options, message, title, tone: 'error' });
  }

  warning(
    title: string,
    message?: string,
    options: Omit<UiNotificationOptions, 'title' | 'message' | 'tone'> = {},
  ): number {
    return this.show({ ...options, message, title, tone: 'warning' });
  }

  success(
    title: string,
    message?: string,
    options: Omit<UiNotificationOptions, 'title' | 'message' | 'tone'> = {},
  ): number {
    return this.show({ ...options, message, title, tone: 'success' });
  }

  info(
    title: string,
    message?: string,
    options: Omit<UiNotificationOptions, 'title' | 'message' | 'tone'> = {},
  ): number {
    return this.show({ ...options, message, title, tone: 'info' });
  }

  dismiss(id: number): void {
    this.clearTimer(id);
    this.notifications.update((current) =>
      current.filter((notification) => notification.id !== id),
    );
  }

  private clearTimer(id: number): void {
    const timer = this.timers.get(id);
    if (timer) {
      clearTimeout(timer);
      this.timers.delete(id);
    }
  }

  private defaultDuration(tone: UiNotificationTone): number {
    switch (tone) {
      case 'error': {
        return 7000;
      }
      case 'info': {
        return 4500;
      }
      case 'success': {
        return 4500;
      }
      case 'warning': {
        return 6000;
      }
    }
  }
}
