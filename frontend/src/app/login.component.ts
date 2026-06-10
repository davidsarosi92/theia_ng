import { Component, inject, output, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';

import { ApiService } from './api.service';
import { AuthState } from './models';
import { getConfig } from './theia-config';

@Component({
  selector: 'theia-login',
  standalone: true,
  imports: [ReactiveFormsModule],
  template: `
    <div class="login-wrap">
      <form class="login-card" [formGroup]="form" (ngSubmit)="submit()">
        <h1>{{ title }}</h1>
        <label class="field">
          <span class="field-label">Username</span>
          <input type="text" formControlName="username" autocomplete="username" />
        </label>
        <label class="field">
          <span class="field-label">Password</span>
          <input type="password" formControlName="password" autocomplete="current-password" />
        </label>
        @if (error()) {
          <div class="errors">{{ error() }}</div>
        }
        <button type="submit" class="btn" [disabled]="form.invalid || busy()">
          {{ busy() ? 'Signing in…' : 'Sign in' }}
        </button>
      </form>
    </div>
  `,
})
export class LoginComponent {
  private api = inject(ApiService);
  title = getConfig().siteTitle;
  loggedIn = output<AuthState>();

  busy = signal(false);
  error = signal<string | null>(null);
  form = new FormGroup({
    username: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    password: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
  });

  submit(): void {
    this.busy.set(true);
    this.error.set(null);
    const { username, password } = this.form.getRawValue();
    this.api.login(username, password).subscribe({
      next: (state) => {
        this.busy.set(false);
        if (state.can_access) {
          this.loggedIn.emit(state);
        } else {
          this.error.set('Signed in, but this account cannot access the admin.');
        }
      },
      error: (err) => {
        this.busy.set(false);
        this.error.set(err?.error?.detail ?? 'Sign in failed.');
      },
    });
  }
}
