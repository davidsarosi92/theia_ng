import { Component, Input, output, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';

import { FieldInputComponent } from './field-input.component';
import { CustomFilter, FieldSpec, ModelSchema } from './models';

export interface AppliedFilter {
  /** Query-param key: a field name, or a custom filter's param. */
  field: string;
  label: string;
  value: unknown;
  display: string;
}

interface FieldEntry {
  kind: 'field';
  key: string;
  label: string;
  field: FieldSpec;
}
interface CustomEntry {
  kind: 'custom';
  key: string;
  label: string;
  filter: CustomFilter;
}
type Entry = FieldEntry | CustomEntry;

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
        <select [value]="selectedKey()" (change)="select($any($event.target).value)">
          <option value="">— choose —</option>
          @for (e of entries(); track e.key) {
            <option [value]="e.key">{{ e.label }}</option>
          }
        </select>
      </label>

      @if (current(); as e) {
        @if (e.kind === 'field') {
          <theia-field [field]="e.field" [control]="valueControl" />
        } @else {
          <label class="field">
            <span class="field-label">{{ e.label }}</span>
            <select [formControl]="valueControl">
              <option [ngValue]="null">—</option>
              @for (c of e.filter.choices; track c.value) {
                <option [ngValue]="c.value">{{ c.label }}</option>
              }
            </select>
          </label>
        }
      }

      <div class="actions">
        <button type="button" class="btn" [disabled]="!selectedKey()" (click)="apply()">OK</button>
        <button type="button" (click)="closed.emit()">Cancel</button>
      </div>
    </div>
  `,
})
export class FilterDialogComponent {
  @Input({ required: true }) schema!: ModelSchema;
  applied = output<AppliedFilter>();
  closed = output<void>();

  selectedKey = signal('');
  valueControl = new FormControl<unknown>(null);

  /** Field filters + custom filters, keyed `field:<name>` / `custom:<param>`. */
  entries(): Entry[] {
    const fieldNames = new Set(this.schema.list.filters);
    const fields: Entry[] = this.schema.fields
      .filter((f) => fieldNames.has(f.name))
      .map((f) => ({ kind: 'field', key: 'field:' + f.name, label: f.label, field: f }));
    const customs: Entry[] = (this.schema.list.custom_filters ?? []).map((cf) => ({
      kind: 'custom',
      key: 'custom:' + cf.param,
      label: cf.label,
      filter: cf,
    }));
    return [...fields, ...customs];
  }

  current(): Entry | undefined {
    return this.entries().find((e) => e.key === this.selectedKey());
  }

  select(key: string): void {
    this.selectedKey.set(key);
    const e = this.current();
    const boolField = e?.kind === 'field' && e.field.type === 'boolean';
    this.valueControl = new FormControl<unknown>(boolField ? false : null);
  }

  apply(): void {
    const e = this.current();
    if (!e) {
      return;
    }
    const value = this.valueControl.value;
    if (e.kind === 'field') {
      this.applied.emit({
        field: e.field.name,
        label: e.field.label,
        value,
        display: this.fieldDisplay(e.field, value),
      });
    } else {
      const label = e.filter.choices.find((c) => c.value === value)?.label ?? String(value);
      this.applied.emit({ field: e.filter.param, label: e.label, value, display: label });
    }
    this.closed.emit();
  }

  private fieldDisplay(f: FieldSpec, value: unknown): string {
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
