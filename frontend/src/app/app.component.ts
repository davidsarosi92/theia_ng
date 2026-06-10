import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';

import { ApiService } from './api.service';
import { RegistryModel } from './models';
import { getConfig } from './theia-config';

@Component({
  selector: 'theia-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink],
  template: `
    <div class="layout">
      <aside class="sidebar">
        <h1 class="brand">{{ siteTitle }}</h1>
        <nav>
          <a routerLink="/" class="nav-home">Home</a>
          @for (m of models(); track m.key) {
            <a [routerLink]="['/', m.key]">{{ m.verbose_name_plural }}</a>
          }
        </nav>
      </aside>
      <main class="content">
        <router-outlet />
      </main>
    </div>
  `,
})
export class AppComponent implements OnInit {
  private api = inject(ApiService);
  siteTitle = getConfig().siteTitle;
  models = signal<RegistryModel[]>([]);

  ngOnInit(): void {
    this.api.getRegistry().subscribe({
      next: (r) => {
        this.siteTitle = r.site.title || this.siteTitle;
        this.models.set(r.models);
      },
      error: () => this.models.set([]),
    });
  }
}
