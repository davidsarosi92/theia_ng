import { APP_BASE_HREF } from '@angular/common';
import { provideHttpClient, withXsrfConfiguration } from '@angular/common/http';
import { ApplicationConfig, provideZonelessChangeDetection } from '@angular/core';
import { provideRouter, withInMemoryScrolling } from '@angular/router';

import { routes } from './app.routes';
import { getConfig } from './theia-config';

export const appConfig: ApplicationConfig = {
  providers: [
    // Zoneless: change detection is driven by signals (no zone.js dependency).
    provideZonelessChangeDetection(),
    // Scroll to top on forward navigation (e.g. opening a related record),
    // restore the previous position on back.
    provideRouter(
      routes,
      withInMemoryScrolling({ scrollPositionRestoration: 'enabled', anchorScrolling: 'enabled' }),
    ),
    // Django session auth: send the CSRF token on unsafe requests.
    provideHttpClient(
      withXsrfConfiguration({
        cookieName: 'csrftoken',
        headerName: 'X-CSRFToken',
      }),
    ),
    // Router base = the runtime mount prefix (prefix-independent bundle).
    { provide: APP_BASE_HREF, useFactory: () => getConfig().basePrefix },
  ],
};
