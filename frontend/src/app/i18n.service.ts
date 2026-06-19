import { Injectable, inject } from '@angular/core';

import { DEFAULT_LANG, MESSAGES, MessageKey } from './i18n/messages';
import { SettingsService } from './settings.service';

/** Runtime UI translation + locale/timezone-aware formatting.
 *
 *  `t()` reads the language signal (from SettingsService), so calling it in a
 *  template registers that signal as a dependency: switching language re-renders
 *  the bindings without a reload. Missing keys fall back to English, then to the
 *  key itself. Dates/numbers are formatted with `Intl` in the user's locale and
 *  timezone. */
@Injectable({ providedIn: 'root' })
export class I18nService {
  private settings = inject(SettingsService);
  /** Reactive current language code (e.g. `hu`). */
  readonly lang = this.settings.language;

  /** Translate `key`, substituting `{name}`-style placeholders from `params`.
   *  Bound as a field so components can expose it directly: `t = inject(...).t`. */
  t = (key: MessageKey, params?: Record<string, string | number>): string => {
    const code = this.lang();
    const table = MESSAGES[code] ?? MESSAGES[DEFAULT_LANG];
    let msg = table[key] ?? MESSAGES[DEFAULT_LANG][key] ?? key;
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        msg = msg.replace(`{${k}}`, String(v));
      }
    }
    return msg;
  };

  /** BCP-47 locale for `Intl` (the language code works directly for our set). */
  private locale(): string {
    return this.lang() || DEFAULT_LANG;
  }

  /** Format an IR date/datetime/time value (ISO from the server) in the user's
   *  locale and timezone. Date-only values are not timezone-shifted (a calendar
   *  date has no time-of-day to convert); datetimes are rendered in the user's tz. */
  formatDate = (value: unknown, type: 'date' | 'datetime' | 'time'): string => {
    if (value === null || value === undefined || value === '') {
      return '';
    }
    const s = String(value);
    const locale = this.locale();
    const tz = this.settings.timezone();

    if (type === 'time') {
      const m = /^(\d{2}):(\d{2})/.exec(s);
      if (!m) {
        return s;
      }
      const d = new Date(2000, 0, 1, +m[1], +m[2]);
      return new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit' }).format(d);
    }

    if (type === 'date') {
      // Parse Y-M-D as a plain calendar date (no tz conversion / day shift).
      const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
      const d = m ? new Date(+m[1], +m[2] - 1, +m[3]) : new Date(s);
      return isNaN(d.getTime()) ? s : new Intl.DateTimeFormat(locale).format(d);
    }

    const d = new Date(s);
    if (isNaN(d.getTime())) {
      return s;
    }
    return new Intl.DateTimeFormat(locale, {
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: tz || undefined,
    }).format(d);
  };
}
