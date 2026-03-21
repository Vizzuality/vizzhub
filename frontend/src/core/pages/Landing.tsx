import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/core/hooks/useAuth';
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

export default function Landing(): JSX.Element {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.is_admin ?? false;

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
          Centralized command interface for project management systems.
          High-fidelity data access protocol initiated. Select a node to begin
          sequence.
        </p>
      </header>

      <div className="landing__grid">
        {MODULES.map((mod) => (
          <div
            key={mod.number}
            className="landing__card"
            onClick={() => navigate(mod.path)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') navigate(mod.path);
            }}
          >
            <span className="landing__card-number">{mod.number}</span>
            <CardIcon type={mod.iconType} />
            <span className="landing__card-symbol">{mod.symbol}</span>
            <span className="landing__card-label">{mod.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
