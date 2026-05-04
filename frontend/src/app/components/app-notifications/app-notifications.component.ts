import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { UiNotificationService } from '../../services/ui-notification.service';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  selector: 'app-notifications',
  standalone: true,
  styleUrl: './app-notifications.component.scss',
  templateUrl: './app-notifications.component.html',
})
export class AppNotificationsComponent {
  readonly notifications = inject(UiNotificationService);
}
