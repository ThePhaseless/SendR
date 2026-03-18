import { Routes } from "@angular/router";
import { authGuard } from "./guards/auth.guard";
import { adminGuard } from "./guards/admin.guard";

export const routes: Routes = [
  { path: "", loadComponent: () => import("./pages/home/home.component").then((m) => m.HomeComponent) },
  { path: "download/group/:group", loadComponent: () => import("./pages/download/download.component").then((m) => m.DownloadComponent) },
  { path: "download/:token", loadComponent: () => import("./pages/download/download.component").then((m) => m.DownloadComponent) },
  { path: "auth", loadComponent: () => import("./pages/auth/auth.component").then((m) => m.AuthComponent) },
  {
    path: "dashboard",
    loadComponent: () => import("./pages/dashboard/dashboard.component").then((m) => m.DashboardComponent),
    canActivate: [authGuard],
  },
  {
    path: "admin",
    loadComponent: () => import("./pages/admin/admin.component").then((m) => m.AdminComponent),
    canActivate: [adminGuard],
  },
];
