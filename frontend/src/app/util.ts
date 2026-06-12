/** Model keys are `app_label.model_name`. URLs use a hyphen instead of the dot
 *  so they read cleanly (`goods.stock` -> `goods-stock`). The dot is the only
 *  separator, so the swap round-trips losslessly. */
export const keyToSlug = (key: string): string => key.replace('.', '-');
export const slugToKey = (slug: string): string => slug.replace('-', '.');

/** Capitalize the first letter — used for menu and breadcrumb labels. */
export const cap = (s: string): string => (s ? s[0].toUpperCase() + s.slice(1) : s);

/** A stable light pastel per key, so each home/app card gets its own colour. */
export const cardColor = (key: string): string => {
  let hue = 0;
  for (let i = 0; i < key.length; i++) {
    hue = (hue * 31 + key.charCodeAt(i)) % 360;
  }
  return `hsl(${hue}, 70%, 95%)`;
};
