import { type CSSProperties, type ReactNode } from "react";
import { Link } from "react-router-dom";

type AuthShellProps = {
  title: string;
  subtitle: string;
  footerText: string;
  footerLinkText: string;
  footerLinkTo: string;
  children: ReactNode;
};

export function AuthShell({
  title,
  subtitle,
  footerText,
  footerLinkText,
  footerLinkTo,
  children,
}: AuthShellProps) {
  return (
    <main className="auth-shell">
      <div className="auth-glow auth-glow-violet" aria-hidden="true" />
      <div className="auth-glow auth-glow-cyan" aria-hidden="true" />

      <div className="auth-layout">
        <section className="auth-story">
          <Link to="/" className="auth-brand" aria-label="MOM home">
            <span className="auth-brand-mark" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
            <span>MOM<span className="auth-brand-period">.</span></span>
          </Link>

          <div className="auth-story-content">
            <div className="auth-eyebrow"><span className="auth-live-dot" /> YOUR MEETINGS, IN FOCUS</div>
            <h1>Make every<br />conversation <span>count.</span></h1>
            <p className="auth-story-copy">
              One calm space for the ideas, decisions, and next steps that move your work forward.
            </p>

            <div className="auth-visual" aria-hidden="true">
              <div className="auth-visual-orbit auth-orbit-one" />
              <div className="auth-visual-orbit auth-orbit-two" />
              <div className="auth-visual-core">
                <div className="auth-waveform">
                  {[18, 30, 22, 42, 27, 52, 34, 62, 40, 27, 47, 33, 20, 38, 24, 15].map((height, index) => (
                  <span key={index} style={{ "--bar-height": `${height}px`, "--bar-index": index } as CSSProperties} />
                  ))}
                </div>
                <span className="auth-core-caption">IN THE MOMENT</span>
              </div>
              <div className="auth-float-card auth-float-top">
                <span className="auth-float-icon">✦</span>
                <span><strong>Key ideas</strong><small>Captured as they happen</small></span>
              </div>
              <div className="auth-float-card auth-float-bottom">
                <span className="auth-float-check">✓</span>
                <span><strong>Next steps</strong><small>Ready when you are</small></span>
              </div>
              <div className="auth-visual-star auth-star-one">✳</div>
              <div className="auth-visual-star auth-star-two">✦</div>
            </div>
          </div>

          <div className="auth-story-footer">
            <span>MEETING OPERATING MEMORY</span>
            <span className="auth-footer-separator" />
            <span>THOUGHTFULLY IN SYNC</span>
          </div>
        </section>

        <section className="auth-form-panel">
          <div className="auth-mobile-brand">
            <Link to="/" className="auth-brand" aria-label="MOM home">
              <span className="auth-brand-mark" aria-hidden="true"><span /><span /><span /></span>
              <span>MOM<span className="auth-brand-period">.</span></span>
            </Link>
          </div>
          <div className="auth-card">
            <div className="auth-form-heading">
              <span className="auth-form-kicker">WELCOME TO MOM</span>
              <h2>{title}</h2>
              <p>{subtitle}</p>
            </div>
            <div className="auth-content">{children}</div>
            <p className="auth-switch">
              {footerText}{" "}
              <Link to={footerLinkTo}>{footerLinkText}<span aria-hidden="true"> ↗</span></Link>
            </p>
            <div className="auth-secure-note"><span aria-hidden="true">◈</span> YOUR WORKSPACE, YOURS ALONE</div>
          </div>
          <div className="auth-panel-footer">© {new Date().getFullYear()} MOM <span>·</span> Make space for what matters.</div>
        </section>
      </div>
    </main>
  );
}
