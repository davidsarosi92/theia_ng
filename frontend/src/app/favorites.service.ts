import { Injectable, inject, signal } from '@angular/core';

import { ApiService } from './api.service';

/** Per-user favorite model keys, stored server-side so they follow the user
 *  across devices.
 *
 *  Favorites are model keys (`app.model`); the home page intersects them with
 *  the permitted set, so a revoked model simply drops out of the list. Toggles
 *  update the signal optimistically, then persist (PUT replaces the list). */
@Injectable({ providedIn: 'root' })
export class FavoritesService {
  private api = inject(ApiService);
  /** Reactive list of favorite model keys (in display order). */
  readonly favorites = signal<string[]>([]);

  /** Load the signed-in user's favorites (call on boot / login). Pass null on
   *  logout to clear. Anonymous / no-access users just keep an empty list. */
  load(authenticated: boolean): void {
    if (!authenticated) {
      this.favorites.set([]);
      return;
    }
    this.api.getFavorites().subscribe({
      next: (r) => this.favorites.set(r.favorites ?? []),
      error: () => this.favorites.set([]),
    });
  }

  isFavorite(key: string): boolean {
    return this.favorites().includes(key);
  }

  toggle(key: string): void {
    const cur = this.favorites();
    const next = cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key];
    this.persist(next, cur);
  }

  /** Reorder favorites given the new order of the *visible* subset (the home
   *  page only shows favorites the user may still see). Non-visible favorite
   *  keys keep their slots, so a reorder never drops a temporarily hidden one. */
  reorder(visibleOrdered: string[]): void {
    const cur = this.favorites();
    const visible = new Set(visibleOrdered);
    let i = 0;
    const next = cur.map((k) => (visible.has(k) ? visibleOrdered[i++] : k));
    this.persist(next, cur);
  }

  /** Optimistically set + persist (PUT replaces the list); revert on failure. */
  private persist(next: string[], prev: string[]): void {
    this.favorites.set(next);
    this.api.saveFavorites(next).subscribe({
      next: (r) => this.favorites.set(r.favorites ?? next),
      error: () => this.favorites.set(prev),
    });
  }
}
