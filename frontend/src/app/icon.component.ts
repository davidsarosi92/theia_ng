import { Component, Input, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

/** Inner markup per icon — a consistent monochrome, stroke-based set (24×24,
 *  `currentColor`) so icons inherit the button's colour and font size. Static,
 *  author-controlled strings (safe to trust). */
const ICONS: Record<string, string> = {
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  'arrow-left': '<path d="M19 12H5"/><path d="m12 19-7-7 7-7"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  pencil: '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  trash:
    '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>' +
    '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M10 11v6M14 11v6"/>',
  funnel: '<path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3Z"/>',
  play: '<path d="M6 3v18l15-9z"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  'circle-slash': '<circle cx="12" cy="12" r="9"/><path d="m6 6 12 12"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
};

/** Renders one icon from the built-in set by `name`, sized to the current font
 *  (1em) and stroked in the current colour. */
@Component({
  selector: 'theia-icon',
  standalone: true,
  template: `<span class="ticon" aria-hidden="true" [innerHTML]="svg()"></span>`,
})
export class IconComponent {
  @Input({ required: true }) name = '';

  private sanitizer = inject(DomSanitizer);
  private static cache = new Map<string, SafeHtml>();

  static has(name: string): boolean {
    return name in ICONS;
  }

  svg(): SafeHtml {
    let cached = IconComponent.cache.get(this.name);
    if (!cached) {
      const inner = ICONS[this.name] ?? '';
      cached = this.sanitizer.bypassSecurityTrustHtml(
        `<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor"` +
          ` stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`,
      );
      IconComponent.cache.set(this.name, cached);
    }
    return cached;
  }
}
