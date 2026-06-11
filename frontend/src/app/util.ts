/** Model keys are `app_label.model_name`. URLs use a hyphen instead of the dot
 *  so they read cleanly (`goods.stock` -> `goods-stock`). The dot is the only
 *  separator, so the swap round-trips losslessly. */
export const keyToSlug = (key: string): string => key.replace('.', '-');
export const slugToKey = (slug: string): string => slug.replace('-', '.');

/** Capitalize the first letter — used for menu and breadcrumb labels. */
export const cap = (s: string): string => (s ? s[0].toUpperCase() + s.slice(1) : s);
