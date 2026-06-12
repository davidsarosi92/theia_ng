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
    this.favorites.set(next); // optimistic
    this.api.saveFavorites(next).subscribe({
      // Reconcile with the server's canonical order/dedupe; revert on failure.
      next: (r) => this.favorites.set(r.favorites ?? next),
      error: () => this.favorites.set(cur),
    });
  }
}
