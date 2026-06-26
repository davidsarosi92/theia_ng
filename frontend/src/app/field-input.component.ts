import { Component, DestroyRef, Input, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ApiService } from './api.service';
import { I18nService } from './i18n.service';
import { Choice, FieldSpec, Perms, RelationValue } from './models';
import { RelationPickerDialogComponent } from './relation-picker-dialog.component';
import { RelationSelectComponent } from './relation-select.component';
import { WidgetKind, inputTypeFor, widgetFor } from './field-widgets';
import { cap, keyToSlug } from './util';

@Component({
  selector: 'theia-field',
  standalone: true,
  imports: [ReactiveFormsModule, RelationSelectComponent, RelationPickerDialogComponent],
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
          @if (rawPickable()) {
            <!-- raw_id_fields with a registered target: a modal table picker that
                 only loads when opened (keeps the form light for huge tables). -->
            <div class="raw-rel">
              <span class="raw-rel-val">{{ rawLabel() || '—' }}</span>
              @if (field.type === 'fk' && rawSingleId() !== null) {
                @if (targetPerms()?.change) {
                  <button type="button" class="rel-act" (click)="editRaw($event)">{{ t('edit') }}</button>
                } @else if (targetPerms()?.view) {
                  <button type="button" class="rel-act" (click)="viewRaw($event)">{{ t('view') }}</button>
                }
              }
              <button
                type="button"
                class="btn small secondary"
                [disabled]="control.disabled"
                (click)="pickerOpen.set(true)"
              >{{ t('choose') }}</button>
              @if (rawHasValue() && !control.disabled) {
                <button type="button" class="raw-rel-clear" (click)="clearRaw()" [attr.aria-label]="t('clear')">✕</button>
              }
            </div>
            @if (pickerOpen()) {
              <theia-relation-picker-dialog
                [endpoint]="rawEndpoint()"
                [multi]="field.type === 'm2m'"
                [selectedIds]="currentIds()"
                (picked)="onPicked($event)"
                (closed)="pickerOpen.set(false)"
              />
            }
          } @else if (plainRaw()) {
            <!-- Unregistered FK/M2M target: no options endpoint, so a plain id
                 input. M2M takes comma-separated ids. -->
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
              [exclude]="exclude"
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
  /** Option ids to hide from a relation dropdown (passed through to the relation
   *  select) — e.g. values already chosen in sibling inline rows. */
  @Input() exclude: (number | string)[] = [];
  cap = cap;

  private destroyRef = inject(DestroyRef);
  private router = inject(Router);
  private api = inject(ApiService);
  private i18n = inject(I18nService);
  protected t = this.i18n.t;
  /** model_field_select: the model keys currently chosen in the sibling field. */
  selectedKeys = signal<string[]>([]);
  /** Bumped on control value changes so checkbox state re-renders (zoneless). */
  private rev = signal(0);
  /** raw_id picker open state. */
  pickerOpen = signal(false);
  /** Permissions on a raw FK's target — drive its View/Edit shortcut buttons. */
  targetPerms = signal<Perms | undefined>(undefined);

  ngOnInit(): void {
    const widget = this.field.widget;
    // raw_id input shows pk(s) from the control; re-render when the record loads
    // (async setValue) or after a pick — the control isn't a signal (zoneless).
    if ((this.field.type === 'fk' || this.field.type === 'm2m') && this.rawPickable()) {
      this.control.valueChanges
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe(() => this.rev.update((n) => n + 1));
      // Fetch target perms so a raw FK with a value can offer View/Edit shortcuts
      // (same gating as the non-raw relation widget).
      const target = this.field.relation?.target;
      if (target && this.field.relation?.registered !== false) {
        this.api
          .permsFor(target)
          .pipe(takeUntilDestroyed(this.destroyRef))
          .subscribe((perms) => this.targetPerms.set(perms));
      }
    }
    if (widget === 'multiselect' || widget === 'model_field_select') {
      // The form control isn't a signal: re-render checkbox state whenever its
      // value changes (incl. the async record load and toggles).
      this.control.valueChanges
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe(() => this.rev.update((n) => n + 1));
    }
    if (widget === 'model_field_select' && this.field.models_field && this.form) {
      const sibling = this.form.get(this.field.models_field);
      // Only render groups for models still in the registry — a stale key (a
      // model that's been unregistered or lost access) is silently skipped.
      const known = this.field.field_choices ?? {};
      const sync = () =>
        this.selectedKeys.set(
          (Array.isArray(sibling?.value) ? sibling!.value : []).filter((k: string) => k in known),
        );
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

  /** raw_id_fields on a registered target: render a modal table picker. */
  rawPickable(): boolean {
    const r = this.field.relation;
    return !!r && r.raw === true && r.registered !== false;
  }

  /** No options endpoint (unregistered target): fall back to a plain id input. */
  plainRaw(): boolean {
    const r = this.field.relation;
    return !!r && r.registered === false;
  }

  /** Unfiltered list endpoint for the target, so the picker can show *every*
   *  row — including assignments that wouldn't match a dependent filter (e.g. a
   *  Space wrongly linked to a Stock whose House it doesn't belong to). */
  rawEndpoint(): string {
    return `data/${this.field.relation?.target}/`;
  }

  /** The raw input shows the pk(s) themselves — no label lookup for raw fields. */
  rawLabel(): string {
    this.rev(); // track for re-render in zoneless
    const v = this.control.value;
    if (Array.isArray(v)) {
      return v.join(', ');
    }
    return v === null || v === undefined ? '' : String(v);
  }

  /** Current selection as pk array (FK -> single, M2M -> the list), for the modal. */
  currentIds(): (number | string)[] {
    const v = this.control.value;
    if (Array.isArray(v)) {
      return v as (number | string)[];
    }
    return v === null || v === undefined || v === '' ? [] : [v as number | string];
  }

  rawHasValue(): boolean {
    return this.currentIds().length > 0;
  }

  /** The single pk of a raw FK (null for empty or M2M), for View/Edit shortcuts. */
  rawSingleId(): number | string | null {
    this.rev(); // track for re-render in zoneless
    if (this.field.type !== 'fk') {
      return null;
    }
    const ids = this.currentIds();
    return ids.length ? ids[0] : null;
  }

  viewRaw(event: Event): void {
    event.stopPropagation();
    this.navigateToRaw('view');
  }

  editRaw(event: Event): void {
    event.stopPropagation();
    this.navigateToRaw('edit');
  }

  /** Open the related record's page; remember where to return. */
  private navigateToRaw(mode: 'view' | 'edit'): void {
    const id = this.rawSingleId();
    const target = this.field.relation?.target;
    if (id === null || !target) {
      return;
    }
    const queryParams: Record<string, string> = { ret: this.router.url };
    if (mode === 'view') {
      queryParams['mode'] = 'view';
    }
    this.router.navigate(['/', keyToSlug(target), id], { queryParams });
    window.scrollTo({ top: 0 });
  }

  /** Apply a pick from the modal: FK sets the pk, M2M replaces with the full set. */
  onPicked(value: number | string | (number | string)[]): void {
    this.control.setValue(this.field.type === 'm2m' ? (value as unknown[]) : value);
    this.control.markAsDirty();
  }

  clearRaw(): void {
    this.control.setValue(this.field.type === 'm2m' ? [] : null);
    this.control.markAsDirty();
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
