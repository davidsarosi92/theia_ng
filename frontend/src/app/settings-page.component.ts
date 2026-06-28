import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { BrandService } from './brand.service';
import { I18nService } from './i18n.service';
import { SiteConfigPayload, ThemePref } from './models';
import { SettingsService } from './settings.service';
import { ToastService } from './toast.service';

/** The Settings page: per-user preferences (language/theme/timezone, moved here
 *  from the topbar) plus, for superusers, admin overrides of the settings.py
 *  THEIA_NG deploy config (with a reset to defaults) and a schema-cache flush. */
@Component({
  selector: 'theia-settings-page',
  standalone: true,
  imports: [RouterLink, FormsModule],
  template: `
    <nav class="breadcrumb">
      <a routerLink="/">{{ t('home') }}</a>
      <span class="sep">/</span>
      <span>{{ t('settings') }}</span>
    </nav>

    <header class="list-header"><h2>{{ t('settings') }}</h2></header>

    <!-- per-user preferences -->
    <section class="settings-card">
      <h3 class="settings-title">{{ t('preferences') }}</h3>
      <label class="field">
        <span class="field-label">{{ t('language') }}</span>
        <select [ngModel]="settings.language()" (ngModelChange)="settings.setLanguage($event)">
          @for (l of settings.availableLanguages(); track l.code) {
            <option [value]="l.code">{{ l.label }}</option>
          }
        </select>
      </label>
      <label class="field">
        <span class="field-label">{{ t('theme') }}</span>
        <select [ngModel]="settings.theme()" (ngModelChange)="onTheme($event)">
          <option value="auto">{{ t('themeAuto') }}</option>
          <option value="light">{{ t('themeLight') }}</option>
          <option value="dark">{{ t('themeDark') }}</option>
        </select>
      </label>
      <label class="field">
        <span class="field-label">{{ t('buttonStyle') }}</span>
        <select [ngModel]="settings.buttonStyle()" (ngModelChange)="settings.setButtonStyle($event)">
          <option value="label">{{ t('buttonStyleLabel') }}</option>
          <option value="icon">{{ t('buttonStyleIcon') }}</option>
          <option value="both">{{ t('buttonStyleBoth') }}</option>
        </select>
      </label>
      <label class="field">
        <span class="field-label">{{ t('timezoneLabel') }}</span>
        <input
          type="text"
          [ngModel]="settings.timezone()"
          (ngModelChange)="tzDraft.set($event)"
          (blur)="saveTz()"
        />
      </label>
    </section>

    <!-- self-service: change own password -->
    <section class="settings-card">
      <h3 class="settings-title">{{ t('changePassword') }}</h3>
      <label class="field">
        <span class="field-label">{{ t('currentPassword') }}</span>
        <input type="password" autocomplete="current-password"
               [ngModel]="pwCurrent()" (ngModelChange)="pwCurrent.set($event)" />
      </label>
      <label class="field">
        <span class="field-label">{{ t('newPassword') }}</span>
        <input type="password" autocomplete="new-password"
               [ngModel]="pwNew()" (ngModelChange)="pwNew.set($event)" />
      </label>
      <label class="field">
        <span class="field-label">{{ t('confirmPassword') }}</span>
        <input type="password" autocomplete="new-password"
               [ngModel]="pwConfirm()" (ngModelChange)="pwConfirm.set($event)" />
      </label>
      <div class="actions">
        <button type="button" class="btn" [disabled]="pwSaving()" (click)="changePassword()">
          {{ t('changePassword') }}
        </button>
      </div>
    </section>

    @if (isSuperuser()) {
      @if (cfg(); as c) {
        <!-- admin: override settings.py THEIA_NG -->
        <section class="settings-card">
          <h3 class="settings-title">{{ t('siteSettings') }}</h3>
          <label class="field">
            <span class="field-label">{{ t('siteTitleLabel') }}</span>
            <input type="text" [ngModel]="siteTitle()" (ngModelChange)="siteTitle.set($event)"
                   [placeholder]="c.defaults.site_title" />
            <small class="help">{{ t('defaultHint', { value: c.defaults.site_title }) }}</small>
          </label>
          <label class="field">
            <span class="field-label">{{ t('logoUrlLabel') }}</span>
            <input type="text" [ngModel]="logoUrl()" (ngModelChange)="logoUrl.set($event)"
                   [placeholder]="c.defaults.logo_url || '—'" />
            <small class="help">{{ t('defaultHint', { value: c.defaults.logo_url || '—' }) }}</small>
          </label>
          <label class="field">
            <span class="field-label">{{ t('schemaTtlLabel') }}</span>
            <input type="number" min="0" [ngModel]="schemaTtl()" (ngModelChange)="schemaTtl.set($event)"
                   [placeholder]="c.defaults.schema_ttl" />
            <small class="help">{{ t('defaultHint', { value: c.defaults.schema_ttl }) }}</small>
          </label>
          <label class="field">
            <span class="field-label">{{ t('cacheVersionLabel') }}</span>
            <input type="text" [ngModel]="cacheVersion()" (ngModelChange)="cacheVersion.set($event)"
                   [placeholder]="c.defaults.cache_version" />
            <small class="help">{{ t('defaultHint', { value: c.defaults.cache_version } ) }}</small>
          </label>
          <div class="actions">
            <button type="button" class="btn" [disabled]="saving()" (click)="saveSite()">{{ t('save') }}</button>
            <button type="button" class="btn secondary" [disabled]="saving()" (click)="resetSite()">{{ t('resetToDefaults') }}</button>
          </div>
        </section>

        <!-- admin: maintenance -->
        <section class="settings-card">
          <h3 class="settings-title">{{ t('maintenance') }}</h3>
          <button type="button" class="btn secondary" [disabled]="clearing()" (click)="clearCache()">
            ↻ {{ t('clearCache') }}
          </button>
        </section>
      }
    }
  `,
})
export class SettingsPageComponent implements OnInit {
  private api = inject(ApiService);
  protected settings = inject(SettingsService);
  private i18n = inject(I18nService);
  private toast = inject(ToastService);
  private brand = inject(BrandService);
  protected t = this.i18n.t;

  isSuperuser = signal(false);
  cfg = signal<SiteConfigPayload | null>(null);
  saving = signal(false);
  clearing = signal(false);
  tzDraft = signal<string>('');

  // self-service password change
  pwCurrent = signal('');
  pwNew = signal('');
  pwConfirm = signal('');
  pwSaving = signal(false);

  // site-config edit fields (override values; empty = use the settings.py default)
  siteTitle = signal('');
  logoUrl = signal('');
  schemaTtl = signal<number | string | null>(null);
  cacheVersion = signal('');

  ngOnInit(): void {
    this.api.me().subscribe((state) => {
      this.isSuperuser.set(!!state.is_superuser);
      if (state.is_superuser) {
        this.api.getSiteConfig().subscribe((c) => this.applyCfg(c));
      }
    });
  }

  private applyCfg(c: SiteConfigPayload): void {
    this.cfg.set(c);
    this.siteTitle.set(c.overrides.site_title);
    this.logoUrl.set(c.overrides.logo_url);
    this.schemaTtl.set(c.overrides.schema_ttl);
    this.cacheVersion.set(c.overrides.cache_version);
    // Push the effective brand to the topbar so it updates live (save + reset).
    this.brand.set(c.effective.site_title, c.effective.logo_url);
  }

  onTheme(theme: string): void {
    this.settings.setTheme(theme as ThemePref);
  }

  saveTz(): void {
    const tz = this.tzDraft().trim();
    if (tz && tz !== this.settings.timezone()) {
      this.settings.setTimezone(tz);
    }
  }

  saveSite(): void {
    this.saving.set(true);
    const ttl = this.schemaTtl();
    this.api
      .saveSiteConfig({
        site_title: this.siteTitle(),
        logo_url: this.logoUrl(),
        cache_version: this.cacheVersion(),
        schema_ttl: ttl === '' || ttl === null ? null : Number(ttl),
      })
      .subscribe({
        next: (c) => {
          this.saving.set(false);
          this.applyCfg(c);
          this.toast.success(this.t('saved'));
        },
        error: () => {
          this.saving.set(false);
          this.toast.error(this.t('couldNotSave'));
        },
      });
  }

  resetSite(): void {
    this.saving.set(true);
    this.api.resetSiteConfig().subscribe({
      next: (c) => {
        this.saving.set(false);
        this.applyCfg(c);
        this.toast.success(this.t('saved'));
      },
      error: () => {
        this.saving.set(false);
        this.toast.error(this.t('couldNotSave'));
      },
    });
  }

  changePassword(): void {
    const current = this.pwCurrent();
    const next = this.pwNew();
    if (!current || !next) {
      this.toast.error(this.t('passwordRequired'));
      return;
    }
    if (next !== this.pwConfirm()) {
      this.toast.error(this.t('passwordMismatch'));
      return;
    }
    this.pwSaving.set(true);
    this.api.changePassword(current, next).subscribe({
      next: () => {
        this.pwSaving.set(false);
        this.pwCurrent.set('');
        this.pwNew.set('');
        this.pwConfirm.set('');
        this.toast.success(this.t('passwordChanged'));
      },
      error: (err) => {
        this.pwSaving.set(false);
        this.toast.error(err?.error?.detail || this.t('actionFailed'));
      },
    });
  }

  clearCache(): void {
    this.clearing.set(true);
    this.api.clearSchemaCache().subscribe({
      next: () => {
        this.clearing.set(false);
        this.toast.success(this.t('cacheCleared'));
      },
      error: () => {
        this.clearing.set(false);
        this.toast.error(this.t('actionFailed'));
      },
    });
  }
}
