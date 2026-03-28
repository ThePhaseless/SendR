import type { Routes } from "@angular/router";
import { adminGuard } from "./guards/admin.guard";
import { authGuard } from "./guards/auth.guard";

export const routes: Routes = [
  {
    loadComponent: () => import("./pages/home/home.component").then((m) => m.HomeComponent),
    path: "",
  },
  {
    loadComponent: () =>
      import("./pages/download/download.component").then((m) => m.DownloadComponent),
    path: "download/group/:group",
  },
  {
    loadComponent: () =>
      import("./pages/download/download.component").then((m) => m.DownloadComponent),
    path: "download/:token",
  },
  {
    loadComponent: () => import("./pages/auth/auth.component").then((m) => m.AuthComponent),
    path: "auth",
  },
  {
    canActivate: [authGuard],
    loadComponent: () =>
      import("./pages/dashboard/dashboard.component").then((m) => m.DashboardComponent),
    path: "dashboard",
  },
  {
    canActivate: [authGuard],
    loadComponent: () =>
      import("./pages/premium/premium.component").then((m) => m.PremiumComponent),
    path: "premium",
  },
  {
    canActivate: [adminGuard],
    loadComponent: () => import("./pages/admin/admin.component").then((m) => m.AdminComponent),
    path: "admin",
  },
];
