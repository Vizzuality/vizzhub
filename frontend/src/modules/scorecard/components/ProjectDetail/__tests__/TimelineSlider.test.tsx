import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeAll } from 'vitest';
import TimelineSlider from '../TimelineSlider';
import type { MetricsWithScores } from '@/modules/scorecard/types';

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

const mockSnapshots = [
  { period_year: 2025, period_month: 10 },
  { period_year: 2025, period_month: 11 },
  { period_year: 2025, period_month: 12 },
] as MetricsWithScores[];

describe('TimelineSlider', () => {
  it('renders all months from start date to now', () => {
    const startDate = '2025-10-01';
    render(
      <TimelineSlider
        projectStartDate={startDate}
        snapshots={mockSnapshots}
        selectedPeriod={null}
        onPeriodChange={vi.fn()}
      />,
    );

    expect(screen.getByText('Oct 2025')).toBeInTheDocument();
  });

  it('calls onPeriodChange when clicking a month', () => {
    const onPeriodChange = vi.fn();
    render(
      <TimelineSlider
        projectStartDate="2025-10-01"
        snapshots={mockSnapshots}
        selectedPeriod={null}
        onPeriodChange={onPeriodChange}
      />,
    );

    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[0]);

    expect(onPeriodChange).toHaveBeenCalledWith({ year: 2025, month: 10 });
  });

  it('shows reset button when period is selected', () => {
    render(
      <TimelineSlider
        projectStartDate="2025-10-01"
        snapshots={mockSnapshots}
        selectedPeriod={{ year: 2025, month: 10 }}
        onPeriodChange={vi.fn()}
      />,
    );

    expect(screen.getByText('Reset to latest')).toBeInTheDocument();
  });

  it('hides reset button when no period selected', () => {
    render(
      <TimelineSlider
        projectStartDate="2025-10-01"
        snapshots={mockSnapshots}
        selectedPeriod={null}
        onPeriodChange={vi.fn()}
      />,
    );

    expect(screen.queryByText('Reset to latest')).not.toBeInTheDocument();
  });

  it('shows pulse animation when capturing', () => {
    const { container } = render(
      <TimelineSlider
        projectStartDate="2025-10-01"
        snapshots={mockSnapshots}
        selectedPeriod={{ year: 2025, month: 10 }}
        onPeriodChange={vi.fn()}
        isCapturing
      />,
    );

    const animatedElement = container.querySelector('.animate-pulse');
    expect(animatedElement).toBeInTheDocument();
  });
});
