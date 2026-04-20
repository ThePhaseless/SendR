import { Component, computed, effect, input, model, output } from "@angular/core";
import { FormsModule } from "@angular/forms";

export interface ExpiryOption {
  value: number;
  label: string;
}

export interface PasswordEntry {
  label: string;
  password: string;
}

@Component({
  imports: [FormsModule],
  selector: "app-upload-settings",
  styleUrl: "./upload-settings.component.scss",
  templateUrl: "./upload-settings.component.html",
})
export class UploadSettingsComponent {
  /** User tier: 'temporary' | 'free' | 'premium'. */
  tier = input("temporary");

  /** Selected expiry duration in hours. */
  expiryHours = model(168);

  /** Selected max downloads (0 = unlimited). */
  maxDownloads = model(0);

  /** Whether the upload is publicly accessible. */
  isPublic = model(true);

  /** Password entries for the upload. */
  passwords = model<PasswordEntry[]>([]);

  /** Email recipients for the upload. */
  emails = model<string[]>([]);

  /** Whether email recipients can see download stats. */
  showEmailStats = model(false);

  /** Whether download counts are tracked separately for public vs restricted. */
  separateDownloadCounts = model(false);

  /** Transfer title. */
  title = model("");

  /** Transfer description. */
  description = model("");

  /** Whether to show the heading. */
  showHeading = input(true);

  /** Whether to show the access control section. */
  showAccessControl = input(true);

  /** Max passwords per upload for current tier. */
  maxPasswordsPerUpload = input(0);

  /** Max emails per upload for current tier. */
  maxEmailsPerUpload = input(0);

  /** Discrete expiry hour options from backend (temporary tier). */
  expiryOptionsHours = input<number[] | null>(null);

  /** Min/max expiry hours from backend (free/premium). */
  minExpiryHours = input<number | null>(null);
  maxExpiryHours = input<number | null>(null);

  /** Max downloads limit from backend (free/premium). 0 = unlimited. */
  backendMaxDownloadsLimit = input<number | null>(null);

  /** Discrete max download options from backend (temporary tier). */
  backendMaxDownloadsOptions = input<number[] | null>(null);

  /** Whether the user can use separate download counts (free+ only). */
  canUseSeparateDownloadCounts = input(false);

  /** Whether the user can use email stats (free+ only). */
  canUseEmailStats = input(false);

  /** Whether password section is expanded. */
  passwordsExpanded = false;

  /** Whether email section is expanded. */
  emailsExpanded = false;

  /** Track password visibility per entry. */
  passwordVisibility: boolean[] = [];

  /** Emits whether the settings have a validation error. */
  hasError = output<boolean>();

  constructor() {
    effect(() => {
      const options = this.expiryOptions();
      const current = this.expiryHours();
      if (options.length > 0 && !options.some((o) => o.value === current)) {
        this.expiryHours.set(options.at(-1)!.value);
      }
    });
    // Emit validation error state
    effect(() => {
      this.hasError.emit(this.maxDownloadsExceedsLimit());
    });
    // Reset isPublic to true when no passwords remain (hide-details toggle only makes sense with passwords)
    effect(() => {
      if (this.passwordCount() === 0 && !this.isPublic()) {
        this.isPublic.set(true);
      }
    });
  }

  private static readonly KNOWN_EXPIRY_LABELS: Record<number, string> = {
    1: "1 hour",
    24: "1 day",
    72: "3 days",
    168: "7 days",
    336: "14 days",
    720: "30 days",
  };

  /** Available expiry duration options, driven by backend data. */
  expiryOptions = computed<ExpiryOption[]>(() => {
    const discrete = this.expiryOptionsHours();
    if (discrete) {
      // Temporary tier: use discrete options from backend
      return discrete.map((h) => ({
        label: UploadSettingsComponent.KNOWN_EXPIRY_LABELS[h] ?? `${h}h`,
        value: h,
      }));
    }
    // Free/premium: generate options within min–max range
    const min = this.minExpiryHours() ?? 1;
    const max = this.maxExpiryHours() ?? 168;
    const all = [1, 24, 72, 168, 336, 720];
    return all
      .filter((h) => h >= min && h <= max)
      .map((h) => ({
        label: UploadSettingsComponent.KNOWN_EXPIRY_LABELS[h] ?? `${h}h`,
        value: h,
      }));
  });

  /** Max download limit from backend. */
  maxDownloadsLimit = computed(() => {
    return this.backendMaxDownloadsLimit() ?? 1;
  });

  /** Whether to show custom download input (free/premium) vs select (temporary). */
  useCustomDownloads = computed(() => {
    return this.backendMaxDownloadsLimit() != null;
  });

  /** Available max download options for the select (temporary tier). */
  maxDownloadsOptions = computed<{ value: number; label: string }[]>(() => {
    const opts = this.backendMaxDownloadsOptions();
    if (opts) {
      return opts.map((v) => ({ label: v === 0 ? "Unlimited" : String(v), value: v }));
    }
    return [{ label: "Unlimited", value: 0 }, { label: "1", value: 1 }];
  });

  /** Whether user can add more passwords. */
  canAddPassword = computed(() => {
    const limit = this.maxPasswordsPerUpload();
    return limit === 0 || this.passwords().length < limit;
  });

  /** Whether user can use email invites (not temp). */
  canUseEmails = computed(() => this.tier() !== "temporary");

  /** Whether user can add more emails. */
  canAddEmail = computed(() => {
    const limit = this.maxEmailsPerUpload();
    return limit === 0 || this.emails().length < limit;
  });

  /** Count of non-empty password entries (for badge). */
  passwordCount = computed(() => this.passwords().filter((p) => p.password).length);

  /** Count of non-empty email entries (for badge). */
  emailCount = computed(() => this.emails().filter((e) => e.trim()).length);

  /** Whether the user can disable public link (needs at least one password or email). */
  canDisablePublic = computed(() => this.passwordCount() > 0 || this.emailCount() > 0);

  /** Whether max downloads exceeds the tier limit. */
  maxDownloadsExceedsLimit = computed(() => {
    const val = this.maxDownloads();
    if (val <= 0) {
      return false;
    }
    return val > this.maxDownloadsLimit();
  });

  onMaxDownloadsChange(value: number | null): void {
    if (value === null || value <= 0) {
      this.maxDownloads.set(0);
      return;
    }
    this.maxDownloads.set(value);
  }

  togglePasswordsExpanded(): void {
    this.passwordsExpanded = !this.passwordsExpanded;
    if (this.passwordsExpanded) {
      this.ensureTrailingPasswordEntry();
    }
  }

  toggleEmailsExpanded(): void {
    this.emailsExpanded = !this.emailsExpanded;
    if (this.emailsExpanded) {
      this.ensureTrailingEmailEntry();
    }
  }

  private ensureTrailingPasswordEntry(): void {
    const list = this.passwords();
    if ((list.length === 0 || list.at(-1)!.password !== "") && this.canAddPassword()) {
      this.passwords.update((l) => [...l, { label: "", password: "" }]);
      this.passwordVisibility.push(false);
    }
  }

  private ensureTrailingEmailEntry(): void {
    const list = this.emails();
    if ((list.length === 0 || list.at(-1) !== "") && this.canAddEmail()) {
      this.emails.update((l) => [...l, ""]);
    }
  }

  removePassword(index: number): void {
    this.passwords.update((list) => list.filter((_, i) => i !== index));
    this.passwordVisibility.splice(index, 1);
    this.ensureTrailingPasswordEntry();
  }

  updatePasswordLabel(index: number, label: string): void {
    this.passwords.update((list) =>
      list.map((entry, i) => (i === index ? { ...entry, label } : entry)),
    );
  }

  updatePasswordValue(index: number, password: string): void {
    const isLast = index === this.passwords().length - 1;
    this.passwords.update((list) =>
      list.map((entry, i) => (i === index ? { ...entry, password } : entry)),
    );
    if (isLast && password && this.canAddPassword()) {
      this.passwords.update((l) => [...l, { label: "", password: "" }]);
      this.passwordVisibility.push(false);
    }
  }

  togglePasswordVisibility(index: number): void {
    this.passwordVisibility[index] = !this.passwordVisibility[index];
  }

  removeEmail(index: number): void {
    this.emails.update((list) => list.filter((_, i) => i !== index));
    this.ensureTrailingEmailEntry();
  }

  updateEmail(index: number, email: string): void {
    const isLast = index === this.emails().length - 1;
    this.emails.update((list) => list.map((e, i) => (i === index ? email : e)));
    if (isLast && email.trim() && this.canAddEmail()) {
      this.emails.update((l) => [...l, ""]);
    }
  }
}
