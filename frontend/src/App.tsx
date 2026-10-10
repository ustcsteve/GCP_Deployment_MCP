import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { GoogleLogin, GoogleOAuthProvider, googleLogout } from "@react-oauth/google";

type Message = {
  role: "user" | "assistant";
  text: string;
};

type ChatResponse = {
  response: string;
  session_id: string;
};

type AuthenticatedUser = {
  email: string;
  name: string;
};

const starterPrompts = [
  "Compare the latest market signals for NVDA and AMD",
  "Explain the main risks in a concentrated tech portfolio",
  "Give me background on the business behind COST",
];

export default function App() {
  const [clientId, setClientId] = useState("");
  const [configLoading, setConfigLoading] = useState(true);
  const [configError, setConfigError] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [identity, setIdentity] = useState<AuthenticatedUser | null>(null);
  const [authError, setAuthError] = useState("");
  const [authPending, setAuthPending] = useState(false);

  useEffect(() => {
    let active = true;
    fetch("/api/auth/config")
      .then(async (response) => {
        const config = (await response.json()) as { client_id?: string; detail?: string };
        if (!response.ok || !config.client_id) {
          throw new Error(config.detail || "Google Sign-In is not configured.");
        }
        if (active) setClientId(config.client_id);
      })
      .catch((requestError) => {
        if (active) {
          setConfigError(
            requestError instanceof Error ? requestError.message : "Unable to load sign-in configuration.",
          );
        }
      })
      .finally(() => {
        if (active) setConfigLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function signIn(credential: string) {
    setAuthPending(true);
    setAuthError("");
    try {
      const response = await fetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${credential}` },
      });
      const result = (await response.json()) as AuthenticatedUser & { detail?: string };
      if (!response.ok) throw new Error(result.detail || "Google sign-in failed.");
      setIdentity(result);
      setAccessToken(credential);
    } catch (requestError) {
      setAuthError(
        requestError instanceof Error ? requestError.message : "Google sign-in failed.",
      );
    } finally {
      setAuthPending(false);
    }
  }

  function signOut() {
    googleLogout();
    setIdentity(null);
    setAccessToken("");
    setAuthError("");
  }

  if (configLoading) return <SignInPage message="Checking sign-in configuration…" />;
  if (!clientId) return <SignInPage message={configError} />;

  return (
    <GoogleOAuthProvider clientId={clientId}>
      {accessToken && identity ? (
        <Workspace accessToken={accessToken} identity={identity} onSignOut={signOut} />
      ) : (
        <SignInPage
          message={authError}
          pending={authPending}
          onSignIn={signIn}
          onError={() => setAuthError("Google sign-in did not complete. Try again.")}
        />
      )}
    </GoogleOAuthProvider>
  );
}

function SignInPage({
  message,
  pending = false,
  onSignIn,
  onError,
}: {
  message: string;
  pending?: boolean;
  onSignIn?: (credential: string) => Promise<void>;
  onError?: () => void;
}) {
  return (
    <main className="signin-page">
      <section className="signin-content">
        <a className="signin-brand" href="/" aria-label="FinMarket home">
          <span className="brand-mark">F<span>.</span></span>
          <span className="brand-name">FINMARKET<small>INTELLIGENCE</small></span>
        </a>
        <div className="signin-eyebrow">PRIVATE RESEARCH WORKSPACE</div>
        <h1>Sign in to continue.</h1>
        <p className="signin-policy">Access is limited to verified Gmail accounts.</p>
        {onSignIn && !pending && (
          <GoogleLogin
            onSuccess={(credentialResponse) => {
              if (credentialResponse.credential) {
                void onSignIn(credentialResponse.credential);
              } else {
                onError?.();
              }
            }}
            onError={onError}
            text="signin_with"
            shape="rectangular"
            theme="outline"
            size="large"
          />
        )}
        {pending && <div className="signin-pending">Verifying Google account…</div>}
        {message && <div className="signin-error" role="alert">{message}</div>}
        <div className="signin-footer">GOOGLE IDENTITY · VERIFIED SERVER-SIDE</div>
      </section>
    </main>
  );
}

function Workspace({
  accessToken,
  identity,
  onSignOut,
}: {
  accessToken: string;
  identity: AuthenticatedUser;
  onSignOut: () => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [serviceMode, setServiceMode] = useState<"loading" | "demo" | "live" | "offline">("loading");
  const [menuOpen, setMenuOpen] = useState(false);
  const transcriptEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    fetch("/api/health")
      .then(async (response) => {
        if (!response.ok) throw new Error("API unavailable");
        return (await response.json()) as { mode?: string };
      })
      .then((health) => {
        if (active) setServiceMode(health.mode === "demo" ? "demo" : "live");
      })
      .catch(() => {
        if (active) setServiceMode("offline");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pending]);

  async function sendMessage(text = draft) {
    const message = text.trim();
    if (!message || pending) return;

    setMessages((current) => [...current, { role: "user", text: message }]);
    setDraft("");
    setError("");
    setPending(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ message, session_id: sessionId }),
      });
      const result = (await response.json()) as ChatResponse & { detail?: string };
      if (!response.ok) throw new Error(result.detail || "The request failed.");
      setSessionId(result.session_id);
      setMessages((current) => [...current, { role: "assistant", text: result.response }]);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to reach the agent. Try again.",
      );
    } finally {
      setPending(false);
    }
  }

  function startNewChat() {
    setMessages([]);
    setSessionId(null);
    setError("");
    setDraft("");
    setMenuOpen(false);
  }

  return (
    <main className="workspace">
      <aside className={`rail ${menuOpen ? "rail-open" : ""}`}>
        <a className="brand" href="/" aria-label="FinMarket home">
          <span className="brand-mark">F<span>.</span></span>
          <span className="brand-name">FINMARKET<small>INTELLIGENCE</small></span>
        </a>

        <button className="new-chat" onClick={startNewChat} disabled={pending}>
          <span aria-hidden="true">+</span> New research
        </button>

        <div className="rail-label">WORKSPACE</div>
        <div className="active-workspace">
          <span className="workspace-dot" />
          Market research
          <span className="active-indicator">CURRENT</span>
        </div>

        <div className="rail-bottom">
          <div className="signed-in-user">
            <span className="connection-label">SIGNED IN</span>
            <span className="user-email">{identity.email}</span>
            <button className="signout-button" onClick={onSignOut}>Sign out</button>
          </div>
          <div className="connection-label">SERVICE STATUS</div>
          <div className="connection-state">
            <span className={`status-dot ${serviceMode === "offline" ? "offline" : "online"}`} />
            {serviceMode === "demo" ? "Demo mode · no AI" : serviceMode === "live" ? "API connected" : serviceMode === "loading" ? "Checking API" : "API unavailable"}
          </div>
          <div className="rail-footnote">Market data · Research · Risk</div>
        </div>
      </aside>
      {menuOpen && (
        <button
          className="rail-backdrop"
          aria-label="Close navigation"
          onClick={() => setMenuOpen(false)}
        />
      )}

      <section className="main-panel">
        <header className="topbar">
          <button
            className="mobile-menu"
            aria-label="Toggle navigation"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <span />
            <span />
          </button>
          <div className="breadcrumb"><span>RESEARCH DESK</span><b>/</b> EQUITIES</div>
          <div className="topbar-meta"><span className="live-mark" /> LIVE WORKSPACE</div>
        </header>

        <div className="conversation-wrap">
          <div className="conversation-heading">
            <div>
              <div className="eyebrow">FINANCIAL MARKET INTELLIGENCE</div>
              <h1>Research, with context.</h1>
              <p>Ask about market movement, company fundamentals, or portfolio exposure.</p>
            </div>
            <div className="session-tag"><span>ADK</span> AGENT SESSION</div>
          </div>

          <div className="transcript" aria-live="polite">
            {messages.length === 0 ? (
              <section className="welcome-block">
                <div className="welcome-icon">F<span>.</span></div>
                <div className="welcome-copy">
                  <div className="message-kicker">FINMARKET ASSISTANT <span>READY</span></div>
                  <h2>What are you looking into?</h2>
                  <p>
                    I can bring together market data, company background, and portfolio
                    concentration signals in one research brief.
                  </p>
                  <div className="prompt-list">
                    {starterPrompts.map((prompt, index) => (
                      <button key={prompt} onClick={() => void sendMessage(prompt)}>
                        <span>0{index + 1}</span>{prompt}<b aria-hidden="true">↗</b>
                      </button>
                    ))}
                  </div>
                </div>
              </section>
            ) : (
              <div className="message-list">
                {messages.map((message, index) => (
                  <article className={`message message-${message.role}`} key={`${index}-${message.role}`}>
                    {message.role === "assistant" && <div className="message-avatar">F<span>.</span></div>}
                    <div className="message-body">
                      <div className="message-kicker">
                        {message.role === "user" ? "YOU" : "FINMARKET ASSISTANT"}
                      </div>
                      {message.role === "assistant" ? (
                        <div className="message-text markdown-content">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              table: ({ children }) => (
                                <div className="markdown-table-wrap">
                                  <table>{children}</table>
                                </div>
                              ),
                            }}
                          >
                            {message.text}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <div className="message-text">{message.text}</div>
                      )}
                    </div>
                  </article>
                ))}
                {pending && (
                  <article className="message message-assistant">
                    <div className="message-avatar">F<span>.</span></div>
                    <div className="message-body">
                      <div className="message-kicker">FINMARKET ASSISTANT <span>ANALYZING</span></div>
                      <div className="thinking"><i /><i /><i /></div>
                    </div>
                  </article>
                )}
                <div ref={transcriptEnd} />
              </div>
            )}
            {error && <div className="error-banner" role="alert">{error}</div>}
          </div>

          <form
            className="composer"
            onSubmit={(event) => {
              event.preventDefault();
              void sendMessage();
            }}
          >
            <textarea
              aria-label="Your research question"
              placeholder="Ask a market or portfolio question..."
              value={draft}
              maxLength={4000}
              rows={1}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendMessage();
                }
              }}
            />
            <div className="composer-footer">
              <span>Research can be incomplete. Verify critical market decisions.</span>
              <button type="submit" disabled={pending || !draft.trim()}>
                {pending ? "Working" : "Send question"}<span aria-hidden="true">↗</span>
              </button>
            </div>
          </form>
        </div>
        <footer className="page-footer">
          <span>FINMARKET INTELLIGENCE</span>
          <span>MARKET DATA PROVIDED BY ALPHA VANTAGE</span>
        </footer>
      </section>
    </main>
  );
}