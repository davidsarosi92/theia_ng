/**
 * Runtime configuration, injected by the Django `spa_index` view into
 * `window.__THEIA_NG_CONFIG__`. Reading it at runtime (rather than baking it in
 * at build time) keeps the bundle prefix-independent: one build works under any
 * mount prefix.
 */
export interface TheiaNgConfig {
  basePrefix: string;
  apiBase: string;
  siteTitle: string;
  schemaVersion: string;
  /** Installed theia_ng package version, shown as a footnote in the topbar. */
  version: string;
  /** Brand logo URL shown before the title (empty = none). */
  logoUrl: string;
  /** Django's active UI language (base code), used until per-user settings load. */
  defaultLanguage: string;
  /** Django's active timezone name, used until per-user settings load. */
  defaultTimezone: string;
}

declare global {
  interface Window {
    __THEIA_NG_CONFIG__?: TheiaNgConfig;
  }
}

const FALLBACK: TheiaNgConfig = {
  basePrefix: '/theia/',
  apiBase: '/theia/api/',
  siteTitle: 'Theia NG Admin',
  schemaVersion: '1.0',
  version: '',
  logoUrl: '',
  defaultLanguage: 'en',
  defaultTimezone: 'UTC',
};

export function getConfig(): TheiaNgConfig {
  // Merge over the fallback so older Django backends that inject a partial
  // config (missing logoUrl / locale defaults) still yield a complete object.
  return { ...FALLBACK, ...(window.__THEIA_NG_CONFIG__ ?? {}) };
}
