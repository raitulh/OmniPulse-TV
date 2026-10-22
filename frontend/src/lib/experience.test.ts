import { describe, expect, it } from 'vitest';
import { intentFromCommand, recommendMode } from './experience';

describe('recommendMode', () => {
  it('uses saved advanced preference to suggest analyst mode', () => {
    expect(recommendMode({ default_mode: 'analyst', detail_level: 'advanced' }).mode).toBe('analyst');
  });
  it('respects simple detail level when scores tie', () => {
    expect(recommendMode({ default_mode: 'family', detail_level: 'simple' }).mode).toBe('family');
  });
  it('uses catch-up mode when strict spoilers outweigh family mode', () => {
    expect(recommendMode({ default_mode: 'family', spoiler_policy: 'strict' }).mode).toBe('family');
    expect(recommendMode({ default_mode: 'catch_up', spoiler_policy: 'strict' }).mode).toBe('catch_up');
  });
  it('falls back to family on invalid saved values', () => {
    expect(recommendMode({ default_mode: 'invalid' }).mode).toBe('family');
  });
});

describe('intentFromCommand', () => {
  it('recognizes recap requests', () => expect(intentFromCommand('What did I miss?')).toBe('catch_up'));
  it('recognizes tactical analysis', () => expect(intentFromCommand('Break down this play')).toBe('break_down_play'));
  it('falls back to help for unsupported commands', () => expect(intentFromCommand('change my television volume')).toBe('help'));
});
