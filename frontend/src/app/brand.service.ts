import { Injectable, signal } from '@angular/core';

import { getConfig } from './theia-config';

/** Site brand (title + logo) as signals, so an admin editing them on the Settings
 *  page updates the topbar live. Seeded from the injected config, refreshed from
 *  the registry payload on load, and pushed to by the site-config save. */
@Injectable({ providedIn: 'root' })
export class BrandService {
  private cfg = getConfig();
  readonly title = signal<string>(this.cfg.siteTitle);
  readonly logo = signal<string>(this.cfg.logoUrl);

  set(title: string | undefined, logo: string | undefined): void {
    if (title) {
      this.title.set(title);
    }
    if (logo !== undefined) {
      this.logo.set(logo);
    }
  }
}
