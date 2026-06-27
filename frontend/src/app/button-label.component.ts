import { Component, Input } from '@angular/core';

/** Glyph per logical icon name. Monochrome unicode to match the app's chrome.
 *  Only buttons given one of these names participate in the icon/label toggle. */
const GLYPHS: Record<string, string> = {
  save: '✓',
  saveContinue: '✓',
  cancel: '✕',
  back: '←',
  add: '＋',
  edit: '✎',
  view: '👁',
  delete: '🗑',
  removeLink: '⊘',
  deleteEntity: '🗑',
  filter: '☰',
  apply: '✓',
  ok: '✓',
  run: '▶',
  choose: '⋯',
  clear: '✕',
  prev: '‹',
  next: '›',
};

/** A button's content as an icon + label pair. Which parts show is driven by the
 *  user's `button_style` preference, reflected on `<html data-btn>` and applied
 *  in CSS (`.bico` / `.btxt`): label-only (default), icon-only, or both. In
 *  icon-only mode the label is visually hidden but kept for screen readers. */
@Component({
  selector: 'theia-blabel',
  standalone: true,
  template: `@if (glyph()) {<span class="bico" aria-hidden="true">{{ glyph() }}</span>}<span class="btxt">{{ text }}</span>`,
})
export class ButtonLabelComponent {
  /** Logical icon name (key of GLYPHS). */
  @Input() icon = '';
  @Input() text = '';

  glyph(): string {
    return GLYPHS[this.icon] ?? '';
  }
}
