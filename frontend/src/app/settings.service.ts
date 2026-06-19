import { Injectable, inject, signal } from '@angular/core';

import { ApiService } from './api.service';
import { LanguageOption, ThemePref, UserSettings } from './models';
import { getConfig } from './theia-config';

/** localStorage key for the resolved theme, mirrored so the inline bootstrap in
 *  index.html can apply it before paint (no flash) while the user settings load. */
const THEME_KEY = 'theia-ng:theme';

/** Per-user UI preferences (language, timezone, theme, sidebar order).
 *
 *  State lives in signals so the zoneless app reacts to changes. Defaults come
 *  from the injected Django config until the signed-in user's saved settings
 *  arrive; mutations update optimistically, then PATCH the server. The theme is
 *  applied to `<html data-theme>` and mirrored to localStorage for before-paint
 *  application on the next load. */
@Injectable({ providedIn: 'root' })
export class SettingsService {
  private api = inject(ApiService);
  private cfg = getConfig();

  readonly language = signal<string>(this.cfg.defaultLanguage);
  readonly timezone = signal<string>(this.cfg.defaultTimezone);
  readonly theme = signal<ThemePref>('auto');
  readonly navAppOrder = signal<string[]>([]);
  readonly navOrder = signal<string[]>([]);
  readonly availableLanguages = signal<LanguageOption[]>([]);

  private mql?: MediaQueryList;

  constructor() {
    // Re-resolve `auto` when the OS scheme flips.
    if (typeof matchMedia === 'function') {
      this.mql = matchMedia('(prefers-color-scheme: dark)');
      this.mql.addEventListener('change', () => this.applyTheme());
    }
    this.applyTheme();
  }

  /** Load the signed-in user's settings (call on boot / login). Pass false on
   *  logout to fall back to config defaults. */
  load(authenticated: boolean): void {
    if (!authenticated) {
      this.language.set(this.cfg.defaultLanguage);
      this.timezone.set(this.cfg.defaultTimezone);
      this.theme.set('auto');
      this.navAppOrder.set([]);
      this.navOrder.set([]);
      this.applyTheme();
      return;
    }
    this.api.getSettings().subscribe({
      next: (s) => this.apply(s),
      error: () => {
        /* keep config defaults */
      },
    });
  }

  private apply(s: UserSettings): void {
    this.language.set(s.language || this.cfg.defaultLanguage);
    this.timezone.set(s.timezone || this.cfg.defaultTimezone);
    this.theme.set(s.theme ?? 'auto');
    this.navAppOrder.set(s.nav_app_order ?? []);
    this.navOrder.set(s.nav_order ?? []);
    if (s.available_languages) {
      this.availableLanguages.set(s.available_languages);
    }
    this.applyTheme();
  }

  setLanguage(code: string): void {
    if (code === this.language()) {
      return;
    }
    this.language.set(code);
    this.persist({ language: code });
  }

  setTimezone(tz: string): void {
    if (tz === this.timezone()) {
      return;
    }
    this.timezone.set(tz);
    this.persist({ timezone: tz });
  }

  setTheme(theme: ThemePref): void {
    this.theme.set(theme);
    this.applyTheme();
    this.persist({ theme });
  }

  setNavOrder(order: string[]): void {
    this.navOrder.set(order);
    this.persist({ nav_order: order });
  }

  setNavAppOrder(order: string[]): void {
    this.navAppOrder.set(order);
    this.persist({ nav_app_order: order });
  }

  /** The concrete theme in effect right now (`auto` resolved against the OS). */
  resolvedTheme(): 'light' | 'dark' {
    const pref = this.theme();
    if (pref === 'auto') {
      return this.mql?.matches ? 'dark' : 'light';
    }
    return pref;
  }

  private applyTheme(): void {
    const resolved = this.resolvedTheme();
    document.documentElement.setAttribute('data-theme', resolved);
    try {
      // Store the *preference* (not the resolved value) so a later OS change is
      // still honoured by the before-paint bootstrap when pref is `auto`.
      localStorage.setItem(THEME_KEY, this.theme());
    } catch {
      /* private mode / storage disabled — non-fatal */
    }
  }

  private persist(patch: Partial<UserSettings>): void {
    this.api.saveSettings(patch).subscribe({
      next: (s) => this.apply(s),
      error: () => {
        /* keep optimistic local state */
      },
    });
  }
}
