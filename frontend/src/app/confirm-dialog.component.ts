import { Component, Input, inject, output } from '@angular/core';

import { I18nService } from './i18n.service';

/** A small modal confirmation, replacing the browser's `confirm()` alert.
 *  Labels are optional: when a caller omits one it falls back to the translated
 *  default, so the dialog (incl. its Cancel button) is never left in English. */
@Component({
  selector: 'theia-confirm-dialog',
  standalone: true,
  template: `
    <div class="dialog-backdrop" (click)="cancelled.emit()"></div>
    <div class="dialog confirm-dialog">
      @if (title) {
        <h3>{{ title }}</h3>
      }
      <p>{{ message || t('confirmDefault') }}</p>
      @if (hint) {
        <p class="section-desc">{{ hint }}</p>
      }
      <div class="confirm-actions">
        <button type="button" class="btn" [class.danger]="danger" (click)="confirmed.emit()">
          {{ confirmLabel || t('confirm') }}
        </button>
        <button type="button" (click)="cancelled.emit()">{{ cancelLabel || t('cancel') }}</button>
      </div>
    </div>
  `,
})
export class ConfirmDialogComponent {
  @Input() title = '';
  @Input() message = '';
  /** Optional second line clarifying the consequence (e.g. link vs entity). */
  @Input() hint = '';
  @Input() confirmLabel = '';
  @Input() cancelLabel = '';
  @Input() danger = false;
  confirmed = output<void>();
  cancelled = output<void>();

  private i18n = inject(I18nService);
  protected t = this.i18n.t;
}
