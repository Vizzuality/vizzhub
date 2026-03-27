import { useNavigate, useLocation } from 'react-router-dom';
import './NotFound.css';

export default function NotFound(): JSX.Element {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className="notfound">
      <div className="notfound__grid" />
      <span className="notfound__coord notfound__coord--tl">00:00:00</span>
      <span className="notfound__coord notfound__coord--br">ERR_UNRESOLVED</span>

      <div className="notfound__card">
        <span className="notfound__number">404</span>
        <span className="notfound__mass">??.???</span>
        <span className="notfound__symbol">Nf</span>
        <span className="notfound__label">NOT_FOUND</span>
      </div>

      <div className="notfound__readout">
        <p className="notfound__message">
          This element doesn&apos;t exist in the Vizzhub catalog.
        </p>
        <span className="notfound__path">
          {location.pathname}
        </span>
      </div>

      <button
        className="notfound__cta"
        onClick={() => navigate('/')}
        type="button"
      >
        Return to catalog
      </button>
    </div>
  );
}
