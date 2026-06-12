import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { FavoritesService } from './favorites.service';
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

    @for (g of groups(); track g.appLabel) {
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
    } @empty {
      <p>Nothing to show in this view.</p>
    }
  `,
})
export class HomeComponent implements OnInit {
  private api = inject(ApiService);
  private vs = inject(ViewService);
  private favs = inject(FavoritesService);
  title = getConfig().siteTitle;
  cap = cap;
  slug = keyToSlug;

  private models = signal<RegistryModel[]>([]);
  /** Same models as the sidebar: permitted set, narrowed by the active view. */
  private visible = computed(() => this.vs.filterModels(this.models()));
  groups = computed(() => groupByApp(this.visible()));

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

  /** A stable light pastel per model, so each card has its own colour. */
  cardColor(key: string): string {
    let hue = 0;
    for (let i = 0; i < key.length; i++) {
      hue = (hue * 31 + key.charCodeAt(i)) % 360;
    }
    return `hsl(${hue}, 70%, 95%)`;
  }
}
