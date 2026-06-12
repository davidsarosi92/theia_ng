import { Component, DestroyRef, Input, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';

import { Choice, FieldSpec, RelationValue } from './models';
import { RelationSelectComponent } from './relation-select.component';
import { WidgetKind, inputTypeFor, widgetFor } from './field-widgets';
import { cap } from './util';

@Component({
  selector: 'theia-field',
  standalone: true,
  imports: [ReactiveFormsModule, RelationSelectComponent],
  template: `
    <!-- A plain <div>, NOT a <label>: a <label> forwards clicks on non-control
         areas (e.g. the relation trigger) to its first form control — which for
         the relation widget is the View button, causing accidental navigation. -->
    <div class="field">
      <span class="field-label">
        {{ field.label }}@if (field.required) {<em class="req">*</em>}
      </span>

      @switch (widgetType()) {
        @case ('textarea') {
          <textarea [formControl]="control" rows="4"></textarea>
        }
        @case ('checkbox') {
          <input type="checkbox" [formControl]="control" />
        }
        @case ('select') {
          <select [formControl]="control">
            <option [ngValue]="null">—</option>
            @for (c of field.choices ?? []; track c.value) {
              <option [ngValue]="c.value">{{ c.label }}</option>
            }
          </select>
        }
        @case ('multiselect') {
          <div class="multiselect">
            @for (c of field.choices ?? []; track c.value) {
              <label class="ms-opt">
                <input
                  type="checkbox"
                  [checked]="isChecked(c.value)"
                  [disabled]="control.disabled"
                  (change)="toggleChoice(c.value, $any($event.target).checked)"
                />
                {{ cap(c.label) }}
              </label>
            }
          </div>
        }
        @case ('model_field_select') {
          <!-- For each model selected in the sibling field, pick its fields. -->
          @for (mk of selectedKeys(); track mk) {
            <div class="mfs-group">
              <div class="mfs-title">{{ cap(modelLabel(mk)) }}</div>
              @for (c of fieldsOf(mk); track c.value) {
                <label class="ms-opt">
                  <input
                    type="checkbox"
                    [checked]="isFieldChecked(mk, c.value)"
                    [disabled]="control.disabled"
                    (change)="toggleField(mk, c.value, $any($event.target).checked)"
                  />
                  {{ cap(c.label) }}
                </label>
              }
              <small class="help">Empty = all fields.</small>
            </div>
          } @empty {
            <small class="help">Select models first.</small>
          }
        }
        @case ('relation') {
          @if (rawInput()) {
            <!-- raw_id_fields, or an unregistered FK target: plain id input(s)
                 instead of a picker. M2M takes comma-separated ids. -->
            @if (field.type === 'm2m') {
              <input
                type="text"
                placeholder="comma-separated ids"
                [value]="m2mText()"
                [disabled]="control.disabled"
                (input)="onM2mInput($any($event.target).value)"
              />
            } @else {
              <input type="text" [formControl]="control" />
            }
          } @else {
            <theia-relation-select
              [field]="field"
              [control]="control"
              [initial]="initial"
              [form]="form"
              [locked]="field.relation?.registered === false"
            />
          }
        }
        @default {
          <input [type]="inputType()" [formControl]="control" />
        }
      }

      @if (field.help_text) {
        <small class="help">{{ field.help_text }}</small>
      }
    </div>
  `,
})
export class FieldInputComponent implements OnInit {
  @Input({ required: true }) field!: FieldSpec;
  @Input({ required: true }) control!: FormControl;
  @Input() initial: RelationValue | RelationValue[] | null = null;
  @Input() form?: FormGroup;
  cap = cap;

  private destroyRef = inject(DestroyRef);
  /** model_field_select: the model keys currently chosen in the sibling field. */
  selectedKeys = signal<string[]>([]);
  /** Bumped on control value changes so checkbox state re-renders (zoneless). */
  private rev = signal(0);

  ngOnInit(): void {
    const widget = this.field.widget;
    if (widget === 'multiselect' || widget === 'model_field_select') {
      // The form control isn't a signal: re-render checkbox state whenever its
      // value changes (incl. the async record load and toggles).
      this.control.valueChanges
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe(() => this.rev.update((n) => n + 1));
    }
    if (widget === 'model_field_select' && this.field.models_field && this.form) {
      const sibling = this.form.get(this.field.models_field);
      const sync = () =>
        this.selectedKeys.set(Array.isArray(sibling?.value) ? sibling!.value : []);
      sync();
      sibling?.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(sync);
    }
  }

  widgetType(): WidgetKind {
    // A widget hint (registry_choice_fields / model_field_select) overrides the
    // type-derived widget.
    if (this.field.widget === 'multiselect' || this.field.widget === 'model_field_select') {
      return this.field.widget;
    }
    return widgetFor(this.field.type);
  }

  // --- model_field_select (per-model field picker; value = {key: [fields]}) ---
  modelLabel(modelKey: string): string {
    return this.field.field_choices?.[modelKey]?.label ?? modelKey;
  }

  fieldsOf(modelKey: string): Choice[] {
    return this.field.field_choices?.[modelKey]?.fields ?? [];
  }

  isFieldChecked(modelKey: string, value: string | number): boolean {
    this.rev(); // track for re-render in zoneless
    const map = this.control.value;
    return Array.isArray(map?.[modelKey]) && map[modelKey].includes(value);
  }

  toggleField(modelKey: string, value: string | number, checked: boolean): void {
    const map = { ...(this.control.value || {}) } as Record<string, unknown[]>;
    const cur = Array.isArray(map[modelKey]) ? [...map[modelKey]] : [];
    map[modelKey] = checked ? [...new Set([...cur, value])] : cur.filter((x) => x !== value);
    this.control.setValue(map);
    this.control.markAsDirty();
  }

  // --- multiselect (array-valued checkbox group) ---------------------------
  isChecked(value: string | number): boolean {
    this.rev(); // track for re-render in zoneless
    const v = this.control.value;
    return Array.isArray(v) && v.includes(value);
  }

  toggleChoice(value: string | number, checked: boolean): void {
    const cur: unknown[] = Array.isArray(this.control.value) ? [...this.control.value] : [];
    const next = checked ? [...new Set([...cur, value])] : cur.filter((x) => x !== value);
    this.control.setValue(next);
    this.control.markAsDirty();
  }

  inputType(): string {
    return inputTypeFor(this.field.type);
  }

  /** Render the relation as a plain id input: explicit raw_id_fields, or an
   *  unregistered FK target (which has no picker endpoint). */
  rawInput(): boolean {
    const r = this.field.relation;
    return !!r && (r.raw === true || (this.field.type === 'fk' && r.registered === false));
  }

  /** M2M raw value (array of ids) <-> comma-separated text. */
  m2mText(): string {
    const v = this.control.value;
    return Array.isArray(v) ? v.join(', ') : '';
  }

  onM2mInput(text: string): void {
    const ids = text
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      .map((s) => (/^\d+$/.test(s) ? Number(s) : s));
    this.control.setValue(ids);
    this.control.markAsDirty();
  }
}
