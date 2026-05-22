import { describe, it, expect } from 'vitest';
import { Action } from '@/core/permissions/constants';

describe('Action constants', () => {
  it('includes scorecard permissions', () => {
    expect(Action.SCORECARD_VIEW).toBe('scorecard:view');
    expect(Action.SCORECARD_MANAGE).toBe('scorecard:manage');
  });

  it('includes tracker permissions', () => {
    expect(Action.TRACKER_VIEW).toBe('tracker:view');
    expect(Action.TRACKER_MANAGE).toBe('tracker:manage');
  });

  it('includes capacity permissions', () => {
    expect(Action.CAPACITY_VIEW).toBe('capacity:view');
    expect(Action.CAPACITY_MANAGE).toBe('capacity:manage');
  });

  it('includes accrual permissions', () => {
    expect(Action.ACCRUAL_VIEW).toBe('accrual:view');
    expect(Action.ACCRUAL_MANAGE).toBe('accrual:manage');
    expect(Action.ACCRUAL_PERIOD_MANAGE).toBe('accrual:period_manage');
  });
});
