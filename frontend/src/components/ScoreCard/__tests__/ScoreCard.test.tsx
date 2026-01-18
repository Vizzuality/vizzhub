import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ScoreCard from '../ScoreCard';
import type { FinalScore } from '../../../types';

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
    render(<ScoreCard score={mockScore} />);

    expect(screen.getByText('73')).toBeDefined();
  });

  it('renders default title', () => {
    render(<ScoreCard score={mockScore} />);

    expect(screen.getByText('Overall Score')).toBeDefined();
  });

  it('renders custom title when provided', () => {
    render(<ScoreCard score={mockScore} title="Project Performance" />);

    expect(screen.getByText('Project Performance')).toBeDefined();
    expect(screen.queryByText('Overall Score')).toBeNull();
  });

  it('renders all dimension scores', () => {
    render(<ScoreCard score={mockScore} />);

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

    expect(screen.getByText('Risk')).toBeDefined();
    expect(screen.getByText('82')).toBeDefined();
  });

  it('applies excellent color for score >= 80', () => {
    const excellentScore: FinalScore = {
      score: 87,
      dimensions: mockScore.dimensions,
      weights_applied: {},
    };

    const { container } = render(<ScoreCard score={excellentScore} />);

    const scoreElement = screen.getByText('87');
    expect(scoreElement.className).toContain('text-score-excellent');

    const bgElement = container.querySelector('.bg-score-excellent');
    expect(bgElement).toBeDefined();
  });

  it('applies good color for score between 60-79', () => {
    const goodScore: FinalScore = {
      score: 72,
      dimensions: mockScore.dimensions,
      weights_applied: {},
    };

    const { container } = render(<ScoreCard score={goodScore} />);

    const scoreElement = screen.getByText('72');
    expect(scoreElement.className).toContain('text-score-good');

    const bgElement = container.querySelector('.bg-score-good');
    expect(bgElement).toBeDefined();
  });

  it('applies average color for score between 40-59', () => {
    const averageScore: FinalScore = {
      score: 50,
      dimensions: mockScore.dimensions,
      weights_applied: {},
    };

    const { container } = render(<ScoreCard score={averageScore} />);

    const scoreElement = screen.getByText('50');
    expect(scoreElement.className).toContain('text-score-average');

    const bgElement = container.querySelector('.bg-score-average');
    expect(bgElement).toBeDefined();
  });

  it('applies poor color for score between 20-39', () => {
    const poorScore: FinalScore = {
      score: 30,
      dimensions: mockScore.dimensions,
      weights_applied: {},
    };

    const { container } = render(<ScoreCard score={poorScore} />);

    const scoreElement = screen.getByText('30');
    expect(scoreElement.className).toContain('text-score-poor');

    const bgElement = container.querySelector('.bg-score-poor');
    expect(bgElement).toBeDefined();
  });

  it('applies critical color for score < 20', () => {
    const criticalScore: FinalScore = {
      score: 15,
      dimensions: mockScore.dimensions,
      weights_applied: {},
    };

    const { container } = render(<ScoreCard score={criticalScore} />);

    const scoreElement = screen.getByText('15');
    expect(scoreElement.className).toContain('text-score-critical');

    const bgElement = container.querySelector('.bg-score-critical');
    expect(bgElement).toBeDefined();
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

    render(<ScoreCard score={perfectScore} />);

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

    render(<ScoreCard score={zeroScore} />);

    // Should find exactly 9 instances of "0": 1 overall + 8 dimensions
    const zeroElements = screen.getAllByText('0');
    expect(zeroElements.length).toBe(9);
  });

  it('dimension badges show correct colors', () => {
    const mixedScore: FinalScore = {
      score: 51, // Changed to avoid duplicate with p_quality
      dimensions: {
        p_time: 90, // excellent
        p_cost: 70, // good
        p_quality: 50, // average
        p_value: 30, // poor
        p_satisfaction: 10, // critical
        p_flow: 80, // excellent
        p_engineering: 60, // good
        p_risk: 40, // average
      },
      weights_applied: {},
    };

    render(<ScoreCard score={mixedScore} />);

    const timeScore = screen.getByText('90');
    expect(timeScore.className).toContain('text-score-excellent');

    const costScore = screen.getByText('70');
    expect(costScore.className).toContain('text-score-good');

    const qualityScore = screen.getByText('50');
    expect(qualityScore.className).toContain('text-score-average');

    const valueScore = screen.getByText('30');
    expect(valueScore.className).toContain('text-score-poor');

    const satisfactionScore = screen.getByText('10');
    expect(satisfactionScore.className).toContain('text-score-critical');
  });
});
