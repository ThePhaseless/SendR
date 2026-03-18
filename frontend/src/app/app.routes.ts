import { Routes } from "@angular/router";
import { HomeComponent } from "./pages/home/home.component";
import { DownloadComponent } from "./pages/download/download.component";
import { AuthComponent } from "./pages/auth/auth.component";
import { DashboardComponent } from "./pages/dashboard/dashboard.component";
import { AdminComponent } from "./pages/admin/admin.component";
import { authGuard } from "./guards/auth.guard";
import { adminGuard } from "./guards/admin.guard";

export const routes: Routes = [
  { path: "", component: HomeComponent },
  { path: "download/:token", component: DownloadComponent },
  { path: "auth", component: AuthComponent },
  {
    path: "dashboard",
    component: DashboardComponent,
    canActivate: [authGuard],
  },
  {
    path: "admin",
    component: AdminComponent,
    canActivate: [adminGuard],
  },
];
