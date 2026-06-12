import { Injectable, inject, signal } from '@angular/core';

import { ApiService } from './api.service';
import { MenuView, RegistryModel } from './models';

const VIEW_KEY = 'theia_ng:view';

/** Holds the admin-defined sidebar views and the active selection (remembered
 *  across sessions). Shared so the sidebar, list and detail all narrow to the
 *  active view consistently. Permissions are already applied server-side; a
 *  view only intersects further. */
@Injectable({ providedIn: 'root' })
export class ViewService {
  private api = inject(ApiService);
  readonly views = signal<MenuView[]>([]);
  readonly active = signal<string>(localStorage.getItem(VIEW_KEY) ?? '');

  /** Re-fetch the views (after a MenuView was created/edited/deleted) so the
   *  selector and sidebar update without a full reload. */
  reload(): void {
    this.api.getRegistry().subscribe((r) => this.setViews(r.views ?? []));
  }

  setViews(views: MenuView[]): void {
    this.views.set(views);
    // Drop a remembered view that no longer exists.
    if (this.active() && !views.some((v) => v.name === this.active())) {
      this.setActive('');
    }
  }

  setActive(name: string): void {
    this.active.set(name);
    localStorage.setItem(VIEW_KEY, name);
  }

  private current(): MenuView | undefined {
    return this.views().find((v) => v.name === this.active());
  }

  /** Models visible under the active view (all when "Full"). */
  filterModels(all: RegistryModel[]): RegistryModel[] {
    const v = this.current();
    if (!v) {
      return all;
    }
    const allowed = new Set(v.models);
    return all.filter((m) => allowed.has(m.key));
  }

  /** Visible field names for a model under the active view, in order; null = all
   *  (no active view, or no/empty field list for the model). */
  fieldsFor(modelKey: string): string[] | null {
    const v = this.current();
    const f = v?.fields?.[modelKey];
    return f && f.length ? f : null;
  }
}
