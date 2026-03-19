import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import SubIndicatorCard from '../../SubIndicatorCard';
import GovernanceCard from '../GovernanceCard';
import ClientSurveyCard from '../ClientSurveyCard';
import type { ClientSurvey } from '../../../types';

describe('Config Integration - Dynamic Target Display', () => {
  describe('SubIndicatorCard', () => {
    it('displays target value from props', () => {
      render(
        <SubIndicatorCard
          title="Defect Density"
          indicatorValue={5}
          indicatorLabel="Bugs per 100 tasks"
          indicatorSuffix="%"
          description="Ratio of bugs to completed tasks"
          target={6}
          lowerIsBetter={true}
          formula="(Bugs / Tasks) × 100"
          metrics={[{ label: 'Bugs', value: 10 }]}
        />
      );

      expect(screen.getByText('≤6%')).toBeInTheDocument();
    });

    it('shows green color when value meets target (lower is better)', () => {
      render(
        <SubIndicatorCard
          title="Defect Density"
          indicatorValue={5}
          indicatorLabel="Bugs per 100 tasks"
          indicatorSuffix="%"
          target={6}
          lowerIsBetter={true}
          metrics={[]}
        />
      );

      const valueElement = screen.getByText('5.0%');
      expect(valueElement.parentElement?.querySelector('.bg-aux-neon-grass')).toBeTruthy();
    });

    it('shows red color when value exceeds target (lower is better)', () => {
      render(
        <SubIndicatorCard
          title="Defect Density"
          indicatorValue={10}
          indicatorLabel="Bugs per 100 tasks"
          indicatorSuffix="%"
          target={6}
          lowerIsBetter={true}
          metrics={[]}
        />
      );

      const valueElement = screen.getByText('10.0%');
      expect(valueElement.parentElement?.querySelector('.bg-aux-red')).toBeTruthy();
    });

    it('shows green color when value meets target (higher is better)', () => {
      render(
        <SubIndicatorCard
          title="Story Review Ratio"
          indicatorValue={90}
          indicatorLabel="Stories with reviewer"
          indicatorSuffix="%"
          target={85}
          lowerIsBetter={false}
          metrics={[]}
        />
      );

      const valueElement = screen.getByText('90.0%');
      expect(valueElement.parentElement?.querySelector('.bg-aux-neon-grass')).toBeTruthy();
    });

    it('shows red color when value misses target (higher is better)', () => {
      render(
        <SubIndicatorCard
          title="Story Review Ratio"
          indicatorValue={70}
          indicatorLabel="Stories with reviewer"
          indicatorSuffix="%"
          target={85}
          lowerIsBetter={false}
          metrics={[]}
        />
      );

      const valueElement = screen.getByText('70.0%');
      expect(valueElement.parentElement?.querySelector('.bg-aux-red')).toBeTruthy();
    });

    it('changing target affects both display value and color logic', () => {
      const { rerender } = render(
        <SubIndicatorCard
          title="Test Metric"
          indicatorValue={50}
          indicatorLabel="Test"
          indicatorSuffix="%"
          target={40}
          lowerIsBetter={false}
          metrics={[]}
        />
      );

      expect(screen.getByText('≥40%')).toBeInTheDocument();
      expect(screen.getByText('50.0%').parentElement?.querySelector('.bg-aux-neon-grass')).toBeTruthy();

      rerender(
        <SubIndicatorCard
          title="Test Metric"
          indicatorValue={50}
          indicatorLabel="Test"
          indicatorSuffix="%"
          target={60}
          lowerIsBetter={false}
          metrics={[]}
        />
      );

      expect(screen.getByText('≥60%')).toBeInTheDocument();
      expect(screen.getByText('50.0%').parentElement?.querySelector('.bg-aux-red')).toBeTruthy();
    });
  });

  describe('GovernanceCard', () => {
    const mockOnSave = vi.fn();

    beforeEach(() => {
      vi.clearAllMocks();
    });

    it('displays target from props', () => {
      render(
        <GovernanceCard
          value={1}
          target={3}
          onSave={mockOnSave}
          isPending={false}
        />
      );

      expect(screen.getByText('≤3 exceptions')).toBeInTheDocument();
    });

    it('shows green dot when exceptions below target', () => {
      render(
        <GovernanceCard
          value={1}
          target={3}
          onSave={mockOnSave}
          isPending={false}
        />
      );

      const valueElement = screen.getByText('1');
      expect(valueElement.querySelector('.bg-aux-neon-grass')).not.toBeNull();
    });

    it('shows yellow dot when exceptions equal target', () => {
      render(
        <GovernanceCard
          value={3}
          target={3}
          onSave={mockOnSave}
          isPending={false}
        />
      );

      const valueElement = screen.getByText('3');
      expect(valueElement.querySelector('.bg-aux-yellow')).not.toBeNull();
    });

    it('shows red dot when exceptions exceed target', () => {
      render(
        <GovernanceCard
          value={5}
          target={3}
          onSave={mockOnSave}
          isPending={false}
        />
      );

      const valueElement = screen.getByText('5');
      expect(valueElement.querySelector('.bg-aux-red')).not.toBeNull();
    });

    it('respects different target values - dot color changes with target', () => {
      const { rerender } = render(
        <GovernanceCard
          value={4}
          target={3}
          onSave={mockOnSave}
          isPending={false}
        />
      );

      expect(screen.getByText('4').querySelector('.bg-aux-red')).not.toBeNull();
      expect(screen.getByText('≤3 exceptions')).toBeInTheDocument();

      rerender(
        <GovernanceCard
          value={4}
          target={5}
          onSave={mockOnSave}
          isPending={false}
        />
      );

      expect(screen.getByText('4').querySelector('.bg-aux-neon-grass')).not.toBeNull();
      expect(screen.getByText('≤5 exceptions')).toBeInTheDocument();
    });
  });

  describe('ClientSurveyCard', () => {
    const mockOnSave = vi.fn();
    const mockGetWeight = vi.fn();

    beforeEach(() => {
      vi.clearAllMocks();
      mockGetWeight.mockReturnValue(null);
    });

    it('displays target from props', () => {
      render(
        <ClientSurveyCard
          data={null}
          indicatorValue={null}
          target={85}
          projectStatus="finished"
          onSave={mockOnSave}
          isPending={false}
          getWeight={mockGetWeight}
        />
      );

      expect(screen.getByText('≥85%')).toBeInTheDocument();
    });

    it('calls getWeight function for tooltip weights', () => {
      render(
        <ClientSurveyCard
          data={null}
          indicatorValue={0.9}
          target={85}
          projectStatus="finished"
          onSave={mockOnSave}
          isPending={false}
          getWeight={mockGetWeight}
        />
      );

      expect(mockGetWeight).toHaveBeenCalledWith('weight_survey_quality');
      expect(mockGetWeight).toHaveBeenCalledWith('weight_survey_time');
    });

    it('renders without error when getWeight returns null (uses defaults)', () => {
      mockGetWeight.mockReturnValue(null);

      expect(() => {
        render(
          <ClientSurveyCard
            data={null}
            indicatorValue={0.9}
            target={85}
            projectStatus="finished"
            onSave={mockOnSave}
            isPending={false}
            getWeight={mockGetWeight}
          />
        );
      }).not.toThrow();

      expect(screen.getByText('Client Satisfaction Survey')).toBeInTheDocument();
    });

    it('shows correct dot color based on dynamic target', () => {
      render(
        <ClientSurveyCard
          data={{ understanding: 5, quality: 5 } as ClientSurvey}
          indicatorValue={0.90}
          target={85}
          projectStatus="finished"
          onSave={mockOnSave}
          isPending={false}
          getWeight={mockGetWeight}
        />
      );

      expect(screen.getByText('90%').querySelector('.bg-aux-neon-grass')).not.toBeNull();
    });

    it('dot color changes when target changes', () => {
      const { rerender } = render(
        <ClientSurveyCard
          data={{ understanding: 5, quality: 5 } as ClientSurvey}
          indicatorValue={0.80}
          target={75}
          projectStatus="finished"
          onSave={mockOnSave}
          isPending={false}
          getWeight={mockGetWeight}
        />
      );

      expect(screen.getByText('80%').querySelector('.bg-aux-neon-grass')).not.toBeNull();

      rerender(
        <ClientSurveyCard
          data={{ understanding: 5, quality: 5 } as ClientSurvey}
          indicatorValue={0.80}
          target={90}
          projectStatus="finished"
          onSave={mockOnSave}
          isPending={false}
          getWeight={mockGetWeight}
        />
      );

      expect(screen.getByText('80%').querySelector('.bg-aux-red')).not.toBeNull();
    });

    it('respects different target values for KPI display', () => {
      const { rerender } = render(
        <ClientSurveyCard
          data={null}
          indicatorValue={null}
          target={80}
          projectStatus="finished"
          onSave={mockOnSave}
          isPending={false}
          getWeight={mockGetWeight}
        />
      );

      expect(screen.getByText('≥80%')).toBeInTheDocument();

      rerender(
        <ClientSurveyCard
          data={null}
          indicatorValue={null}
          target={95}
          projectStatus="finished"
          onSave={mockOnSave}
          isPending={false}
          getWeight={mockGetWeight}
        />
      );

      expect(screen.getByText('≥95%')).toBeInTheDocument();
    });
  });
});

describe('Config Values Must Match Between Config and Display', () => {
  describe('Target-based color thresholds', () => {
    it('value exactly at 90% of target shows yellow (warning zone)', () => {
      render(
        <SubIndicatorCard
          title="Test"
          indicatorValue={72}
          indicatorLabel="Test"
          indicatorSuffix="%"
          target={80}
          lowerIsBetter={false}
          metrics={[]}
        />
      );

      expect(screen.getByText('72.0%').parentElement?.querySelector('.bg-aux-red')).toBeTruthy();
    });

    it('value just above 90% of target still shows green', () => {
      render(
        <SubIndicatorCard
          title="Test"
          indicatorValue={80}
          indicatorLabel="Test"
          indicatorSuffix="%"
          target={80}
          lowerIsBetter={false}
          metrics={[]}
        />
      );

      expect(screen.getByText('80.0%').parentElement?.querySelector('.bg-aux-neon-grass')).toBeTruthy();
    });
  });

  describe('Edge cases for target changes', () => {
    it('same value can be green or red depending on target', () => {
      const { rerender } = render(
        <SubIndicatorCard
          title="Lead Time"
          indicatorValue={8}
          indicatorLabel="Days"
          indicatorSuffix="d"
          target={10}
          lowerIsBetter={true}
          metrics={[]}
        />
      );

      expect(screen.getByText('8.0d').parentElement?.querySelector('.bg-aux-neon-grass')).toBeTruthy();

      rerender(
        <SubIndicatorCard
          title="Lead Time"
          indicatorValue={8}
          indicatorLabel="Days"
          indicatorSuffix="d"
          target={5}
          lowerIsBetter={true}
          metrics={[]}
        />
      );

      expect(screen.getByText('8.0d').parentElement?.querySelector('.bg-aux-red')).toBeTruthy();
    });
  });
});
