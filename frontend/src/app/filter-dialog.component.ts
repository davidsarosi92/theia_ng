import { Component, Input, output, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';

import { FieldInputComponent } from './field-input.component';
import { FieldSpec, ModelSchema } from './models';

export interface AppliedFilter {
  field: string;
  label: string;
  value: unknown;
  display: string;
}

@Component({
  selector: 'theia-filter-dialog',
  standalone: true,
  imports: [ReactiveFormsModule, FieldInputComponent],
  template: `
    <div class="dialog-backdrop" (click)="closed.emit()"></div>
    <div class="dialog">
      <h3>Add filter</h3>

      <label class="field">
        <span class="field-label">Field</span>
        <select [value]="selectedName()" (change)="selectField($any($event.target).value)">
          <option value="">— choose —</option>
          @for (f of filterable(); track f.name) {
            <option [value]="f.name">{{ f.label }}</option>
          }
        </select>
      </label>

      @if (selectedField(); as f) {
        <theia-field [field]="f" [control]="valueControl" />
      }

      <div class="actions">
        <button type="button" class="btn" [disabled]="!selectedName()" (click)="apply()">OK</button>
        <button type="button" (click)="closed.emit()">Cancel</button>
      </div>
    </div>
  `,
})
export class FilterDialogComponent {
  @Input({ required: true }) schema!: ModelSchema;
  applied = output<AppliedFilter>();
  closed = output<void>();

  selectedName = signal('');
  valueControl = new FormControl<unknown>(null);

  filterable(): FieldSpec[] {
    const names = new Set(this.schema.list.filters);
    return this.schema.fields.filter((f) => names.has(f.name));
  }

  selectedField(): FieldSpec | undefined {
    return this.schema.fields.find((f) => f.name === this.selectedName());
  }

  selectField(name: string): void {
    this.selectedName.set(name);
    const f = this.selectedField();
    this.valueControl = new FormControl<unknown>(f?.type === 'boolean' ? false : null);
  }

  apply(): void {
    const f = this.selectedField();
    if (!f) {
      return;
    }
    const value = this.valueControl.value;
    this.applied.emit({ field: f.name, label: f.label, value, display: this.display(f, value) });
    this.closed.emit();
  }

  private display(f: FieldSpec, value: unknown): string {
    if (f.type === 'boolean') {
      return value ? 'Yes' : 'No';
    }
    if (f.type === 'choice') {
      return f.choices?.find((c) => c.value === value)?.label ?? String(value);
    }
    if (value === null || value === undefined || value === '') {
      return '(empty)';
    }
    return String(value);
  }
}
