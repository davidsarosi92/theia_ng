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

/** Human, locale-aware rendering of an IR date/datetime/time value (ISO from the
 *  server). Falls back to the raw string if it can't be parsed. */
export const formatDateValue = (value: unknown, type: 'date' | 'datetime' | 'time'): string => {
  if (value === null || value === undefined || value === '') {
    return '';
  }
  const s = String(value);
  if (type === 'time') {
    // "14:30:00" / "14:30" -> "14:30"
    const m = /^(\d{2}:\d{2})/.exec(s);
    return m ? m[1] : s;
  }
  if (type === 'date') {
    // Parse Y-M-D as a local date so the day never shifts across time zones.
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
    const d = m ? new Date(+m[1], +m[2] - 1, +m[3]) : new Date(s);
    return isNaN(d.getTime()) ? s : d.toLocaleDateString();
  }
  const d = new Date(s);
  if (isNaN(d.getTime())) {
    return s;
  }
  return `${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
};
