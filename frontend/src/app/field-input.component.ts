import { Component, Input } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';

import { FieldSpec, RelationValue } from './models';
import { RelationSelectComponent } from './relation-select.component';
import { WidgetKind, inputTypeFor, widgetFor } from './field-widgets';

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
export class FieldInputComponent {
  @Input({ required: true }) field!: FieldSpec;
  @Input({ required: true }) control!: FormControl;
  @Input() initial: RelationValue | RelationValue[] | null = null;
  @Input() form?: FormGroup;

  widgetType(): WidgetKind {
    return widgetFor(this.field.type);
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
