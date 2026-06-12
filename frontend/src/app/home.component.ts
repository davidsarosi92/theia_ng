import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { FavoritesService } from './favorites.service';
import { AppGroup, groupByApp } from './grouping';
import { RegistryModel } from './models';
import { getConfig } from './theia-config';
import { cap, cardColor, keyToSlug } from './util';
import { ViewService } from './view.service';

/** Theia NG's own app_label — pinned last, hosts the Activity card. */
const THEIA_APP = 'theia_ng';

@Component({
  selector: 'theia-home',
  standalone: true,
  imports: [RouterLink],
  template: `
    <h2>{{ title }}</h2>

    @if (favorites().length) {
      <section class="home-group">
        <h3 class="home-group-title">★ Favorites</h3>
        <div class="card-grid">
          @for (m of favorites(); track m.key) {
            <a class="model-card" [routerLink]="['/', slug(m.key)]" [style.background]="cardColor(m.key)">
              <span class="card-label">{{ cap(m.verbose_name) }}</span>
              <button
                class="fav-star on"
                (click)="toggleFav($event, m.key)"
                [attr.aria-label]="'Remove ' + m.verbose_name + ' from favorites'"
              >★</button>
            </a>
          }
        </div>
      </section>
    }

    @for (g of otherGroups(); track g.appLabel) {
      <section class="home-group">
        <h3 class="home-group-title">{{ cap(g.appName) }}</h3>
        <div class="card-grid">
          @for (m of g.models; track m.key) {
            <a class="model-card" [routerLink]="['/', slug(m.key)]" [style.background]="cardColor(m.key)">
              <span class="card-label">{{ cap(m.verbose_name) }}</span>
              <button
                class="fav-star"
                [class.on]="isFav(m.key)"
                (click)="toggleFav($event, m.key)"
                [attr.aria-label]="(isFav(m.key) ? 'Remove ' : 'Add ') + m.verbose_name"
              >{{ isFav(m.key) ? '★' : '☆' }}</button>
            </a>
          }
        </div>
      </section>
    }

    <!-- Theia NG Admin: Activity + its models (Menu views), pinned to the bottom. -->
    <section class="home-group">
      <h3 class="home-group-title">{{ adminTitle() }}</h3>
      <div class="card-grid">
        <a class="model-card" routerLink="/logs" [style.background]="cardColor('theia_ng.activity')">
          <span class="card-label">Activity</span>
        </a>
        @if (adminGroup(); as ag) {
          @for (m of ag.models; track m.key) {
            <a class="model-card" [routerLink]="['/', slug(m.key)]" [style.background]="cardColor(m.key)">
              <span class="card-label">{{ cap(m.verbose_name) }}</span>
              <button
                class="fav-star"
                [class.on]="isFav(m.key)"
                (click)="toggleFav($event, m.key)"
                [attr.aria-label]="(isFav(m.key) ? 'Remove ' : 'Add ') + m.verbose_name"
              >{{ isFav(m.key) ? '★' : '☆' }}</button>
            </a>
          }
        }
      </div>
    </section>
  `,
})
export class HomeComponent implements OnInit {
  private api = inject(ApiService);
  private vs = inject(ViewService);
  private favs = inject(FavoritesService);
  title = getConfig().siteTitle;
  cap = cap;
  slug = keyToSlug;
  cardColor = cardColor;

  private models = signal<RegistryModel[]>([]);
  /** Same models as the sidebar: permitted set, narrowed by the active view. */
  private visible = computed(() => this.vs.filterModels(this.models()));
  private groups = computed(() => groupByApp(this.visible()));
  /** Theia NG's own group (Menu views) — rendered last, with the Activity card. */
  adminGroup = computed<AppGroup | null>(
    () => this.groups().find((g) => g.appLabel === THEIA_APP) ?? null,
  );
  otherGroups = computed<AppGroup[]>(() => this.groups().filter((g) => g.appLabel !== THEIA_APP));
  adminTitle = computed(() => this.adminGroup()?.appName ?? 'Theia NG Admin');

  /** Favorite models the user can still see, in the order they were starred. */
  favorites = computed<RegistryModel[]>(() => {
    const byKey = new Map(this.visible().map((m) => [m.key, m]));
    return this.favs
      .favorites()
      .map((key) => byKey.get(key))
      .filter((m): m is RegistryModel => !!m);
  });

  ngOnInit(): void {
    this.api.getRegistry().subscribe((r) => {
      this.models.set(r.models);
      this.vs.setViews(r.views ?? []);
    });
  }

  isFav(key: string): boolean {
    return this.favs.isFavorite(key);
  }

  /** Toggle without following the card's router link. */
  toggleFav(event: Event, key: string): void {
    event.preventDefault();
    event.stopPropagation();
    this.favs.toggle(key);
  }
}
