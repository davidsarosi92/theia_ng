import {
  CdkDrag,
  CdkDragDrop,
  CdkDragHandle,
  CdkDropList,
  moveItemInArray,
} from '@angular/cdk/drag-drop';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';

import { ApiService } from './api.service';
import { FavoritesService } from './favorites.service';
import { AppGroup, groupByApp } from './grouping';
import { I18nService } from './i18n.service';
import { LoadingService } from './loading.service';
import { LoginComponent } from './login.component';
import { AuthState, RegistryModel, ThemePref } from './models';
import { SettingsService } from './settings.service';
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
  imports: [
    RouterOutlet,
    RouterLink,
    LoginComponent,
    ToastHostComponent,
    CdkDropList,
    CdkDrag,
    CdkDragHandle,
  ],
  template: `
    @if (ready()) {
      @if (canAccess()) {
        <div class="shell" [class.nav-open]="sidebarOpen()">
          <header class="topbar">
            <button class="nav-toggle" (click)="toggleSidebar()" [attr.aria-label]="t('toggleMenu')">☰</button>
            <a class="topbar-title" routerLink="/">
              @if (logoUrl) { <img class="topbar-logo" [src]="logoUrl" alt="" /> }
              <span>{{ siteTitle }}</span>
            </a>
            @if (version) { <span class="topbar-version">v{{ version }}</span> }
            @if (firstName() || username()) {
              <span class="topbar-greet">
                @if (firstName()) { <span class="greet-hi">{{ t('greeting', { name: firstName()! }) }}</span> }
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
                  <option value="">{{ t('fullView') }}</option>
                  @for (v of vs.views(); track v.name) {
                    <option [value]="v.name">{{ v.name }}</option>
                  }
                </select>
              }
              @if (settings.availableLanguages().length) {
                <select
                  class="lang-select"
                  [attr.aria-label]="t('language')"
                  [value]="i18n.lang()"
                  (change)="settings.setLanguage($any($event.target).value)"
                >
                  @for (l of settings.availableLanguages(); track l.code) {
                    <option [value]="l.code">{{ l.label }}</option>
                  }
                </select>
              }
              <select
                class="theme-select"
                [attr.aria-label]="t('theme')"
                [value]="settings.theme()"
                (change)="setTheme($any($event.target).value)"
              >
                <option value="auto">{{ t('themeAuto') }}</option>
                <option value="light">{{ t('themeLight') }}</option>
                <option value="dark">{{ t('themeDark') }}</option>
              </select>
              <span class="topbar-busy" [class.active]="loading.active()" aria-hidden="true" [title]="t('working')">
                <span class="spinner"></span>
              </span>
              <button class="link-btn" (click)="logout()">{{ t('signOut') }}</button>
            </div>
          </header>
          <div class="layout">
            <aside class="sidebar" [class.collapsed]="!sidebarOpen()">
              <div class="nav-top">
                <a routerLink="/" class="nav-link" (click)="onNav()" [title]="t('home')">
                  <span class="nav-ini">⌂</span><span class="nav-lbl">{{ t('home') }}</span>
                </a>
              </div>
              <div class="nav-grouplist" cdkDropList (cdkDropListDropped)="dropGroup($event)">
                @for (g of otherGroups(); track g.appLabel) {
                  <div
                    class="nav-group"
                    cdkDrag
                    cdkDragLockAxis="y"
                    cdkDragBoundary=".sidebar"
                    cdkDragPreviewContainer="parent"
                  >
                    <a class="nav-group-title" draggable="false" [routerLink]="['/app', g.appLabel]" (click)="onNav()">
                      <span class="nav-group-name">{{ cap(g.appName) }}</span>
                      <span
                        class="nav-drag group-drag"
                        cdkDragHandle
                        (click)="$event.preventDefault(); $event.stopPropagation()"
                        [title]="t('reorder')"
                        aria-hidden="true"
                      >⠿</span>
                    </a>
                    <div class="nav-modellist" cdkDropList (cdkDropListDropped)="dropNav(g, $event)">
                      @for (m of g.models; track m.key) {
                        <a
                          cdkDrag
                          cdkDragLockAxis="y"
                          cdkDragBoundary=".sidebar"
                          cdkDragPreviewContainer="parent"
                          draggable="false"
                          [routerLink]="['/', slug(m.key)]"
                          (click)="onNav()"
                          [title]="cap(m.verbose_name_plural)"
                        >
                          <span class="nav-ini">{{ initials(m.verbose_name_plural) }}</span>
                          <span class="nav-lbl">{{ cap(m.verbose_name_plural) }}</span>
                          <span
                            class="nav-drag"
                            cdkDragHandle
                            (click)="$event.preventDefault(); $event.stopPropagation()"
                            [title]="t('reorder')"
                            aria-hidden="true"
                          >⠿</span>
                        </a>
                      }
                    </div>
                  </div>
                }
              </div>
              <!-- Theia NG Admin section, pinned to the bottom: Activity + its
                   models (Menu views). Always shows Activity, even if the user
                   can't see the MenuView model. -->
              <div class="nav-group">
                <a class="nav-group-title" [routerLink]="['/app', 'theia_ng']" (click)="onNav()">{{ adminTitle() }}</a>
                <a routerLink="/logs" (click)="onNav()" [title]="t('activity')">
                  <span class="nav-ini">≡</span><span class="nav-lbl">{{ t('activity') }}</span>
                </a>
                @if (adminGroup(); as ag) {
                  <div class="nav-modellist" cdkDropList (cdkDropListDropped)="dropNav(ag, $event)">
                    @for (m of ag.models; track m.key) {
                      <a
                        cdkDrag
                        cdkDragLockAxis="y"
                        cdkDragBoundary=".sidebar"
                        cdkDragPreviewContainer="parent"
                        draggable="false"
                        [routerLink]="['/', slug(m.key)]"
                        (click)="onNav()"
                        [title]="cap(m.verbose_name_plural)"
                      >
                        <span class="nav-ini">{{ initials(m.verbose_name_plural) }}</span>
                        <span class="nav-lbl">{{ cap(m.verbose_name_plural) }}</span>
                        <span
                          class="nav-drag"
                          cdkDragHandle
                          (click)="$event.preventDefault(); $event.stopPropagation()"
                          [title]="t('reorder')"
                          aria-hidden="true"
                        >⠿</span>
                      </a>
                    }
                  </div>
                }
              </div>
              @if (settings.hasCustomNavOrder()) {
                <button type="button" class="nav-reset" (click)="settings.resetNavOrder()">
                  ↺ {{ t('resetOrder') }}
                </button>
              }
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
  protected loading = inject(LoadingService);
  private favorites = inject(FavoritesService);
  protected settings = inject(SettingsService);
  protected i18n = inject(I18nService);
  protected t = this.i18n.t;
  siteTitle = getConfig().siteTitle;
  version = getConfig().version;
  logoUrl = getConfig().logoUrl;
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
   *  apps sorted by name and models by name within each, then re-ordered within
   *  each group by the user's saved sidebar order (A5). */
  groups = computed<AppGroup[]>(() => {
    const raw = groupByApp(this.vs.filterModels(this.models()));
    return raw.map((g) => ({ ...g, models: this.applyNavOrder(g.models) }));
  });

  /** Sort a group's models by the user's saved nav order. Known keys come first
   *  in their saved order; unknown keys keep their incoming (name-sorted) order
   *  via the stable sort. */
  private applyNavOrder(models: RegistryModel[]): RegistryModel[] {
    const order = this.settings.navOrder();
    if (!order.length) {
      return models;
    }
    const idx = new Map(order.map((k, i) => [k, i]));
    const rank = (k: string) => (idx.has(k) ? idx.get(k)! : Number.MAX_SAFE_INTEGER);
    return [...models].sort((a, b) => rank(a.key) - rank(b.key));
  }

  /** Persist a drag-reorder of a sidebar group's items. Rebuilds the full nav
   *  order across every group (in render order) so the saved list stays complete. */
  dropNav(group: AppGroup, event: CdkDragDrop<unknown>): void {
    if (event.previousIndex === event.currentIndex) {
      return;
    }
    const reordered = [...group.models];
    moveItemInArray(reordered, event.previousIndex, event.currentIndex);
    const full: string[] = [];
    for (const g of this.groups()) {
      const list = g.appLabel === group.appLabel ? reordered : g.models;
      for (const m of list) {
        full.push(m.key);
      }
    }
    this.settings.setNavOrder(full);
  }

  /** Persist a drag-reorder of the app groups (the whole block moves). */
  dropGroup(event: CdkDragDrop<unknown>): void {
    if (event.previousIndex === event.currentIndex) {
      return;
    }
    const labels = this.otherGroups().map((g) => g.appLabel);
    moveItemInArray(labels, event.previousIndex, event.currentIndex);
    this.settings.setNavAppOrder(labels);
  }

  /** Theia NG's own app group (holds Menu views) — rendered last, with Activity. */
  adminGroup = computed<AppGroup | null>(
    () => this.groups().find((g) => g.appLabel === THEIA_APP) ?? null,
  );
  /** Every other app group, ordered by the user's saved app order (A5); apps not
   *  in the saved order keep their name-sorted position (stable sort). */
  otherGroups = computed<AppGroup[]>(() => {
    const others = this.groups().filter((g) => g.appLabel !== THEIA_APP);
    const order = this.settings.navAppOrder();
    if (!order.length) {
      return others;
    }
    const idx = new Map(order.map((k, i) => [k, i]));
    const rank = (k: string) => (idx.has(k) ? idx.get(k)! : Number.MAX_SAFE_INTEGER);
    return [...others].sort((a, b) => rank(a.appLabel) - rank(b.appLabel));
  });
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

  /** Apply auth state: user, greeting, favorites scope, settings, and registry. */
  private applyAuth(state: AuthState): void {
    this.username.set(state.username);
    this.firstName.set(state.first_name ?? null);
    this.canAccess.set(state.can_access);
    this.favorites.load(state.can_access);
    this.settings.load(state.can_access);
    if (state.can_access) {
      this.loadRegistry();
    }
  }

  setTheme(theme: string): void {
    this.settings.setTheme(theme as ThemePref);
  }

  logout(): void {
    this.api.logout().subscribe(() => {
      this.canAccess.set(false);
      this.username.set(null);
      this.firstName.set(null);
      this.favorites.load(false);
      this.settings.load(false);
      this.models.set([]);
    });
  }

  private loadRegistry(): void {
    this.api.getRegistry().subscribe({
      next: (r) => {
        this.siteTitle = r.site.title || this.siteTitle;
        // Prefer the live API version (robust to a stale, cached index.html).
        this.version = r.site.version || this.version;
        // Same for the logo — a live value overrides a stale injected config.
        if (r.site.logo_url !== undefined) {
          this.logoUrl = r.site.logo_url;
        }
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
