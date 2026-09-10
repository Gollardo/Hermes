import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: 'imports',
    loadComponent: () => import('./pages/imports/imports').then((m) => m.ImportsPage),
  },
  {
    path: '',
    loadComponent: () => import('./pages/home/home').then((module) => module.HomePage),
  },
  {
    path: 'backend-status',
    loadComponent: () =>
      import('./pages/backend-status/backend-status').then((module) => module.BackendStatusPage),
  },
  {
    path: 'operations',
    loadComponent: () =>
      import('./pages/operations/operations').then((module) => module.OperationsPage),
  },
  {
    path: 'funds',
    loadComponent: () => import('./pages/funds/funds').then((module) => module.FundsPage),
  },
  {
    path: 'calendar',
    loadComponent: () =>
      import('./pages/scheduling/scheduling').then((module) => module.SchedulingPage),
  },
  {
    path: 'forecast',
    loadComponent: () => import('./pages/forecast/forecast').then((module) => module.ForecastPage),
  },
  {
    path: 'reports',
    loadComponent: () => import('./pages/reports/reports').then((module) => module.ReportsPage),
  },
  {
    path: 'accounts',
    loadComponent: () => import('./pages/accounts/accounts').then((module) => module.AccountsPage),
  },
  {
    path: 'categories',
    loadComponent: () =>
      import('./pages/categories/categories').then((module) => module.CategoriesPage),
  },
  {
    path: 'settings',
    loadComponent: () => import('./pages/settings/settings').then((module) => module.SettingsPage),
  },
  { path: '**', redirectTo: '' },
];
