import { Component, computed, input, model } from "@angular/core";
import { FormsModule } from "@angular/forms";

export interface ExpiryOption {
  value: number;
  label: string;
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

  /** Upload password (empty = no password). */
  password = model("");

  /** Whether to show the heading. */
  showHeading = input(true);

  /** Whether to show password field. */
  showPassword = input(true);

  /** Whether password is currently being shown in the input. */
  passwordVisible = false;

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

  onMaxDownloadsChange(value: number | null): void {
    if (value === null || value <= 0) {
      this.maxDownloads.set(0);
      return;
    }
    const limit = this.maxDownloadsLimit();
    this.maxDownloads.set(Math.min(value, limit));
  }
}
