import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';

import { ApiService } from './api.service';
import { FavoritesService } from './favorites.service';
import { AppGroup, groupByApp } from './grouping';
import { LoginComponent } from './login.component';
import { AuthState, RegistryModel } from './models';
import { ToastHostComponent } from './toast-host.component';
import { getConfig } from './theia-config';
import { cap, keyToSlug } from './util';
import { ViewService } from './view.service';

/** Theia NG's own app_label — its sidebar/home section is pinned last and hosts
 *  the Activity link alongside its models (Menu views). */
const THEIA_APP = 'theia_ng';

@Component({
  selector: 'theia-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, LoginComponent, ToastHostComponent],
  template: `
    @if (ready()) {
      @if (canAccess()) {
        <div class="shell" [class.nav-open]="sidebarOpen()">
          <header class="topbar">
            <button class="nav-toggle" (click)="toggleSidebar()" aria-label="Toggle menu">☰</button>
            <a class="topbar-title" routerLink="/">{{ siteTitle }}</a>
            @if (version) { <span class="topbar-version">v{{ version }}</span> }
            @if (firstName() || username()) {
              <span class="topbar-greet">
                @if (firstName()) { <span class="greet-hi">Hi, {{ firstName() }}</span> }
                @if (username()) { <span class="topbar-email">{{ username() }}</span> }
              </span>
            }
            <div class="topbar-right">
              @if (vs.views().length) {
                <select
                  class="view-select"
                  [value]="vs.active()"
                  (change)="vs.setActive($any($event.target).value)"
                >
                  <option value="">Full</option>
                  @for (v of vs.views(); track v.name) {
                    <option [value]="v.name">{{ v.name }}</option>
                  }
                </select>
              }
              <button class="link-btn" (click)="logout()">Sign out</button>
            </div>
          </header>
          <div class="layout">
            <aside class="sidebar" [class.collapsed]="!sidebarOpen()">
              <div class="nav-top">
                <a routerLink="/" class="nav-link" (click)="onNav()" title="Home">
                  <span class="nav-ini">⌂</span><span class="nav-lbl">Home</span>
                </a>
              </div>
              @for (g of otherGroups(); track g.appLabel) {
                <div class="nav-group">
                  <a class="nav-group-title" [routerLink]="['/app', g.appLabel]" (click)="onNav()">{{ cap(g.appName) }}</a>
                  @for (m of g.models; track m.key) {
                    <a
                      [routerLink]="['/', slug(m.key)]"
                      (click)="onNav()"
                      [title]="cap(m.verbose_name_plural)"
                    >
                      <span class="nav-ini">{{ initials(m.verbose_name_plural) }}</span>
                      <span class="nav-lbl">{{ cap(m.verbose_name_plural) }}</span>
                    </a>
                  }
                </div>
              }
              <!-- Theia NG Admin section, pinned to the bottom: Activity + its
                   models (Menu views). Always shows Activity, even if the user
                   can't see the MenuView model. -->
              <div class="nav-group">
                <a class="nav-group-title" [routerLink]="['/app', 'theia_ng']" (click)="onNav()">{{ adminTitle() }}</a>
                <a routerLink="/logs" (click)="onNav()" title="Activity">
                  <span class="nav-ini">≡</span><span class="nav-lbl">Activity</span>
                </a>
                @if (adminGroup(); as ag) {
                  @for (m of ag.models; track m.key) {
                    <a
                      [routerLink]="['/', slug(m.key)]"
                      (click)="onNav()"
                      [title]="cap(m.verbose_name_plural)"
                    >
                      <span class="nav-ini">{{ initials(m.verbose_name_plural) }}</span>
                      <span class="nav-lbl">{{ cap(m.verbose_name_plural) }}</span>
                    </a>
                  }
                }
              </div>
            </aside>
            <div class="sidebar-backdrop" (click)="closeSidebar()"></div>
            <main class="content">
              <router-outlet />
            </main>
          </div>
        </div>
      } @else {
        <theia-login (loggedIn)="onLoggedIn()" />
      }
    }
    <theia-toasts />
  `,
})
export class AppComponent implements OnInit {
  private api = inject(ApiService);
  protected vs = inject(ViewService);
  private favorites = inject(FavoritesService);
  siteTitle = getConfig().siteTitle;
  version = getConfig().version;
  cap = cap;
  slug = keyToSlug;
  models = signal<RegistryModel[]>([]);
  ready = signal(false);
  canAccess = signal(false);
  username = signal<string | null>(null);
  firstName = signal<string | null>(null);
  /** Sidebar open (full). Closed = compact initials rail on desktop, hidden
   *  drawer on mobile. Starts open on wide screens, closed on narrow ones. */
  sidebarOpen = signal(this.isWide());

  private isWide(): boolean {
    return typeof window === 'undefined' || window.innerWidth > 768;
  }

  toggleSidebar(): void {
    this.sidebarOpen.update((open) => !open);
  }

  closeSidebar(): void {
    this.sidebarOpen.set(false);
  }

  /** Clicking a nav link closes the drawer on mobile (it overlays the content). */
  onNav(): void {
    if (!this.isWide()) {
      this.sidebarOpen.set(false);
    }
  }

  /** Initials of a model's words for the compact rail, e.g. "Locale base vats" → "LBV". */
  initials(name: string): string {
    return name
      .split(/\s+/)
      .filter(Boolean)
      .map((w) => w[0])
      .join('')
      .slice(0, 3)
      .toUpperCase();
  }

  /** Visible models (permitted set, narrowed by the active view) grouped by app,
   *  apps sorted by name and models by name within each. */
  groups = computed<AppGroup[]>(() => groupByApp(this.vs.filterModels(this.models())));
  /** Theia NG's own app group (holds Menu views) — rendered last, with Activity. */
  adminGroup = computed<AppGroup | null>(
    () => this.groups().find((g) => g.appLabel === THEIA_APP) ?? null,
  );
  /** Every other app group, in their normal sorted order. */
  otherGroups = computed<AppGroup[]>(() => this.groups().filter((g) => g.appLabel !== THEIA_APP));
  adminTitle = computed(() => this.adminGroup()?.appName ?? 'Theia NG Admin');

  ngOnInit(): void {
    // Seeds the CSRF cookie and tells us whether we're already signed in.
    this.api.me().subscribe({
      next: (state) => {
        this.applyAuth(state);
        this.ready.set(true);
      },
      error: () => this.ready.set(true),
    });
  }

  onLoggedIn(): void {
    this.api.me().subscribe((state) => this.applyAuth(state));
  }

  /** Apply auth state: user, greeting, favorites scope, and load the registry. */
  private applyAuth(state: AuthState): void {
    this.username.set(state.username);
    this.firstName.set(state.first_name ?? null);
    this.canAccess.set(state.can_access);
    this.favorites.load(state.can_access);
    if (state.can_access) {
      this.loadRegistry();
    }
  }

  logout(): void {
    this.api.logout().subscribe(() => {
      this.canAccess.set(false);
      this.username.set(null);
      this.firstName.set(null);
      this.favorites.load(false);
      this.models.set([]);
    });
  }

  private loadRegistry(): void {
    this.api.getRegistry().subscribe({
      next: (r) => {
        this.siteTitle = r.site.title || this.siteTitle;
        this.models.set(r.models);
        this.vs.setViews(r.views ?? []);
      },
      error: () => {
        this.models.set([]);
        this.vs.setViews([]);
      },
    });
  }
}
