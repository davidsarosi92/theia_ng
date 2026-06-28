import { describe, expect, it } from 'vitest';

import { actionResultError } from './util';

describe('actionResultError', () => {
  it('reads the error wrapped under result (the ActionView envelope)', () => {
    expect(actionResultError({ detail: 'ok', result: { error: 'too short' } })).toBe('too short');
  });

  it('falls back to a top-level error', () => {
    expect(actionResultError({ error: 'nope' })).toBe('nope');
  });

  it('returns null for a successful result', () => {
    expect(actionResultError({ detail: 'ok', result: { password_set_for: 'x@y.z' } })).toBeNull();
    expect(actionResultError({ detail: 'ok', result: null })).toBeNull();
    expect(actionResultError(null)).toBeNull();
  });
});
