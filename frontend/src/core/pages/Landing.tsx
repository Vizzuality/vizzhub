import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/core/hooks/useAuth';
import { useActiveProjectSummaries } from '@/core/hooks/useProjects';
import { useProjectScoresMap } from '@/modules/scorecard/hooks/useProjectScoresMap';
import './Landing.css';

interface ModuleCard {
  number: string;
  symbol: string;
  label: string;
  path: string;
  iconType: 'tracker' | 'scorecard' | 'iso' | 'playbook' | 'admin';
  adminOnly?: boolean;
}

const MODULES: ModuleCard[] = [
  {
    number: '01',
    symbol: 'Tr',
    label: 'TRACKER',
    path: '/projects',
    iconType: 'tracker',
  },
  {
    number: '02',
    symbol: 'Sc',
    label: 'SCORECARD',
    path: '/scorecard',
    iconType: 'scorecard',
  },
  {
    number: '03',
    symbol: 'Is',
    label: 'ISO_CORE',
    path: '/iso/snapshots',
    iconType: 'iso',
    adminOnly: true,
  },
  {
    number: '04',
    symbol: 'Pb',
    label: 'PLAYBOOK',
    path: '/tracker/how-to-report',
    iconType: 'playbook',
  },
  {
    number: '05',
    symbol: 'Ad',
    label: 'ADMIN',
    path: '/admin',
    iconType: 'admin',
    adminOnly: true,
  },
];

function getScoreCssVar(score: number | null): string {
  if (score === null) return 'var(--muted-foreground)';
  if (score >= 70) return 'var(--lnd-green)';
  if (score >= 40) return 'var(--aux-yellow)';
  return 'var(--aux-red)';
}

function CardIcon({ type }: { type: ModuleCard['iconType'] }): JSX.Element {
  if (type === 'scorecard') {
    return (
      <span className="landing__card-icon landing__icon-scorecard">
        {Array.from({ length: 9 }).map((_, i) => (
          <span key={i} />
        ))}
      </span>
    );
  }
  const classMap = {
    tracker: 'landing__icon-tracker',
    iso: 'landing__icon-iso',
    playbook: 'landing__icon-playbook',
    admin: 'landing__icon-admin',
  };
  return <span className={`landing__card-icon ${classMap[type]}`} />;
}

function TopScores(): JSX.Element | null {
  const navigate = useNavigate();
  const { data: projects, isLoading: projectsLoading } = useActiveProjectSummaries();
  const { scoresMap, isLoading: scoresLoading } = useProjectScoresMap(projects);

  if (projectsLoading || scoresLoading) return null;
  if (!projects || projects.length === 0) return null;

  const top5 = [...projects]
    .filter((p) => scoresMap[p.id] !== null)
    .sort((a, b) => (scoresMap[b.id] ?? 0) - (scoresMap[a.id] ?? 0))
    .slice(0, 5);

  if (top5.length === 0) return null;

  const maxScore = scoresMap[top5[0].id] ?? 100;

  return (
    <div className="landing__card landing__card--scores">
      <span className="landing__card-number">06</span>
      <span className="landing__card-label">TOP_SCORES</span>
      <div className="landing__top5-list">
        {top5.map((p, i) => {
          const score = scoresMap[p.id] ?? 0;
          const color = getScoreCssVar(score);
          const barWidth = maxScore > 0 ? (score / maxScore) * 100 : 0;
          return (
            <div
              key={p.id}
              className="landing__top5-row"
              onClick={() => navigate(`/scorecard/${p.id}`)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') navigate(`/scorecard/${p.id}`);
              }}
            >
              <span className="landing__top5-rank">{String(i + 1).padStart(2, '0')}</span>
              <span className="landing__top5-name">{p.name}</span>
              <div className="landing__top5-bar-track">
                <div
                  className="landing__top5-bar-fill"
                  style={{ width: `${barWidth}%`, backgroundColor: color }}
                />
              </div>
              <span className="landing__top5-score" style={{ color }}>
                {Math.round(score)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function Landing(): JSX.Element {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  return (
    <div className="landing">
      <header className="landing__header">
        <div className="landing__header-row">
          <h1 className="landing__title">Vizzhub</h1>
          <button
            className="landing__cta"
            onClick={() => navigate('/tracker/my-report')}
            type="button"
          >
            Submit your report
          </button>
        </div>
        <p className="landing__subtitle">
          Project hub. Track budgets, measure performance, and manage compliance
          across all active projects. Select a module to get started.
        </p>
      </header>

      <div className="landing__grid">
        {MODULES.map((mod) => {
          const disabled = mod.adminOnly && !isAdmin;
          return (
          <div
            key={mod.number}
            className={`landing__card${disabled ? ' landing__card--disabled' : ''}`}
            onClick={() => !disabled && navigate(mod.path)}
            role="button"
            tabIndex={disabled ? -1 : 0}
            onKeyDown={(e) => {
              if (!disabled && (e.key === 'Enter' || e.key === ' ')) navigate(mod.path);
            }}
          >
            <span className="landing__card-number">{mod.number}</span>
            <CardIcon type={mod.iconType} />
            <span className="landing__card-symbol">{mod.symbol}</span>
            <span className="landing__card-label">{mod.label}</span>
          </div>
          );
        })}
        <TopScores />
      </div>
    </div>
  );
}
