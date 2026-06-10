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
};

export function getConfig(): TheiaNgConfig {
  return window.__THEIA_NG_CONFIG__ ?? FALLBACK;
}
