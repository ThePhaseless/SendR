import { Component, inject, OnInit, signal } from "@angular/core";
import { Router, RouterLink } from "@angular/router";
import { AuthService } from "../../services/auth.service";

@Component({
  selector: "app-header",
  imports: [RouterLink],
  templateUrl: "./header.component.html",
  styleUrl: "./header.component.scss",
})
export class HeaderComponent implements OnInit {
  private readonly router = inject(Router);
  readonly auth = inject(AuthService);
  isAdmin = signal(false);

  ngOnInit(): void {
    if (this.auth.isAuthenticated()) {
      this.auth.getMe().subscribe({
        next: (me) => this.isAdmin.set(me.is_admin),
      });
    }
  }

  logout(): void {
    this.auth.logout();
    this.isAdmin.set(false);
    this.router.navigate(["/"]);
  }
}
