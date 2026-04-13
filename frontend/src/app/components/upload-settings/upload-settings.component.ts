import { Component, computed, effect, input, model } from "@angular/core";
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

  /** Whether password section is expanded. */
  passwordsExpanded = false;

  /** Whether email section is expanded. */
  emailsExpanded = false;

  /** Track password visibility per entry. */
  passwordVisibility: boolean[] = [];

  constructor() {
    effect(() => {
      const options = this.expiryOptions();
      const current = this.expiryHours();
      if (options.length > 0 && !options.some((o) => o.value === current)) {
        this.expiryHours.set(options[options.length - 1].value);
      }
    });
    effect(() => {
      if (!this.canDisablePublic()) {
        this.isPublic.set(true);
      }
    });
  }

  /** Available expiry duration options, based on tier. */
  expiryOptions = computed<ExpiryOption[]>(() => {
    const t = this.tier();
    if (t === "premium") {
      return [
        { label: "1 hour", value: 1 },
        { label: "1 day", value: 24 },
        { label: "3 days", value: 72 },
        { label: "7 days", value: 168 },
        { label: "14 days", value: 336 },
        { label: "30 days", value: 720 },
      ];
    }
    if (t === "free") {
      return [
        { label: "1 hour", value: 1 },
        { label: "1 day", value: 24 },
        { label: "3 days", value: 72 },
        { label: "7 days", value: 168 },
      ];
    }
    // Temporary
    return [
      { label: "1 day", value: 24 },
      { label: "3 days", value: 72 },
    ];
  });

  /** Max download limit for custom input, based on tier. */
  maxDownloadsLimit = computed(() => {
    const t = this.tier();
    if (t === "premium") {
      return 1000;
    }
    if (t === "free") {
      return 10;
    }
    return 1;
  });

  /** Whether to show custom download input (free/premium) vs select (temporary). */
  useCustomDownloads = computed(() => {
    const t = this.tier();
    return t === "free" || t === "premium";
  });

  /** Available max download options for the select (temporary tier). */
  maxDownloadsOptions = computed<{ value: number; label: string }[]>(() => {
    return [
      { label: "Unlimited", value: 0 },
      { label: "1", value: 1 },
    ];
  });

  /** Whether user can add more passwords. */
  canAddPassword = computed(() => {
    const limit = this.maxPasswordsPerUpload();
    return limit === 0 || this.passwords().length < limit;
  });

  /** Whether user can use email invites (not temp). */
  canUseEmails = computed(() => {
    return this.tier() !== "temporary";
  });

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
  canDisablePublic = computed(() => {
    return this.passwordCount() > 0 || this.emailCount() > 0;
  });

  onMaxDownloadsChange(value: number | null): void {
    if (value === null || value <= 0) {
      this.maxDownloads.set(0);
      return;
    }
    const limit = this.maxDownloadsLimit();
    this.maxDownloads.set(Math.min(value, limit));
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
    if ((list.length === 0 || list[list.length - 1].password !== "") && this.canAddPassword()) {
      this.passwords.update((l) => [...l, { label: "", password: "" }]);
      this.passwordVisibility.push(false);
    }
  }

  private ensureTrailingEmailEntry(): void {
    const list = this.emails();
    if ((list.length === 0 || list[list.length - 1] !== "") && this.canAddEmail()) {
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
