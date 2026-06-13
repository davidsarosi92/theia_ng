import { Component, Input, output } from '@angular/core';

/** A small modal confirmation, replacing the browser's `confirm()` alert. */
@Component({
  selector: 'theia-confirm-dialog',
  standalone: true,
  template: `
    <div class="dialog-backdrop" (click)="cancelled.emit()"></div>
    <div class="dialog confirm-dialog">
      @if (title) {
        <h3>{{ title }}</h3>
      }
      <p>{{ message }}</p>
      <div class="confirm-actions">
        <button type="button" class="btn" [class.danger]="danger" (click)="confirmed.emit()">
          {{ confirmLabel }}
        </button>
        <button type="button" (click)="cancelled.emit()">{{ cancelLabel }}</button>
      </div>
    </div>
  `,
})
export class ConfirmDialogComponent {
  @Input() title = '';
  @Input() message = 'Are you sure?';
  @Input() confirmLabel = 'Confirm';
  @Input() cancelLabel = 'Cancel';
  @Input() danger = false;
  confirmed = output<void>();
  cancelled = output<void>();
}
