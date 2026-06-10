import { describe, expect, it } from 'vitest';

import { inputTypeFor, widgetFor } from './field-widgets';

describe('widgetFor', () => {
  it('maps relations to the relation widget', () => {
    expect(widgetFor('fk')).toBe('relation');
    expect(widgetFor('m2m')).toBe('relation');
  });

  it('maps text/json to textarea, boolean to checkbox, choice to select', () => {
    expect(widgetFor('text')).toBe('textarea');
    expect(widgetFor('json')).toBe('textarea');
    expect(widgetFor('boolean')).toBe('checkbox');
    expect(widgetFor('choice')).toBe('select');
  });

  it('falls back to a plain input', () => {
    expect(widgetFor('string')).toBe('input');
    expect(widgetFor('uuid')).toBe('input');
  });
});

describe('inputTypeFor', () => {
  it('maps numeric and temporal types to native input types', () => {
    expect(inputTypeFor('integer')).toBe('number');
    expect(inputTypeFor('decimal')).toBe('number');
    expect(inputTypeFor('date')).toBe('date');
    expect(inputTypeFor('datetime')).toBe('datetime-local');
    expect(inputTypeFor('time')).toBe('time');
  });

  it('maps email/url and defaults to text', () => {
    expect(inputTypeFor('email')).toBe('email');
    expect(inputTypeFor('url')).toBe('url');
    expect(inputTypeFor('string')).toBe('text');
  });
});
