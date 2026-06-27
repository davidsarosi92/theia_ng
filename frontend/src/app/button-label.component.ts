import { Component, Input } from '@angular/core';

import { IconComponent } from './icon.component';

/** Logical button-icon name → icon-set name. Only buttons given one of these
 *  participate in the icon/label toggle. */
const ICON_FOR: Record<string, string> = {
  save: 'check',
  saveContinue: 'check',
  apply: 'check',
  ok: 'check',
  cancel: 'x',
  clear: 'x',
  back: 'arrow-left',
  add: 'plus',
  edit: 'pencil',
  view: 'eye',
  delete: 'trash',
  deleteEntity: 'trash',
  removeLink: 'circle-slash',
  filter: 'funnel',
  run: 'play',
  choose: 'search',
};

/** A button's content as an icon + label pair. Which parts show is driven by the
 *  user's `button_style` preference, reflected on `<html data-btn>` and applied
 *  in CSS (`.bico` / `.btxt`): label-only (default), icon-only, or both. In
 *  icon-only mode the label is visually hidden but kept for screen readers. */
@Component({
  selector: 'theia-blabel',
  standalone: true,
  imports: [IconComponent],
  template: `@if (iconName(); as n) {<span class="bico"><theia-icon [name]="n" /></span>}<span class="btxt">{{ text }}</span>`,
})
export class ButtonLabelComponent {
  /** Logical icon name (key of ICON_FOR). */
  @Input() icon = '';
  @Input() text = '';

  iconName(): string | null {
    return ICON_FOR[this.icon] ?? null;
  }
}
