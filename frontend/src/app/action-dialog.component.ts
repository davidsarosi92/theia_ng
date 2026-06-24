import { Component, Input, OnInit, inject, output, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';

import { ApiService } from './api.service';
import { FieldInputComponent } from './field-input.component';
import { I18nService } from './i18n.service';
import { ActionSpec } from './models';
import { ToastService } from './toast.service';

/** A modal form for a parameterized action: builds inputs from the action's
 *  fields (reusing theia-field, so it gets relation pickers etc. for free),
 *  then POSTs the collected params + selected ids. */
@Component({
  selector: 'theia-action-dialog',
  standalone: true,
  imports: [ReactiveFormsModule, FieldInputComponent],
  template: `
    <div class="dialog-backdrop" (click)="closed.emit()"></div>
    <div class="dialog">
      <h3>{{ action.label }}</h3>

      @if (errors()['__all__']; as nonField) {
        <div class="errors">{{ nonField.join(' ') }}</div>
      }

      <form [formGroup]="form" (ngSubmit)="run()">
        @for (field of action.fields; track field.name) {
          <theia-field [field]="field" [control]="controlFor(field.name)" [form]="form" />
          @if (errors()[field.name]; as fieldErrors) {
            <div class="errors">{{ fieldErrors.join(' ') }}</div>
          }
        }

        <div class="confirm-actions">
          <button type="submit" class="btn" [disabled]="running()">{{ t('run') }}</button>
          <button type="button" (click)="closed.emit()">{{ t('cancel') }}</button>
        </div>
      </form>
    </div>
  `,
})
export class ActionDialogComponent implements OnInit {
  private api = inject(ApiService);
  private toast = inject(ToastService);
  private i18n = inject(I18nService);
  protected t = this.i18n.t;

  @Input({ required: true }) action!: ActionSpec;
  /** Selected row ids (for selection-based actions; empty for 'none'). */
  @Input() ids: (number | string)[] = [];
  done = output<unknown>();
  closed = output<void>();

  form = new FormGroup({});
  errors = signal<Record<string, string[]>>({});
  running = signal(false);

  ngOnInit(): void {
    const group: Record<string, FormControl> = {};
    for (const field of this.action.fields) {
      const isArray = field.type === 'm2m' || field.widget === 'multiselect';
      group[field.name] = new FormControl(isArray ? [] : field.default ?? null);
    }
    this.form = new FormGroup(group);
  }

  controlFor(name: string): FormControl {
    return this.form.get(name) as FormControl;
  }

  run(): void {
    this.running.set(true);
    this.errors.set({});
    this.api.runAction(this.action.endpoint, { ids: this.ids, params: this.form.value }).subscribe({
      next: (res) => {
        this.running.set(false);
        this.toast.success(this.action.label + ' — done.');
        this.done.emit(res);
      },
      error: (err) => {
        this.running.set(false);
        this.errors.set(err?.error?.errors ?? { __all__: ['Action failed.'] });
        this.toast.error(this.action.label + ' failed.');
      },
    });
  }
}
