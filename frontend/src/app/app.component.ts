import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';

import { ApiService } from './api.service';
import { LoginComponent } from './login.component';
import { RegistryModel } from './models';
import { getConfig } from './theia-config';

@Component({
  selector: 'theia-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, LoginComponent],
  template: `
    @if (ready()) {
      @if (canAccess()) {
        <div class="layout">
          <aside class="sidebar">
            <h1 class="brand">{{ siteTitle }}</h1>
            <nav>
              <a routerLink="/" class="nav-home">Home</a>
              @for (m of models(); track m.key) {
                <a [routerLink]="['/', m.key]">{{ m.verbose_name_plural }}</a>
              }
            </nav>
            <div class="user-box">
              <span class="username">{{ username() }}</span>
              <button class="link-btn" (click)="logout()">Sign out</button>
            </div>
          </aside>
          <main class="content">
            <router-outlet />
          </main>
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
  models = signal<RegistryModel[]>([]);
  ready = signal(false);
  canAccess = signal(false);
  username = signal<string | null>(null);

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
