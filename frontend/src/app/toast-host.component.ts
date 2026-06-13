import { Component, inject } from '@angular/core';

import { ToastService } from './toast.service';

/** Renders the toast stack (top-right). Mounted once at the app root. */
@Component({
  selector: 'theia-toasts',
  standalone: true,
  template: `
    <div class="toast-stack">
      @for (t of toasts.toasts(); track t.id) {
        <div class="toast toast-{{ t.kind }}" (click)="toasts.dismiss(t.id)">
          <span class="toast-icon">{{ t.kind === 'success' ? '✓' : '✕' }}</span>
          <span class="toast-msg">{{ t.message }}</span>
          <button
            type="button"
            class="toast-close"
            (click)="$event.stopPropagation(); toasts.dismiss(t.id)"
            aria-label="Dismiss"
          >×</button>
        </div>
      }
    </div>
  `,
})
export class ToastHostComponent {
  toasts = inject(ToastService);
}
