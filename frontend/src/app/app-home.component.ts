import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { AppGroup, groupByApp } from './grouping';
import { RegistryModel } from './models';
import { cap, cardColor, keyToSlug } from './util';
import { ViewService } from './view.service';

/** Theia NG's own app_label — its landing page also offers the Activity card. */
const THEIA_APP = 'theia_ng';

/** A Home-like landing page for a single app: its model cards (the ones the user
 *  may see), without the favorites feature. Reached by clicking an app name in
 *  the sidebar. */
@Component({
  selector: 'theia-app-home',
  standalone: true,
  imports: [RouterLink],
  template: `
    <nav class="breadcrumb">
      <a routerLink="/">Home</a>
      <span class="sep">/</span>
      <span>{{ cap(appName()) }}</span>
    </nav>

    <h2>{{ cap(appName()) }}</h2>

    <div class="card-grid">
      @if (appLabel() === theiaApp) {
        <a class="model-card" routerLink="/logs" [style.background]="cardColor('theia_ng.activity')">
          <span class="card-label">Activity</span>
        </a>
      }
      @for (m of models(); track m.key) {
        <a class="model-card" [routerLink]="['/', slug(m.key)]" [style.background]="cardColor(m.key)">
          <span class="card-label">{{ cap(m.verbose_name) }}</span>
        </a>
      } @empty {
        @if (appLabel() !== theiaApp) {
          <p>Nothing to show in this app.</p>
        }
      }
    </div>
  `,
})
export class AppHomeComponent implements OnInit {
  private api = inject(ApiService);
  private route = inject(ActivatedRoute);
  private vs = inject(ViewService);
  cap = cap;
  slug = keyToSlug;
  cardColor = cardColor;
  theiaApp = THEIA_APP;

  appLabel = signal('');
  private allModels = signal<RegistryModel[]>([]);

  /** This app's group, narrowed to the permitted + view-filtered set. */
  private group = computed<AppGroup | null>(
    () =>
      groupByApp(this.vs.filterModels(this.allModels())).find(
        (g) => g.appLabel === this.appLabel(),
      ) ?? null,
  );
  appName = computed(
    () => this.group()?.appName || (this.appLabel() === THEIA_APP ? 'Theia NG Admin' : this.appLabel()),
  );
  models = computed<RegistryModel[]>(() => this.group()?.models ?? []);

  ngOnInit(): void {
    this.route.paramMap.subscribe((p) => this.appLabel.set(p.get('appLabel') ?? ''));
    this.api.getRegistry().subscribe((r) => {
      this.allModels.set(r.models);
      this.vs.setViews(r.views ?? []);
    });
  }
}
