import React, {type CSSProperties, type ReactNode, useEffect, useState} from 'react';
import Head from '@docusaurus/Head';
import Link from '@docusaurus/Link';
import clsx from 'clsx';

import styles from './index.module.css';

const DOCS = '/getting-started/getting-started-overview';
const INSTALL = '/getting-started/getting-started-installation';
const QUICKSTART = '/getting-started/getting-started-quickstart';
const WIZARD = '/integrations/integrations-wizard';
const PROVIDERS = '/reference/reference-providers-catalog';
const GITHUB = 'https://github.com/stimm-ai/stimm';

const TAGLINE = 'Optimistic VUI runtime on top of LiveKit Agents';
const DESCRIPTION =
  'Stimm is an Optimistic VUI runtime on top of LiveKit Agents. A low-latency VoiceAgent holds ' +
  'the live turn while a high-capability Supervisor reasons, plans and calls tools in parallel.';

type Segment = {
  flex: number;
  background: string;
  border?: string;
  label?: string;
  color?: string;
  duration: string;
  delay: string;
};

/** Illustrative time-to-first-audio trace: a single-agent pipeline. */
const CLASSIC_TRACE: Segment[] = [
  {flex: 12, background: 'var(--lp-seg-a)', duration: '.5s', delay: '0s'},
  {flex: 48, background: 'var(--lp-seg-b)', label: 'STT', color: 'var(--lp-seg-label)', duration: '.5s', delay: '.18s'},
  {flex: 95, background: 'var(--lp-seg-c)', label: 'LLM + tools', color: 'var(--lp-seg-label-strong)', duration: '.6s', delay: '.36s'},
  {flex: 36, background: 'var(--lp-seg-b)', label: 'TTS', color: 'var(--lp-seg-label)', duration: '.5s', delay: '.62s'},
];

/** The same turn under stimm: speech starts before the supervisor is done. */
const STIMM_TRACE: Segment[] = [
  {flex: 12, background: 'var(--lp-accent-wash)', duration: '.4s', delay: '.1s'},
  {flex: 18, background: 'var(--lp-accent-mid)', duration: '.4s', delay: '.24s'},
  // The moment the first word lands keeps the brand lime as a solid fill.
  {flex: 6, background: 'var(--sg-lime)', duration: '.4s', delay: '.38s'},
  {
    flex: 155,
    background: 'var(--lp-cyan-fill)',
    border: '1px dashed var(--lp-cyan-dash)',
    label: 'supervisor keeps reasoning →',
    color: 'var(--stimm-cyan)',
    duration: '.7s',
    delay: '.5s',
  },
];

const STATS = [
  {value: '6×', label: 'faster acknowledgement'},
  {value: '2', label: 'cooperating agents'},
  {value: '4', label: 'buffering levels'},
];

const PRINCIPLES = [
  {
    index: '01',
    title: 'Acknowledge early',
    body: 'The turn is claimed the moment intent is clear — no dead air while tools resolve.',
  },
  {
    index: '02',
    title: 'Speak early, progressively',
    body: 'Tokens stream to TTS under a buffering policy you choose: none, word, 4-words, punctuation.',
  },
  {
    index: '03',
    title: 'Keep reasoning in parallel',
    body: 'The supervisor plans, calls tools and safely steers the next turn — never blocking this one.',
    cyan: true,
  },
];

const BUFFERING = [
  {name: 'NONE', desc: 'send tokens immediately'},
  {name: 'LOW', desc: 'buffer until word completion'},
  {name: 'MEDIUM', desc: 'buffer until 4 words or punctuation', isDefault: true},
  {name: 'HIGH', desc: 'buffer until punctuation'},
];

const COMPARISON = [
  {criterion: 'Time to first word', classic: 'Gated by the full reasoning chain', stimm: 'Spoken as soon as confidence allows'},
  {criterion: 'Deep reasoning', classic: 'Traded away for latency', stimm: 'Runs in parallel on the supervisor'},
  {criterion: 'Tool calls', classic: 'Block the turn', stimm: 'Resolve behind an early acknowledgement'},
  {criterion: 'Control surface', classic: 'Prompt strings', stimm: 'Typed protocol messages'},
  {criterion: 'Providers', classic: 'Hand-wired per vendor', stimm: 'Runtime-safe contract + generated catalog'},
];

const USE_CASES = [
  {
    tag: 'support',
    title: 'Triage that never stalls',
    body: 'Confirm the caller instantly while the supervisor looks up the account and the order history.',
  },
  {
    tag: 'field',
    title: 'Hands-busy copilots',
    body: 'Technicians and drivers get an answer in the first breath, refined as data arrives.',
  },
  {
    tag: 'telephony',
    title: 'Concierge and booking',
    body: 'Natural back-and-forth on the phone, with real availability checks happening underneath.',
  },
  {
    tag: 'agents',
    title: 'Supervised autonomy',
    body: 'Keep a strict policy layer in the supervisor while the voice stays conversational.',
  },
];

type Theme = 'dark' | 'light';

function ThemeToggle(): ReactNode {
  const [theme, setTheme] = useState<Theme>('dark');

  useEffect(() => {
    setTheme(document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark');
  }, []);

  function flip() {
    const next: Theme = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    document.documentElement.setAttribute('data-theme', next);
    document.documentElement.setAttribute('data-theme-choice', next);
    try {
      localStorage.setItem('theme', next);
    } catch {
      // Private mode: the choice simply does not persist.
    }
  }

  return (
    <button
      type="button"
      className={styles.themeToggle}
      onClick={flip}
      aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
      <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        {theme === 'dark' ? (
          <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z" strokeLinejoin="round" />
        ) : (
          <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" strokeLinecap="round" />
          </>
        )}
      </svg>
    </button>
  );
}

function Trace({segments, playhead}: {segments: Segment[]; playhead?: boolean}): ReactNode {
  return (
    <div className={styles.bars}>
      {segments.map((segment, i) => (
        <div
          key={i}
          className={styles.seg}
          style={
            {
              flex: segment.flex,
              background: segment.background,
              border: segment.border,
              color: segment.color,
              animationDuration: segment.duration,
              animationDelay: segment.delay,
            } as CSSProperties
          }>
          {segment.label}
        </div>
      ))}
      {playhead && <div className={styles.playhead} aria-hidden="true" />}
    </div>
  );
}

export default function Home(): ReactNode {
  return (
    <>
      <Head>
        <title>{`stimm — ${TAGLINE}`}</title>
        <meta name="description" content={DESCRIPTION} />
        <meta property="og:title" content={`stimm — ${TAGLINE}`} />
        <meta property="og:description" content={DESCRIPTION} />
        <meta name="twitter:card" content="summary_large_image" />
        {/* Lets custom.css paint the canvas, incl. overscroll, for the active mode. */}
        <html className="stimm-landing" />
      </Head>

      <div className={styles.page}>
        <div className={styles.grid} aria-hidden="true" />
        <div className={styles.glow} aria-hidden="true" />

        <header className={styles.header}>
          <div className={styles.brand}>
            <div className={styles.mark} aria-hidden="true">
              <span className={styles.markBar} />
              <span className={styles.markBar} />
              <span className={styles.markBar} />
            </div>
            <span className={styles.wordmark}>stimm</span>
          </div>
          <nav className={styles.nav}>
            <a href="#optimistic">Optimistic VUI</a>
            <a href="#runtime">Runtime</a>
            <a href="#compare">Compare</a>
            <a href="#usecases">Use cases</a>
            <a href={GITHUB}>GitHub</a>
          </nav>
          <div className={styles.headerActions}>
            <ThemeToggle />
            <Link className={styles.btnGhostSm} to={DOCS}>
              docs
            </Link>
            <Link className={styles.btnLimeSm} to={INSTALL}>
              pip install stimm
            </Link>
          </div>
        </header>

        <section className={styles.hero}>
          <div className={styles.heroCopy}>
            <div className={styles.badge}>
              <span className={styles.badgeDot} aria-hidden="true" />
              Optimistic VUI runtime
            </div>
            <h1 className={styles.h1}>Voice agents that answer before they finish thinking.</h1>
            <p className={styles.lede}>
              Stimm is an Optimistic VUI runtime on top of LiveKit Agents. A low-latency{' '}
              <code className={styles.inlineCode}>VoiceAgent</code> holds the live turn while a
              high-capability <code className={styles.inlineCode}>Supervisor</code> reasons, plans
              and calls tools in parallel.
            </p>
            <div className={styles.heroActions}>
              <div className={styles.terminal}>
                <span className={styles.prompt}>$</span>
                <span>pip install stimm</span>
                <span className={styles.caret} aria-hidden="true" />
              </div>
              <Link className={styles.btnGhost} to={QUICKSTART}>
                Quick start →
              </Link>
            </div>
            <div className={styles.heroMeta}>
              <span>MIT · open source</span>
              <span>Python + TypeScript supervisors</span>
              <span>WebRTC via LiveKit</span>
            </div>
          </div>

          <div className={styles.trace}>
            <div className={styles.traceHead}>
              <span>time to first audio</span>
              <span className={styles.traceHeadAccent}>illustrative trace</span>
            </div>

            <div className={styles.traceLabel}>classic voice pipeline</div>
            <Trace segments={CLASSIC_TRACE} />
            <div className={styles.traceFootRight}>1 900 ms of silence</div>

            <div className={clsx(styles.traceLabel, styles.traceLabelLime)}>stimm · optimistic turn</div>
            <Trace segments={STIMM_TRACE} playhead />
            <div className={styles.traceFootSplit}>
              <span style={{color: 'var(--stimm-accent)'}}>first word at 320 ms</span>
              <span style={{color: 'var(--stimm-faint)'}}>acknowledge → speak → steer</span>
            </div>

            <div className={styles.stats}>
              {STATS.map((stat) => (
                <div key={stat.label}>
                  <div className={styles.statValue}>{stat.value}</div>
                  <div className={styles.statLabel}>{stat.label}</div>
                </div>
              ))}
            </div>
            <div className={styles.disclaimer}>Timings shown are illustrative — measure your own stack.</div>
          </div>
        </section>

        <section id="optimistic" className={styles.section}>
          <div className={styles.split}>
            <div>
              <div className={styles.eyebrow}>01 — the idea</div>
              <h2 className={styles.h2}>Optimistic VUI is optimistic UI, for speech.</h2>
              <p className={styles.sectionLede}>
                Instead of making the user wait for the entire reasoning chain to complete, the
                system starts behaving usefully as soon as it has enough confidence to move the
                conversation forward.
              </p>
            </div>
            <div className={styles.principles}>
              {PRINCIPLES.map((principle) => (
                <div
                  key={principle.index}
                  className={clsx(styles.principle, principle.cyan && styles.principleCyan)}>
                  <div className={styles.principleIndex}>{principle.index}</div>
                  <div>
                    <div className={styles.principleTitle}>{principle.title}</div>
                    <p className={styles.principleBody}>{principle.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="runtime" className={clsx(styles.section, styles.sectionTinted)}>
          <div className={styles.eyebrow}>02 — the runtime</div>
          <h2 className={styles.h2} style={{maxWidth: '22ch'}}>
            Two cooperating agents, one typed protocol.
          </h2>

          <div className={styles.agents}>
            <div className={styles.agentCard}>
              <div className={styles.agentName}>VoiceAgent</div>
              <p className={styles.agentBody}>
                Optimized for low-latency spoken interaction. Owns the live conversational loop.
              </p>
              <div className={styles.agentList}>
                <span>VAD</span>
                <span>STT</span>
                <span>fast LLM</span>
                <span>TTS</span>
              </div>
            </div>

            <div className={styles.protocol}>
              <div className={styles.protocolLabel}>stimm protocol</div>
              <div className={styles.wire} aria-hidden="true" />
              <div className={clsx(styles.wire, styles.wireCyan)} aria-hidden="true" />
              <div className={styles.protocolCaption}>
                typed messages over
                <br />
                LiveKit data channels
              </div>
            </div>

            <div className={clsx(styles.agentCard, styles.agentCardCyan)}>
              <div className={styles.agentName}>Supervisor</div>
              <p className={styles.agentBody}>
                Optimized for deeper reasoning, planning and tool orchestration. Python or
                TypeScript.
              </p>
              <div className={styles.agentList}>
                <span>planning</span>
                <span>tool calls</span>
                <span>context + memory</span>
                <span>safe steering</span>
              </div>
            </div>
          </div>

          <div className={styles.buffering}>
            {BUFFERING.map((level) => (
              <div key={level.name} className={styles.bufferingCell}>
                <div className={styles.bufferingName}>
                  {level.name}
                  {level.isDefault && <span className={styles.bufferingDefault}> default</span>}
                </div>
                <div className={styles.bufferingDesc}>{level.desc}</div>
              </div>
            ))}
          </div>
        </section>

        <section id="compare" className={styles.section}>
          <div className={styles.eyebrow}>03 — the difference</div>
          <h2 className={clsx(styles.h2, styles.h2Spaced)}>Classic voice agent vs. stimm</h2>
          <div className={styles.compare}>
            {COMPARISON.map((row) => (
              <div key={row.criterion} className={styles.compareRow}>
                <div className={styles.compareCriterion}>{row.criterion}</div>
                <div>
                  <div className={styles.compareTag}>single-agent pipeline</div>
                  <div className={styles.compareValue}>{row.classic}</div>
                </div>
                <div>
                  <div className={clsx(styles.compareTag, styles.compareTagStimm)}>stimm</div>
                  <div className={clsx(styles.compareValue, styles.compareValueStimm)}>{row.stimm}</div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section id="usecases" className={styles.section}>
          <div className={styles.eyebrow}>04 — where it fits</div>
          <h2 className={clsx(styles.h2, styles.h2Spaced)}>Built for speech-first products</h2>
          <div className={styles.useCases}>
            {USE_CASES.map((useCase) => (
              <div key={useCase.tag} className={styles.useCase}>
                <div className={styles.useCaseTag}>{useCase.tag}</div>
                <div className={styles.useCaseTitle}>{useCase.title}</div>
                <p className={styles.useCaseBody}>{useCase.body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.section}>
          <div className={styles.cta}>
            <div>
              <h2 className={styles.h2} style={{marginTop: 0}}>
                Discover providers first.
                <br />
                Install extras second.
              </h2>
              <p className={styles.ctaLede}>
                The wizard-first onboarding walks you through the generated provider catalog, then
                installs only the extras your stack needs.
              </p>
              <div className={styles.ctaActions}>
                <Link className={styles.btnLime} to={INSTALL}>
                  pip install stimm
                </Link>
                <a className={styles.btnOutline} href={GITHUB}>
                  Star on GitHub
                </a>
              </div>
            </div>
            <div className={styles.window}>
              <div className={styles.windowBar}>
                <span className={styles.windowDot} aria-hidden="true" />
                <span className={styles.windowDot} aria-hidden="true" />
                <span className={clsx(styles.windowDot, styles.windowDotLive)} aria-hidden="true" />
                <span className={styles.windowName}>agent.py</span>
              </div>
              <pre className={styles.code}>
                <span className={styles.kw}>from</span> stimm <span className={styles.kw}>import</span> VoiceAgent, Supervisor, Buffering
                {'\n\n'}voice = VoiceAgent({'\n'}
                {'    '}stt=<span className={styles.str}>&quot;deepgram&quot;</span>,{'\n'}
                {'    '}llm=<span className={styles.str}>&quot;gpt-4o-mini&quot;</span>,{'\n'}
                {'    '}tts=<span className={styles.str}>&quot;cartesia&quot;</span>,{'\n'}
                {'    '}buffering=Buffering.MEDIUM,{'\n'})
                {'\n\n'}supervisor = Supervisor({'\n'}
                {'    '}llm=<span className={styles.strCyan}>&quot;claude-sonnet&quot;</span>,{'\n'}
                {'    '}tools=[lookup_order, refund],{'\n'})
                {'\n\n'}
                <span className={styles.kw}>await</span> voice.run(supervisor=supervisor)
              </pre>
            </div>
          </div>
        </section>

        <footer className={styles.footer}>
          <div className={styles.footerBrand}>
            <span className={styles.footerWordmark}>stimm</span>
            <span>{TAGLINE}</span>
          </div>
          <div className={styles.footerLinks}>
            <Link to={DOCS}>Docs</Link>
            <Link to={WIZARD}>Wizard</Link>
            <Link to={PROVIDERS}>Providers</Link>
            <a href={GITHUB}>GitHub</a>
            <span>© {new Date().getFullYear()} stimm</span>
          </div>
        </footer>
      </div>
    </>
  );
}
