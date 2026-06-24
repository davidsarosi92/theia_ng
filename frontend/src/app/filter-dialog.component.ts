import { Component, Input, inject, output, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';

import { FieldInputComponent } from './field-input.component';
import { I18nService } from './i18n.service';
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
        @if (e.kind === 'field' && isDate(e.field)) {
          <label class="field">
            <span class="field-label">When</span>
            <select [value]="datePreset()" (change)="datePreset.set($any($event.target).value)">
              <option value="specific">Specific date</option>
              @for (p of datePresets; track p.key) {
                <option [value]="p.key">{{ p.label }}</option>
              }
            </select>
          </label>
          @if (datePreset() === 'specific') {
            <label class="field">
              <span class="field-label">Date</span>
              <input type="date" [formControl]="valueControl" />
            </label>
          }
        } @else if (e.kind === 'field') {
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
        <button type="button" class="btn" [disabled]="!valid()" (click)="apply()">{{ t('ok') }}</button>
        <button type="button" (click)="closed.emit()">{{ t('cancel') }}</button>
      </div>
    </div>
  `,
})
export class FilterDialogComponent {
  private i18n = inject(I18nService);
  protected t = this.i18n.t;

  @Input({ required: true }) schema!: ModelSchema;
  applied = output<AppliedFilter>();
  closed = output<void>();

  selectedKey = signal('');
  valueControl = new FormControl<unknown>(null);

  /** Relative date presets (mirrors the server's `_DATE_PRESETS`). */
  readonly datePresets = [
    { key: 'today', label: 'Today' },
    { key: 'last_2_days', label: 'Last 2 days' },
    { key: 'last_7_days', label: 'Last 7 days' },
    { key: 'last_30_days', label: 'Last 30 days' },
    { key: 'last_year', label: 'Last year' },
  ];
  /** 'specific' = pick a date; otherwise a preset key. */
  datePreset = signal('specific');

  isDate(f: FieldSpec): boolean {
    return f.type === 'date' || f.type === 'datetime';
  }

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
    this.datePreset.set('specific');
    const e = this.current();
    const boolField = e?.kind === 'field' && e.field.type === 'boolean';
    this.valueControl = new FormControl<unknown>(boolField ? false : null);
  }

  /** The value to apply: a date preset key, or the control's value. */
  private resolvedValue(e: Entry): unknown {
    if (e.kind === 'field' && this.isDate(e.field) && this.datePreset() !== 'specific') {
      return this.datePreset();
    }
    return this.valueControl.value;
  }

  /** No empty filters: booleans/presets are always valid; everything else needs
   *  a non-empty value. */
  valid(): boolean {
    const e = this.current();
    if (!e) {
      return false;
    }
    if (e.kind === 'field') {
      if (e.field.type === 'boolean') {
        return true;
      }
      if (this.isDate(e.field) && this.datePreset() !== 'specific') {
        return true;
      }
    }
    const v = this.valueControl.value;
    return v !== null && v !== undefined && v !== '';
  }

  apply(): void {
    const e = this.current();
    if (!e || !this.valid()) {
      return;
    }
    const value = this.resolvedValue(e);
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
    if (this.isDate(f)) {
      const preset = this.datePresets.find((p) => p.key === value);
      if (preset) {
        return preset.label;
      }
    }
    if (value === null || value === undefined || value === '') {
      return '(empty)';
    }
    return String(value);
  }
}
