import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ScoreCard from '../ScoreCard';
import type { FinalScore } from '../../../types';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

function renderWithProviders(component: React.ReactElement): ReturnType<typeof render> {
  return render(
    <QueryClientProvider client={queryClient}>
      {component}
    </QueryClientProvider>
  );
}

describe('ScoreCard', () => {
  const mockScore: FinalScore = {
    score: 73,
    dimensions: {
      p_time: 80,
      p_cost: 75,
      p_quality: 70,
      p_value: 85,
      p_satisfaction: 90,
      p_flow: 65,
      p_engineering: 78,
      p_risk: 82,
    },
    weights_applied: {},
  };

  it('renders overall score', () => {
    renderWithProviders(<ScoreCard score={mockScore} />);

    expect(screen.getByText('73')).toBeDefined();
  });

  it('renders default title', () => {
    renderWithProviders(<ScoreCard score={mockScore} />);

    expect(screen.getByText('Overall Score')).toBeDefined();
  });

  it('renders custom title when provided', () => {
    renderWithProviders(<ScoreCard score={mockScore} title="Project Performance" />);

    expect(screen.getByText('Project Performance')).toBeDefined();
    expect(screen.queryByText('Overall Score')).toBeNull();
  });

  it('renders all dimension scores', () => {
    renderWithProviders(<ScoreCard score={mockScore} />);

    expect(screen.getByText('Time')).toBeDefined();
    expect(screen.getByText('80')).toBeDefined();

    expect(screen.getByText('Cost')).toBeDefined();
    expect(screen.getByText('75')).toBeDefined();

    expect(screen.getByText('Quality')).toBeDefined();
    expect(screen.getByText('70')).toBeDefined();

    expect(screen.getByText('Value')).toBeDefined();
    expect(screen.getByText('85')).toBeDefined();

    expect(screen.getByText('Satisfaction')).toBeDefined();
    expect(screen.getByText('90')).toBeDefined();

    expect(screen.getByText('Flow')).toBeDefined();
    expect(screen.getByText('65')).toBeDefined();

    expect(screen.getByText('Engineering')).toBeDefined();
    expect(screen.getByText('78')).toBeDefined();

    expect(screen.getByText('Risk Mgmt')).toBeDefined();
    expect(screen.getByText('82')).toBeDefined();
  });

  it('applies green dot to high scores (>=80)', () => {
    const highScore: FinalScore = {
      score: 87,
      dimensions: mockScore.dimensions,
      weights_applied: {},
    };

    const { container } = renderWithProviders(<ScoreCard score={highScore} />);

    const scoreElement = screen.getByText('87');
    expect(scoreElement.className).toContain('text-foreground');

    const dotElements = container.querySelectorAll('.bg-aux-neon-grass');
    expect(dotElements.length).toBeGreaterThan(0);

    const bgElements = container.querySelectorAll('[class*="bg-score-green"]');
    expect(bgElements.length).toBeGreaterThan(0);
  });

  it('renders perfect score (100)', () => {
    const perfectScore: FinalScore = {
      score: 100,
      dimensions: {
        p_time: 100,
        p_cost: 100,
        p_quality: 100,
        p_value: 100,
        p_satisfaction: 100,
        p_flow: 100,
        p_engineering: 100,
        p_risk: 100,
      },
      weights_applied: {},
    };

    renderWithProviders(<ScoreCard score={perfectScore} />);

    // Should find exactly 9 instances of "100": 1 overall + 8 dimensions
    const perfectScoreElements = screen.getAllByText('100');
    expect(perfectScoreElements.length).toBe(9);
  });

  it('renders zero score', () => {
    const zeroScore: FinalScore = {
      score: 0,
      dimensions: {
        p_time: 0,
        p_cost: 0,
        p_quality: 0,
        p_value: 0,
        p_satisfaction: 0,
        p_flow: 0,
        p_engineering: 0,
        p_risk: 0,
      },
      weights_applied: {},
    };

    renderWithProviders(<ScoreCard score={zeroScore} />);

    // Should find exactly 9 instances of "0": 1 overall + 8 dimensions
    const zeroElements = screen.getAllByText('0');
    expect(zeroElements.length).toBe(9);
  });

  it('dimension badges show dot color based on score value', () => {
    const mixedScore: FinalScore = {
      score: 51,
      dimensions: {
        p_time: 90,
        p_cost: 70,
        p_quality: 50,
        p_value: 30,
        p_satisfaction: 10,
        p_flow: 80,
        p_engineering: 60,
        p_risk: 40,
      },
      weights_applied: {},
    };

    renderWithProviders(<ScoreCard score={mixedScore} />);

    const timeScore = screen.getByText('90');
    expect(timeScore.className).toContain('text-foreground');
    const timeDot = timeScore.querySelector('.bg-aux-neon-grass');
    expect(timeDot).not.toBeNull(); // >=80 = green dot

    const costScore = screen.getByText('70');
    const costDot = costScore.querySelector('.bg-aux-cool-steel');
    expect(costDot).not.toBeNull(); // >=60 = yellow dot

    const qualityScore = screen.getByText('50');
    const qualityDot = qualityScore.querySelector('.bg-aux-red');
    expect(qualityDot).not.toBeNull(); // <60 = red dot
  });

  it('shows dash for null dimension scores', () => {
    const partialScore: FinalScore = {
      score: 50,
      dimensions: {
        p_time: 80,
        p_cost: null,
        p_quality: 70,
        p_value: null,
        p_satisfaction: 60,
        p_flow: null,
        p_engineering: 50,
        p_risk: null,
      },
      weights_applied: {},
    };

    renderWithProviders(<ScoreCard score={partialScore} />);

    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBe(4);  // 4 null dimensions
  });
});
