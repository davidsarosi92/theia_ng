import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { groupByApp } from './grouping';
import { RegistryModel } from './models';
import { getConfig } from './theia-config';
import { cap, keyToSlug } from './util';
import { ViewService } from './view.service';

@Component({
  selector: 'theia-home',
  standalone: true,
  imports: [RouterLink],
  template: `
    <h2>{{ title }}</h2>
    @for (g of groups(); track g.appLabel) {
      <section class="home-group">
        <h3 class="home-group-title">{{ cap(g.appName) }}</h3>
        <div class="card-grid">
          @for (m of g.models; track m.key) {
            <a
              class="model-card"
              [routerLink]="['/', slug(m.key)]"
              [style.background]="cardColor(m.key)"
            >
              {{ cap(m.verbose_name) }}
            </a>
          }
        </div>
      </section>
    } @empty {
      <p>Nothing to show in this view.</p>
    }
  `,
})
export class HomeComponent implements OnInit {
  private api = inject(ApiService);
  private vs = inject(ViewService);
  title = getConfig().siteTitle;
  cap = cap;
  slug = keyToSlug;

  private models = signal<RegistryModel[]>([]);
  /** Same models as the sidebar: permitted set, narrowed by the active view. */
  groups = computed(() => groupByApp(this.vs.filterModels(this.models())));

  ngOnInit(): void {
    this.api.getRegistry().subscribe((r) => {
      this.models.set(r.models);
      this.vs.setViews(r.views ?? []);
    });
  }

  /** A stable light pastel per model, so each card has its own colour. */
  cardColor(key: string): string {
    let hue = 0;
    for (let i = 0; i < key.length; i++) {
      hue = (hue * 31 + key.charCodeAt(i)) % 360;
    }
    return `hsl(${hue}, 70%, 95%)`;
  }
}
