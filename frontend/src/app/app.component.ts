import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';

import { ApiService } from './api.service';
import { LoginComponent } from './login.component';
import { RegistryModel } from './models';
import { getConfig } from './theia-config';
import { cap, keyToSlug } from './util';

interface AppGroup {
  appLabel: string;
  appName: string;
  models: RegistryModel[];
}

@Component({
  selector: 'theia-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, LoginComponent],
  template: `
    @if (ready()) {
      @if (canAccess()) {
        <div class="shell">
          <header class="topbar">
            <span class="topbar-title">{{ siteTitle }}</span>
            <div class="topbar-right">
              <span class="username">{{ username() }}</span>
              <button class="link-btn" (click)="logout()">Sign out</button>
            </div>
          </header>
          <div class="layout">
            <aside class="sidebar">
              <a routerLink="/" class="nav-home">Home</a>
              @for (g of groups(); track g.appLabel) {
                <div class="nav-group">
                  <div class="nav-group-title">{{ cap(g.appName) }}</div>
                  @for (m of g.models; track m.key) {
                    <a [routerLink]="['/', slug(m.key)]">{{ cap(m.verbose_name_plural) }}</a>
                  }
                </div>
              }
            </aside>
            <main class="content">
              <router-outlet />
            </main>
          </div>
        </div>
      } @else {
        <theia-login (loggedIn)="onLoggedIn()" />
      }
    }
  `,
})
export class AppComponent implements OnInit {
  private api = inject(ApiService);
  siteTitle = getConfig().siteTitle;
  cap = cap;
  slug = keyToSlug;
  models = signal<RegistryModel[]>([]);
  ready = signal(false);
  canAccess = signal(false);
  username = signal<string | null>(null);

  /** Models grouped by Django app, preserving registration order. */
  groups = computed<AppGroup[]>(() => {
    const map = new Map<string, AppGroup>();
    for (const m of this.models()) {
      let group = map.get(m.app_label);
      if (!group) {
        group = { appLabel: m.app_label, appName: m.app_verbose_name, models: [] };
        map.set(m.app_label, group);
      }
      group.models.push(m);
    }
    return [...map.values()];
  });

  ngOnInit(): void {
    // Seeds the CSRF cookie and tells us whether we're already signed in.
    this.api.me().subscribe({
      next: (state) => {
        this.username.set(state.username);
        this.canAccess.set(state.can_access);
        this.ready.set(true);
        if (state.can_access) {
          this.loadRegistry();
        }
      },
      error: () => this.ready.set(true),
    });
  }

  onLoggedIn(): void {
    this.api.me().subscribe((state) => {
      this.username.set(state.username);
      this.canAccess.set(state.can_access);
      if (state.can_access) {
        this.loadRegistry();
      }
    });
  }

  logout(): void {
    this.api.logout().subscribe(() => {
      this.canAccess.set(false);
      this.username.set(null);
      this.models.set([]);
    });
  }

  private loadRegistry(): void {
    this.api.getRegistry().subscribe({
      next: (r) => {
        this.siteTitle = r.site.title || this.siteTitle;
        this.models.set(r.models);
      },
      error: () => this.models.set([]),
    });
  }
}
