import { Component, DestroyRef, Input, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { Subject, debounceTime, distinctUntilChanged, switchMap } from 'rxjs';

import { ApiService } from './api.service';
import { Choice, FieldSpec } from './models';
import { WidgetKind, inputTypeFor, widgetFor } from './field-widgets';

@Component({
  selector: 'theia-field',
  standalone: true,
  imports: [ReactiveFormsModule],
  template: `
    <label class="field">
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
          @if (field.relation?.searchable) {
            <input
              type="text"
              class="rel-search"
              placeholder="Search…"
              (input)="search$.next($any($event.target).value)"
            />
          }
          <select [formControl]="control" [multiple]="field.type === 'm2m'">
            @if (field.type === 'fk') {
              <option [ngValue]="null">—</option>
            }
            @for (o of options(); track o.id) {
              <option [ngValue]="o.id">{{ o.label }}</option>
            }
          </select>
        }
        @default {
          <input [type]="inputType()" [formControl]="control" />
        }
      }

      @if (field.help_text) {
        <small class="help">{{ field.help_text }}</small>
      }
    </label>
  `,
})
export class FieldInputComponent implements OnInit {
  @Input({ required: true }) field!: FieldSpec;
  @Input({ required: true }) control!: FormControl;

  private api = inject(ApiService);
  private destroyRef = inject(DestroyRef);
  options = signal<{ id: number | string; label: string }[]>([]);
  search$ = new Subject<string>();

  ngOnInit(): void {
    const rel = this.field.relation;
    if (!rel) {
      return;
    }
    // Live, debounced autocomplete against the relation's options endpoint.
    this.search$
      .pipe(
        debounceTime(250),
        distinctUntilChanged(),
        switchMap((term) => this.api.options(rel.options_endpoint, term)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((resp) => this.setOptions(resp.results, rel.display_field));
    // Initial population.
    this.api.options(rel.options_endpoint, '').subscribe((resp) =>
      this.setOptions(resp.results, rel.display_field),
    );
  }

  widgetType(): WidgetKind {
    return widgetFor(this.field.type);
  }

  inputType(): string {
    return inputTypeFor(this.field.type);
  }

  private setOptions(rows: Record<string, unknown>[], displayField: string): void {
    this.options.set(
      rows.map((r) => ({ id: r['pk'] as number | string, label: this.displayOf(r, displayField) })),
    );
  }

  private displayOf(row: Record<string, unknown>, displayField: string): string {
    const value = row[displayField];
    if (value && typeof value === 'object' && 'label' in (value as object)) {
      return String((value as Choice).label);
    }
    return value != null ? String(value) : String(row['pk']);
  }
}
