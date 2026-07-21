import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronRight,
  Code2,
  Compass,
  Copy,
  CreditCard,
  FileCheck2,
  FileSearch,
  GitBranch,
  Globe,
  Hand,
  HelpCircle,
  KeyRound,
  Lock,
  LogOut,
  Moon,
  Network,
  Play,
  Pause,
  Plug,
  Plus,
  Radio,
  RefreshCw,
  Save,
  Scale,
  Search,
  Settings,
  ShieldCheck,
  SquareFunction,
  Sun,
  Target,
  Trash2,
  Upload,
  X,
  Zap,
} from "lucide-react";
import { api, clearTokens, get, post, setTokens, token } from "./api";

const kinds = {
  question: "#58a6ff",
  hypothesis: "#a78bfa",
  claim: "#2dd4bf",
  evidence: "#67e8a7",
  contradiction: "#fb7185",
  counterexample: "#ef4444",
  dead_end: "#f59e0b",
  computation: "#38bdf8",
  formal_verification: "#34d399",
  conclusion: "#22c55e",
};
const fmt = (d) => (d ? new Date(d).toLocaleString() : "");

function Brand() {
  return (
    <div className="brand">
      <span className="brandMark">
        <i />
      </span>
      <div>
        <b>PICO PROBE</b>
        <small>RESEARCH ASSURANCE</small>
      </div>
    </div>
  );
}
function Toast({ toast, onClose }) {
  if (!toast) return null;
  return (
    <div className={`toast ${toast.type || ""}`}>
      <span>{toast.message}</span>
      <button onClick={onClose}>
        <X size={15} />
      </button>
    </div>
  );
}

function Auth({ onDone, theme, setTheme }) {
  const [mode, setMode] = useState("login");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "register") await post("/auth/register", form);
      const data = await post("/auth/login", {
        username: form.username,
        password: form.password,
      });
      setTokens(data);
      onDone();
    } catch (e) {
      setError(
        e.status === 401
          ? "That account was not found. Create an account first, or check the username and password."
          : e.message,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="authPage">
      <button
        className="authTheme"
        aria-label={`Use ${theme === "dark" ? "light" : "dark"} mode`}
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      >
        {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
      </button>
      <section className="authIntro">
        <Brand />
        <div className="eyebrow">
          <Target size={14} /> EVIDENCE BEFORE CERTAINTY
        </div>
        <h1>
          Research you can
          <br />
          <em>inspect.</em>
        </h1>
        <p>
          Pico Probe separates model proposals from evidence, challenges,
          deterministic checks, and human decisions—then preserves the whole
          trail.
        </p>
        <div className="featureStrip">
          <span>
            <Network />
            Claim graph
          </span>
          <span>
            <ShieldCheck />
            Independent checks
          </span>
          <span>
            <Radio />
            Complete replay
          </span>
        </div>
      </section>
      <section className="authCard">
        <div className="authTabs">
          <button
            className={mode === "login" ? "active" : ""}
            onClick={() => {
              setMode("login");
              setError("");
            }}
          >
            Sign in
          </button>
          <button
            className={mode === "register" ? "active" : ""}
            onClick={() => {
              setMode("register");
              setError("");
            }}
          >
            Create account
          </button>
        </div>
        <form onSubmit={submit}>
          <label>
            Username
            <input
              autoFocus
              required
              minLength="3"
              title="Use letters, numbers, dots, underscores, or hyphens"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              placeholder="researcher"
            />
          </label>
          {mode === "register" && (
            <label>
              Email
              <input
                type="email"
                required
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="you@example.com"
              />
            </label>
          )}
          <label>
            Password
            <input
              type="password"
              required
              minLength="10"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder="At least 10 characters"
            />
          </label>
          {error && <div className="formError">{error}</div>}
          <button className="primary full" disabled={busy}>
            {busy ? (
              <RefreshCw className="spin" size={17} />
            ) : (
              <ArrowRight size={17} />
            )}{" "}
            {mode === "register" ? "Create workspace" : "Enter workspace"}
          </button>
        </form>
        <p className="authFoot">
          New here? Select Create account first · mock mode needs no API key
        </p>
      </section>
    </main>
  );
}

function Sidebar({
  page,
  setPage,
  project,
  onExit,
  theme,
  setTheme,
  onTutorial,
}) {
  const research = project
    ? [
        ["contract", Target, "Assurance contract"],
        ["pipeline", GitBranch, "Pipeline editor"],
        ["runs", Play, "Run research"],
        ["verification", Scale, "Verification"],
        ["graph", Network, "Claim graph"],
        ["passport", FileCheck2, "Claim passport"],
        ["discovery", Compass, "Discovery"],
        ["replay", Radio, "Replay"],
      ]
    : [];
  const global = [
    ["library", Lock, "Private library"],
    ["public", Globe, "Public library"],
    ["plugins", Plug, "Plugins"],
    ["settings", Settings, "Settings & API keys"],
  ];
  return (
    <aside className="sidebar">
      <Brand />
      {project && (
        <button className="back" onClick={onExit}>
          <ArrowLeft size={16} /> Libraries
        </button>
      )}
      <nav>
        {research.length > 0 && <small>RESEARCH</small>}
        {research.map(([id, Icon, label]) => (
          <button
            data-tour={id}
            key={id}
            className={page === id ? "active" : ""}
            onClick={() => setPage(id)}
          >
            <Icon size={18} />
            <span>{label}</span>
            {page === id && <i />}
          </button>
        ))}
        <small>LIBRARIES & SYSTEM</small>
        {global.map(([id, Icon, label]) => (
          <button
            key={id}
            className={page === id ? "active" : ""}
            onClick={() => {
              if (project) onExit(id);
              else setPage(id);
            }}
          >
            <Icon size={18} />
            <span>{label}</span>
            {page === id && <i />}
          </button>
        ))}
      </nav>
      <div className="sideBottom">
        <div className="system">
          <span className="liveDot" />
          Assurance kernel ready
        </div>
        <button onClick={onTutorial}>
          <HelpCircle size={17} /> Guided tour
        </button>
        <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
          {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}{" "}
          {theme === "dark" ? "Light mode" : "Dark mode"}
        </button>
        <button
          onClick={() => {
            clearTokens();
            location.reload();
          }}
        >
          <LogOut size={17} /> Sign out
        </button>
      </div>
    </aside>
  );
}

function Topbar({ project, title, action }) {
  const [showQuestion, setShowQuestion] = useState(false);
  return (
    <header className="topbar">
      <div>
        {project && (
          <div className="crumb">
            PROJECT <ChevronRight size={12} /> {project.title}
          </div>
        )}
        <h2>{title}</h2>
      </div>
      <div className="topActions">
        {project && (
          <button className="researchQuestionRef" onClick={() => setShowQuestion(true)} title="View the canonical research question">
            <code>\researchquestion</code>
          </button>
        )}
        {action}
      </div>
      {showQuestion && (
        <Modal title="Canonical research question" close={() => setShowQuestion(false)}>
          <div className="questionReferenceCard"><code>\researchquestion</code><p>{project.question}</p></div>
        </Modal>
      )}
    </header>
  );
}

function LibraryPage({ openProject, notify, onDemo }) {
  const [projects, setProjects] = useState([]);
  const [filter, setFilter] = useState("");
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({
    title: "",
    question: "",
    abstract: "",
    tags: [],
  });
  const load = () =>
    get("/projects")
      .then(setProjects)
      .catch((e) => notify(e.message, "error"));
  useEffect(() => {
    void load();
  }, []);
  const visibleProjects = useMemo(() => {
    const query = filter.trim().toLowerCase();
    if (!query) return projects;
    return projects.filter((project) =>
      [
        project.title,
        project.question,
        project.abstract,
        ...(project.tags || []),
      ]
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }, [projects, filter]);
  async function create(e) {
    e.preventDefault();
    try {
      const p = await post("/projects", form);
      setShow(false);
      openProject(p, "contract");
    } catch (e) {
      notify(e.message, "error");
    }
  }
  return (
    <>
      <Topbar
        title="Investigations"
        action={
          <button
            data-tour="new"
            className="primary"
            onClick={() => setShow(true)}
          >
            <Plus size={17} /> New investigation
          </button>
        }
      />
      <div className="page">
        <section className="heroPanel">
          <div>
            <span className="eyebrow">PICO PROBE · RESEARCH ASSURANCE</span>
            <h3>Make the reasoning inspectable.</h3>
            <p>
              Begin with a question. End with claims whose evidence, challenges,
              checks, provenance, and human decisions can be examined
              separately.
            </p>
            <div className="heroActions">
              <button className="primary" onClick={onDemo}>
                <Compass size={17} /> Start guided investigation
              </button>
              <button onClick={() => setShow(true)}>
                Start from a blank question
              </button>
            </div>
          </div>
          <div className="probeMark" aria-hidden="true">
            <span />
            <i />
            <b />
          </div>
        </section>
        <div className="sectionHead">
          <div>
            <h3>Your investigations</h3>
            <p>
              {projects.length} saved{" "}
              {projects.length === 1 ? "project" : "projects"}
            </p>
          </div>
          <div className="filter">
            <Search size={16} />
            <input
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder="Filter investigations"
              aria-label="Filter investigations"
            />
          </div>
        </div>
        {visibleProjects.length ? (
          <div className="projectGrid">
            {visibleProjects.map((p) => (
              <button
                className="projectCard"
                key={p.id}
                onClick={() => openProject(p)}
              >
                <div className="projectIcon">
                  <Network />
                </div>
                <div className="statusPill">
                  <span /> {p.status}
                </div>
                <h3>{p.title}</h3>
                <p>{p.question}</p>
                <div className="cardMeta">
                  <span>
                    <GitBranch size={14} /> main
                  </span>
                  <span>{fmt(p.updated_at)}</span>
                </div>
              </button>
            ))}
          </div>
        ) : projects.length ? (
          <div className="empty compact">
            <Search size={32} />
            <h3>No matching investigations</h3>
            <p>Try a title, question, context term, or tag.</p>
          </div>
        ) : (
          <div className="empty">
            <Target size={40} />
            <h3>No investigations yet</h3>
            <p>
              Use the guided investigation to see the complete assurance
              workflow in a few minutes.
            </p>
            <button className="primary" onClick={onDemo}>
              <Compass size={17} /> Start guided investigation
            </button>
          </div>
        )}
      </div>
      {show && (
        <Modal title="New investigation" close={() => setShow(false)}>
          <form onSubmit={create} className="stack">
            <label>
              Project title
              <input
                required
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="A concise investigation name"
              />
            </label>
            <label>
              Research question
              <textarea
                required
                value={form.question}
                onChange={(e) => setForm({ ...form, question: e.target.value })}
                placeholder="What are you trying to establish?"
              />
            </label>
            <label>
              Context <small>optional</small>
              <textarea
                value={form.abstract}
                onChange={(e) => setForm({ ...form, abstract: e.target.value })}
                placeholder="Why this matters and what is in scope"
              />
            </label>
            <button className="primary">
              <ArrowRight size={17} /> Define the assurance contract
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}

function Modal({ title, close, children, wide = false }) {
  return (
    <div
      className="modalShade"
      onMouseDown={(e) => e.target === e.currentTarget && close()}
    >
      <section className={`modal ${wide ? "wide" : ""}`}>
        <header>
          <h3>{title}</h3>
          <button onClick={close}>
            <X />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}

function GraphPage({ project, notify }) {
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [selected, setSelected] = useState(null);
  const [showClaim, setShowClaim] = useState(false);
  const [claim, setClaim] = useState({
    statement: "",
    assumptions: [],
    required_capabilities: [],
  });
  const load = () =>
    get(`/projects/${project.id}/graph`)
      .then(setGraph)
      .catch((e) => notify(e.message, "error"));
  useEffect(() => {
    void load();
  }, [project.id]);
  async function addClaim(e) {
    e.preventDefault();
    try {
      await post(`/projects/${project.id}/claims`, claim);
      setShowClaim(false);
      setClaim({ statement: "", assumptions: [], required_capabilities: [] });
      load();
      notify("Claim added to Research Graph");
    } catch (e) {
      notify(e.message, "error");
    }
  }
  async function publish() {
    try {
      const snapshot = await post(`/projects/${project.id}/publish`);
      notify(`Public snapshot ${snapshot.snapshot_id.slice(0, 12)} created`);
    } catch (error) {
      notify(error.message, "error");
    }
  }
  const layout = useMemo(
    () =>
      graph.nodes.map((n, i) => ({
        ...n,
        x: 90 + (i % 4) * 230,
        y: 85 + Math.floor(i / 4) * 165,
      })),
    [graph],
  );
  return (
    <>
      <Topbar
        project={project}
        title="Research graph"
        action={
          <>
            <button onClick={publish}>
              <Globe size={16} /> Publish snapshot
            </button>
            <button onClick={load}>
              <RefreshCw size={16} /> Refresh
            </button>
            <button className="primary" onClick={() => setShowClaim(true)}>
              <Plus size={17} /> Add claim
            </button>
          </>
        }
      />
      <section className="graphGuide">
        <Network />
        <div>
          <b>How to read the Claim Graph</b>
          <p>
            This is the durable research record, not the execution pipeline.
            Each card is a typed claim, source, objection, computation, proof,
            or human decision. Lines state whether one item supports, critiques,
            or verifies another. Select any node to inspect its content and
            provenance.
          </p>
        </div>
      </section>
      <div className="workspace">
        <div className="graphToolbar">
          <span>{graph.nodes.length} nodes</span>
          <span>{graph.edges.length} relationships</span>
          <div className="legend">
            {Object.entries(kinds)
              .slice(0, 6)
              .map(([k, c]) => (
                <i key={k}>
                  <b style={{ background: c }} />
                  {k.replace("_", " ")}
                </i>
              ))}
          </div>
        </div>
        <div className="canvas">
          <svg className="edges">
            {graph.edges.map((e) => {
              const a = layout.find((n) => n.id === e.source_id),
                b = layout.find((n) => n.id === e.target_id);
              return a && b ? (
                <g key={e.id}>
                  <line
                    x1={a.x + 78}
                    y1={a.y + 38}
                    x2={b.x + 78}
                    y2={b.y + 38}
                  />
                  <text x={(a.x + b.x) / 2 + 78} y={(a.y + b.y) / 2 + 31}>
                    {e.edge_type}
                  </text>
                </g>
              ) : null;
            })}
          </svg>
          {layout.map((n) => (
            <button
              key={n.id}
              className={`graphNode ${selected?.id === n.id ? "selected" : ""}`}
              style={{
                left: n.x,
                top: n.y,
                "--kind": kinds[n.kind] || "#64748b",
              }}
              onClick={() => setSelected(n)}
            >
              <span className="nodeKind">{n.kind.replaceAll("_", " ")}</span>
              <b>{n.title}</b>
              <small className={`nodeStatus ${n.status}`}>{n.status}</small>
            </button>
          ))}
          {!layout.length && (
            <div className="canvasEmpty">
              <Network size={52} />
              <h3>Your graph is ready</h3>
              <p>
                Add the first claim to begin structuring this investigation.
              </p>
              <button className="primary" onClick={() => setShowClaim(true)}>
                <Plus /> Add a claim
              </button>
            </div>
          )}
        </div>
        {selected && (
          <aside className="inspector">
            <div className="inspectorTop">
              <span style={{ background: kinds[selected.kind] }} />
              <div>
                <small>{selected.kind}</small>
                <h3>{selected.title}</h3>
              </div>
              <button onClick={() => setSelected(null)}>
                <X size={17} />
              </button>
            </div>
            <div className="inspectBody">
              <label>Status</label>
              <div className={`statusBox ${selected.status}`}>
                {selected.status}
              </div>
              <label>Structured content</label>
              <pre>{JSON.stringify(selected.content, null, 2)}</pre>
              <label>Provenance</label>
              <pre>{JSON.stringify(selected.provenance, null, 2)}</pre>
            </div>
          </aside>
        )}
      </div>
      {showClaim && (
        <Modal title="Add a structured claim" close={() => setShowClaim(false)}>
          <form className="stack" onSubmit={addClaim}>
            <label>
              Claim statement
              <textarea
                autoFocus
                required
                value={claim.statement}
                onChange={(e) =>
                  setClaim({ ...claim, statement: e.target.value })
                }
                placeholder="State the claim precisely"
              />
            </label>
            <label>
              Assumptions <small>one per line</small>
              <textarea
                onChange={(e) =>
                  setClaim({
                    ...claim,
                    assumptions: e.target.value.split("\n").filter(Boolean),
                  })
                }
              />
            </label>
            <button className="primary">
              <Network size={17} /> Add to graph
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}

// Kept temporarily as a compatibility reference while the visual editor replaces it.
// eslint-disable-next-line no-unused-vars
function LegacyPipelinePage({ project, notify }) {
  const [templates, setTemplates] = useState([]),
    [pipelines, setPipelines] = useState([]),
    [chosen, setChosen] = useState(null),
    [showNode, setShowNode] = useState(false);
  const [node, setNode] = useState({
    label: "Researcher contribution",
    type: "human_review",
    owner: "human",
    instructions: "",
  });
  const load = () =>
    Promise.all([
      get("/pipeline-templates"),
      get(`/projects/${project.id}/pipelines`),
    ]).then(([t, p]) => {
      setTemplates(t);
      setPipelines(p);
    });
  useEffect(() => {
    load().catch((e) => notify(e.message, "error"));
  }, [project.id]);
  async function instantiate(t) {
    try {
      const p = await post(
        `/pipeline-templates/${t.id}/instantiate?project_id=${project.id}`,
      );
      setChosen(p);
      load();
      notify(`${t.name} instantiated`);
    } catch (e) {
      notify(e.message, "error");
    }
  }
  async function addNode(e) {
    e.preventDefault();
    const definition = structuredClone(chosen.definition);
    const id = `${node.owner}_${Date.now()}`;
    const config = { label: node.label, instructions: node.instructions };
    if (node.owner === "human") config.human_input = true;
    if (node.owner === "ai") config.provider = "openai";
    if (node.owner === "lean") {
      config.plugin = "core.lean";
      config.input = { theorem: node.instructions };
    }
    definition.nodes.push({ id, type: node.type, config });
    if (definition.nodes.length > 1)
      definition.edges.push({ source: definition.nodes.at(-2).id, target: id });
    try {
      const saved = await api(`/pipelines/${chosen.id}`, {
        method: "PUT",
        body: JSON.stringify(definition),
      });
      setChosen(saved);
      setShowNode(false);
      load();
      notify("Independent contribution step added");
    } catch (err) {
      notify(err.message, "error");
    }
  }
  return (
    <>
      <Topbar
        project={project}
        title="Pipeline studio"
        action={
          chosen && (
            <button className="primary" onClick={() => setShowNode(true)}>
              <Plus size={17} /> Add step
            </button>
          )
        }
      />
      <div className="page">
        <section className="governanceBanner">
          <Scale />
          <div>
            <span className="eyebrow">GOVERNED AUTONOMY</span>
            <h3>AI proposes. Evidence, tools, and people decide.</h3>
            <p>
              Assign any step to AI, yourself, an independent reviewer, or a
              deterministic verifier. Every handoff is preserved in Research
              Replay.
            </p>
          </div>
        </section>
        <div className="sectionHead">
          <div>
            <h3>Research workflow templates</h3>
            <p>
              Start with a validated topology, then decide who performs each
              step.
            </p>
          </div>
        </div>
        <div className="templateGrid">
          {templates.map((t, i) => (
            <article className="templateCard" key={t.id}>
              <div className="templateNum">
                {String(i + 1).padStart(2, "0")}
              </div>
              <GitBranch size={25} />
              <h3>{t.name}</h3>
              <p>
                {t.nodes.length} steps · {t.edges.length} evidence paths
              </p>
              <div className="miniFlow">
                {t.nodes.slice(0, 5).map((n) => (
                  <span key={n.id} title={n.type} />
                ))}
              </div>
              <button onClick={() => instantiate(t)}>
                <Plus size={16} /> Use topology
              </button>
            </article>
          ))}
        </div>
        {pipelines.length > 0 && (
          <section className="savedPipelines">
            <h3>Saved pipelines</h3>
            {pipelines.map((p) => (
              <button
                className={chosen?.id === p.id ? "active" : ""}
                key={p.id}
                onClick={() => setChosen(p)}
              >
                <GitBranch />
                <span>
                  <b>{p.name}</b>
                  <small>
                    {p.definition.nodes.length} steps · version {p.version}
                  </small>
                </span>
                <ChevronRight />
              </button>
            ))}
          </section>
        )}
        {chosen && (
          <section className="pipelineDetail">
            <div>
              <span className="eyebrow">ACTIVE PIPELINE</span>
              <h3>{chosen.definition.name}</h3>
            </div>
            <div className="pipelineNodes governed">
              {chosen.definition.nodes.map((n, i) => {
                const owner = n.config?.human_input
                  ? "human"
                  : n.config?.plugin
                    ? "tool"
                    : n.config?.provider
                      ? "ai"
                      : "adaptive";
                return (
                  <div key={n.id} data-owner={owner}>
                    <b>{i + 1}</b>
                    <span>
                      {n.config?.label || n.type.replaceAll("_", " ")}
                    </span>
                    <small>
                      {owner === "human" ? (
                        <>
                          <Hand /> Researcher
                        </>
                      ) : owner === "tool" ? (
                        <>
                          <Scale /> Verifier
                        </>
                      ) : (
                        <>
                          <Bot /> AI / adaptive
                        </>
                      )}
                    </small>
                  </div>
                );
              })}
            </div>
          </section>
        )}
      </div>
      {showNode && (
        <Modal
          title="Add an independent pipeline step"
          close={() => setShowNode(false)}
        >
          <form className="stack" onSubmit={addNode}>
            <label>
              Who performs this step?
              <select
                value={node.owner}
                onChange={(e) => setNode({ ...node, owner: e.target.value })}
              >
                <option value="human">
                  Researcher — I contribute directly
                </option>
                <option value="ai">AI — primary contributor</option>
                <option value="lean">Lean — deterministic proof check</option>
              </select>
            </label>
            <label>
              Step name
              <input
                required
                value={node.label}
                onChange={(e) => setNode({ ...node, label: e.target.value })}
              />
            </label>
            <label>
              {node.owner === "lean"
                ? "Lean theorem or proof"
                : "Instructions / acceptance criteria"}
              <textarea
                required
                value={node.instructions}
                onChange={(e) =>
                  setNode({ ...node, instructions: e.target.value })
                }
                placeholder={
                  node.owner === "lean"
                    ? "theorem identity : 1 = 1 := by rfl"
                    : "Describe what must be contributed or reviewed."
                }
              />
            </label>
            <button className="primary">
              <CheckCircle2 /> Add governed step
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}

function pipelineLayout(definition) {
  const nodes = definition?.nodes || [];
  const edges = definition?.edges || [];
  const depth = Object.fromEntries(nodes.map((node) => [node.id, 0]));
  for (let pass = 0; pass < nodes.length; pass += 1)
    for (const edge of edges)
      depth[edge.target] = Math.max(
        depth[edge.target] || 0,
        (depth[edge.source] || 0) + 1,
      );
  const rows = {};
  return nodes.map((node) => {
    const column = depth[node.id] || 0;
    const row = rows[column] || 0;
    rows[column] = row + 1;
    return { ...node, x: 55 + column * 215, y: 65 + row * 125 };
  });
}

// eslint-disable-next-line no-unused-vars
function BasicPipelinePage({ project, notify }) {
  const [templates, setTemplates] = useState([]);
  const [pipelines, setPipelines] = useState([]);
  const [plugins, setPlugins] = useState([]);
  const [chosen, setChosen] = useState(null);
  const [selected, setSelected] = useState(null);
  const [showNode, setShowNode] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [node, setNode] = useState({
    label: "Independent contribution",
    type: "hypothesis_generation",
    owner: "ai",
    provider: "openai",
    plugin: "core.sympy",
    instructions: "",
  });
  const load = () =>
    Promise.all([
      get("/pipeline-templates"),
      get(`/projects/${project.id}/pipelines`),
      get("/plugins"),
    ]).then(([availableTemplates, saved, installed]) => {
      setTemplates(availableTemplates);
      setPipelines(saved);
      setPlugins(installed);
    });
  useEffect(() => {
    load().catch((error) => notify(error.message, "error"));
  }, [project.id]);
  const layout = useMemo(() => pipelineLayout(chosen?.definition), [chosen]);
  async function instantiate(template) {
    try {
      const saved = await post(
        `/pipeline-templates/${template.id}/instantiate?project_id=${project.id}`,
      );
      setChosen(saved);
      setDirty(false);
      await load();
      notify(`${template.name} saved to this investigation`);
    } catch (error) {
      notify(error.message, "error");
    }
  }
  function addNode(event) {
    event.preventDefault();
    const definition = structuredClone(chosen.definition);
    const id = `${node.owner}_${Date.now()}`;
    const config = { label: node.label, instructions: node.instructions };
    if (node.owner === "human") config.human_input = true;
    if (node.owner === "ai") {
      config.provider = node.provider;
      config.model =
        node.provider === "openai"
          ? "gpt-5.6"
          : node.provider === "anthropic"
            ? "claude-sonnet-4-5"
            : node.provider === "google"
              ? "gemini-2.5-pro"
              : "configured-model";
    }
    if (node.owner === "plugin") {
      config.plugin = node.plugin;
      config.input = {};
    }
    definition.nodes.push({
      id,
      type: node.owner === "plugin" ? "plugin" : node.type,
      config,
    });
    if (definition.nodes.length > 1)
      definition.edges.push({ source: definition.nodes.at(-2).id, target: id });
    setChosen({ ...chosen, definition });
    setDirty(true);
    setShowNode(false);
    notify("Step added locally—select Save pipeline to persist it");
  }
  async function save() {
    try {
      const saved = await api(`/pipelines/${chosen.id}`, {
        method: "PUT",
        body: JSON.stringify(chosen.definition),
      });
      setChosen(saved);
      setDirty(false);
      await load();
      notify(`Pipeline saved as version ${saved.version}`);
    } catch (error) {
      notify(error.message, "error");
    }
  }
  async function duplicate() {
    try {
      const saved = await post(`/pipelines/${chosen.id}/duplicate`);
      setChosen(saved);
      await load();
      notify("Pipeline duplicated and saved");
    } catch (error) {
      notify(error.message, "error");
    }
  }
  function removeSelected() {
    if (!selected) return;
    const definition = structuredClone(chosen.definition);
    definition.nodes = definition.nodes.filter(
      (item) => item.id !== selected.id,
    );
    definition.edges = definition.edges.filter(
      (edge) => edge.source !== selected.id && edge.target !== selected.id,
    );
    setChosen({ ...chosen, definition });
    setSelected(null);
    setDirty(true);
  }
  return (
    <>
      <Topbar
        project={project}
        title="Pipeline editor"
        action={
          chosen && (
            <>
              <button onClick={duplicate}>
                <Copy size={16} /> Duplicate
              </button>
              <button className="primary" disabled={!dirty} onClick={save}>
                <Save size={16} /> {dirty ? "Save pipeline" : "Saved"}
              </button>
            </>
          )
        }
      />
      <div className="page pipelinePage">
        <section className="explainPanel">
          <GitBranch />
          <div>
            <span className="eyebrow">THIS IS THE RESEARCH PIPELINE</span>
            <h3>Design who thinks, what branches, and what verifies.</h3>
            <p>
              Nodes are executable steps; lines are dependencies. Parallel AI
              nodes work independently. A comparator can elect an optimal route
              while preserving rejected ideas as amber unexplored branches. The
              Claim Graph is different: it records the claims and evidence
              produced by this pipeline.
            </p>
          </div>
        </section>
        {!chosen && (
          <>
            <div className="sectionHead">
              <div>
                <h3>Start from a saved topology</h3>
                <p>
                  Choosing a topology immediately creates a versioned pipeline.
                  The first template demonstrates independent OpenAI, Claude,
                  and Gemini planning, route election, research, comparison,
                  SymPy, Lean, and human sign-off.
                </p>
              </div>
            </div>
            <div className="templateGrid">
              {templates.map((template, index) => (
                <article className="templateCard" key={template.id}>
                  <div className="templateNum">
                    {String(index + 1).padStart(2, "0")}
                  </div>
                  <GitBranch />
                  <h3>{template.name}</h3>
                  <p>
                    {template.nodes.length} nodes · {template.edges.length}{" "}
                    connections
                  </p>
                  <button onClick={() => instantiate(template)}>
                    <Plus size={16} /> Create saved pipeline
                  </button>
                </article>
              ))}
            </div>
          </>
        )}
        {pipelines.length > 0 && (
          <section className="pipelinePicker">
            <label>
              Saved pipeline
              <select
                value={chosen?.id || ""}
                onChange={(event) => {
                  const pipeline = pipelines.find(
                    (item) => item.id === event.target.value,
                  );
                  setChosen(pipeline || null);
                  setSelected(null);
                  setDirty(false);
                }}
              >
                <option value="">Choose a saved pipeline</option>
                {pipelines.map((pipeline) => (
                  <option key={pipeline.id} value={pipeline.id}>
                    {pipeline.name} · v{pipeline.version}
                  </option>
                ))}
              </select>
            </label>
            {chosen && (
              <button onClick={() => setShowNode(true)}>
                <Plus size={16} /> Add node
              </button>
            )}
          </section>
        )}
        {chosen && (
          <section className="pipelineWorkbench">
            <aside className="nodePalette">
              <span className="eyebrow">NODE PALETTE</span>
              <p>
                Click Add node, then assign the step to a person, AI provider,
                or installed plugin.
              </p>
              {[
                [Bot, "AI model", "Independent planning, critique, synthesis"],
                [
                  Hand,
                  "Researcher",
                  "Your reasoning, code, proof, or decision",
                ],
                [Plug, "Plugin", "Lean, SymPy, simulation, or installed tool"],
                [GitBranch, "Comparator", "Merge branches or elect a route"],
              ].map(([Icon, title, text]) => (
                <div key={title}>
                  <Icon />
                  <span>
                    <b>{title}</b>
                    <small>{text}</small>
                  </span>
                </div>
              ))}
            </aside>
            <div className="pipelineCanvas">
              <svg>
                {chosen.definition.edges.map((edge, index) => {
                  const source = layout.find((item) => item.id === edge.source),
                    target = layout.find((item) => item.id === edge.target);
                  return source && target ? (
                    <path
                      key={`${edge.source}-${edge.target}-${index}`}
                      d={`M${source.x + 165},${source.y + 38} C${source.x + 190},${source.y + 38} ${target.x - 25},${target.y + 38} ${target.x},${target.y + 38}`}
                    />
                  ) : null;
                })}
              </svg>
              {layout.map((item) => {
                const owner = item.config?.human_input
                  ? "human"
                  : item.config?.plugin
                    ? "plugin"
                    : item.config?.provider
                      ? "ai"
                      : "kernel";
                const unexplored =
                  item.config?.unexplored || item.config?.preserved;
                return (
                  <button
                    key={item.id}
                    className={`pipelineNode ${selected?.id === item.id ? "selected" : ""} ${unexplored ? "unexplored" : ""}`}
                    data-owner={owner}
                    style={{ left: item.x, top: item.y }}
                    onClick={() => setSelected(item)}
                  >
                    <small>
                      {owner} · {item.type.replaceAll("_", " ")}
                    </small>
                    <b>{item.config?.label || item.id}</b>
                    <span>
                      {unexplored
                        ? "Preserved · unexplored"
                        : item.config?.provider ||
                          item.config?.plugin ||
                          (owner === "human" ? "Researcher input" : "Kernel")}
                    </span>
                  </button>
                );
              })}
            </div>
            {selected && (
              <aside className="nodeInspector">
                <header>
                  <div>
                    <span className="eyebrow">SELECTED NODE</span>
                    <h3>{selected.config?.label || selected.id}</h3>
                  </div>
                  <button onClick={() => setSelected(null)}>
                    <X />
                  </button>
                </header>
                <dl>
                  <dt>Executor</dt>
                  <dd>
                    {selected.config?.human_input
                      ? "Researcher"
                      : selected.config?.plugin ||
                        selected.config?.provider ||
                        "Pico Probe kernel"}
                  </dd>
                  <dt>Purpose</dt>
                  <dd>
                    {selected.config?.instructions ||
                      selected.type.replaceAll("_", " ")}
                  </dd>
                  <dt>Branch behavior</dt>
                  <dd>
                    {selected.config?.branch_behavior ||
                      "Continue when dependencies complete"}
                  </dd>
                </dl>
                <button className="danger" onClick={removeSelected}>
                  <Trash2 /> Remove node
                </button>
              </aside>
            )}
          </section>
        )}
      </div>
      {showNode && (
        <Modal
          title="Add an executable pipeline node"
          close={() => setShowNode(false)}
        >
          <form className="stack" onSubmit={addNode}>
            <label>
              Who performs this step?
              <select
                value={node.owner}
                onChange={(event) =>
                  setNode({ ...node, owner: event.target.value })
                }
              >
                <option value="human">
                  Researcher — I contribute independently
                </option>
                <option value="ai">AI provider — autonomous contributor</option>
                <option value="plugin">
                  Plugin — deterministic or external tool
                </option>
              </select>
            </label>
            {node.owner === "ai" && (
              <label>
                AI provider
                <select
                  value={node.provider}
                  onChange={(event) =>
                    setNode({ ...node, provider: event.target.value })
                  }
                >
                  {[
                    "openai",
                    "anthropic",
                    "google",
                    "xai",
                    "deepseek",
                    "ollama",
                  ].map((provider) => (
                    <option key={provider}>{provider}</option>
                  ))}
                </select>
              </label>
            )}
            {node.owner === "plugin" && (
              <label>
                Installed plugin
                <select
                  value={node.plugin}
                  onChange={(event) =>
                    setNode({ ...node, plugin: event.target.value })
                  }
                >
                  {plugins.map((plugin) => (
                    <option key={plugin.plugin_id} value={plugin.plugin_id}>
                      {plugin.name} · {plugin.plugin_id}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label>
              Step name
              <input
                required
                value={node.label}
                onChange={(event) =>
                  setNode({ ...node, label: event.target.value })
                }
              />
            </label>
            <label>
              Instructions / acceptance criteria
              <textarea
                required
                value={node.instructions}
                onChange={(event) =>
                  setNode({ ...node, instructions: event.target.value })
                }
                placeholder="Describe exactly what this independent contributor must produce or verify."
              />
            </label>
            <button className="primary">
              <Plus /> Add node to canvas
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}

function EditablePipelinePage({ project, notify }) {
  const [templates, setTemplates] = useState([]);
  const [pipelines, setPipelines] = useState([]);
  const [plugins, setPlugins] = useState([]);
  const [chosen, setChosen] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [connectFrom, setConnectFrom] = useState(null);
  const [mergeSources, setMergeSources] = useState([]);
  const [mergeBehavior, setMergeBehavior] = useState("all");
  const [showNode, setShowNode] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [drag, setDrag] = useState(null);
  const [compilation, setCompilation] = useState(null);
  const [compiling, setCompiling] = useState(false);
  const [node, setNode] = useState({
    label: "",
    type: "hypothesis_generation",
    owner: "ai",
    provider: "openai",
    plugin: "core.sympy",
    instructions: "",
    pluginInput: "{}",
  });
  const emptyNode = (owner = "ai", plugin = "core.sympy") => ({
    label: "", type: "hypothesis_generation", owner, provider: owner === "ai" ? "openai" : "openai",
    plugin, instructions: "", pluginInput: JSON.stringify({
      "core.lean": { source: "theorem pipeline_check : True := by\n  trivial", theorem_name: "pipeline_check" },
      "core.monte_carlo": { seed: 0, trials: 10000, batches: 10, expected_statistic: "mean" },
      "core.sympy": { expression: "1/n**3", operation: "simplify", variables: ["n"] },
      "core.python_experiment": { source: "print(sum(1 / k**3 for k in range(1, 10001)))", seed: 0 },
    }[plugin] || {}, null, 2),
  });
  function openNode(owner = "ai", plugin = "core.sympy") {
    setNode(emptyNode(owner, plugin));
    setShowNode(true);
  }
  const load = () =>
    Promise.all([
      get("/pipeline-templates"),
      get(`/projects/${project.id}/pipelines`),
      get("/plugins"),
    ]).then(([available, saved, installed]) => {
      setTemplates(available);
      setPipelines(saved);
      setPlugins(installed);
      if (project.tags?.includes("guided-demo"))
        setChosen((current) => current || saved[0] || null);
    });
  useEffect(() => {
    load().catch((error) => notify(error.message, "error"));
  }, [project.id]);
  useEffect(() => {
    if (!drag) return;
    const move = (event) => {
      const dx = (event.clientX - drag.clientX) / zoom,
        dy = (event.clientY - drag.clientY) / zoom;
      mutateNode(
        drag.id,
        (item) => ({
          ...item,
          config: {
            ...item.config,
            position: {
              x: Math.max(10, drag.x + dx),
              y: Math.max(10, drag.y + dy),
            },
          },
        }),
        false,
      );
    };
    const up = () => {
      setDrag(null);
      setDirty(true);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up, { once: true });
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [drag, zoom]);
  const definition = chosen?.definition;
  const automatic = useMemo(() => pipelineLayout(definition), [definition]);
  const layout = useMemo(
    () =>
      automatic.map((item) => ({
        ...item,
        x: item.config?.position?.x ?? item.x,
        y: item.config?.position?.y ?? item.y,
      })),
    [automatic],
  );
  const selected = definition?.nodes.find((item) => item.id === selectedId);
  function changeDefinition(update, mark = true) {
    setChosen((current) => ({
      ...current,
      definition:
        typeof update === "function"
          ? update(structuredClone(current.definition))
          : update,
    }));
    if (mark) setDirty(true);
  }
  function mutateNode(id, update, mark = true) {
    changeDefinition((next) => {
      next.nodes = next.nodes.map((item) =>
        item.id === id ? update(item) : item,
      );
      return next;
    }, mark);
  }
  async function instantiate(template) {
    try {
      const saved = await post(
        `/pipeline-templates/${template.id}/instantiate?project_id=${project.id}`,
      );
      setChosen(saved);
      setDirty(false);
      await load();
      notify(`${template.name} created and saved`);
    } catch (error) {
      notify(error.message, "error");
    }
  }
  function addNode(event) {
    event.preventDefault();
    const id = `${node.owner}_${Date.now()}`;
    const config = {
      label: node.label,
      instructions: node.instructions,
      position: {
        x: 60 + (definition?.nodes.length || 0) * 35,
        y: 80 + (definition?.nodes.length || 0) * 28,
      },
    };
    if (node.owner === "human") config.human_input = true;
    if (node.owner === "ai") {
      config.provider = node.provider;
      config.model =
        node.provider === "openai"
          ? "gpt-5.6"
          : node.provider === "anthropic"
            ? "claude-sonnet-4-5"
            : node.provider === "google"
              ? "gemini-2.5-pro"
              : "configured-model";
    }
    if (node.owner === "plugin") {
      config.plugin = node.plugin;
      try {
        config.input = JSON.parse(node.pluginInput || "{}");
      } catch {
        return notify("Plugin input must be valid JSON", "error");
      }
    }
    changeDefinition((next) => {
      next.nodes.push({
        id,
        type: node.owner === "plugin" ? "plugin" : node.type,
        config,
      });
      return next;
    });
    setSelectedId(id);
    setShowNode(false);
  }
  function connectNodes(source, target) {
    if (!source || !target || source === target) return;
    changeDefinition((next) => {
      if (!next.edges.some((edge) => edge.source === source && edge.target === target)) {
        next.edges.push({
          source,
          target,
          relation: "dependency",
        });
      }
      return next;
    });
    setConnectFrom(null);
    notify("Connection created—save to persist it");
  }
  function selectNode(id) {
    if (connectFrom && connectFrom !== id) connectNodes(connectFrom, id);
    setSelectedId(id);
    setSelectedEdge(null);
  }
  function removeNode() {
    changeDefinition((next) => {
      next.nodes = next.nodes.filter((item) => item.id !== selectedId);
      next.edges = next.edges.filter(
        (edge) => edge.source !== selectedId && edge.target !== selectedId,
      );
      return next;
    });
    setSelectedId(null);
  }
  function removeEdge() {
    changeDefinition((next) => {
      next.edges.splice(selectedEdge, 1);
      return next;
    });
    setSelectedEdge(null);
  }
  function updateEdge(field, value) {
    changeDefinition((next) => {
      next.edges[selectedEdge] = {
        ...next.edges[selectedEdge],
        [field]: value,
      };
      return next;
    });
  }
  function toggleMerge(id) {
    setMergeSources((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    );
  }
  function createMerge() {
    if (mergeSources.length < 2)
      return notify("Select at least two source nodes", "error");
    const id = `merge_${Date.now()}`;
    changeDefinition((next) => {
      next.nodes.push({
        id,
        type: mergeBehavior === "vote" ? "synthesis" : "merge",
        config: {
          label:
            mergeBehavior === "vote"
              ? "Vote and elect route"
              : "Merge research branches",
          branch_behavior: mergeBehavior,
          preserve_unselected: mergeBehavior === "vote",
          position: {
            x:
              Math.max(
                ...mergeSources.map(
                  (source) => layout.find((item) => item.id === source)?.x || 0,
                ),
              ) + 235,
            y: Math.min(
              ...mergeSources.map(
                (source) => layout.find((item) => item.id === source)?.y || 80,
              ),
            ),
          },
        },
      });
      for (const source of mergeSources)
        next.edges.push({
          source,
          target: id,
          relation: mergeBehavior === "vote" ? "candidate" : "dependency",
        });
      return next;
    });
    setMergeSources([]);
    setSelectedId(id);
    notify("Merge node created—connect its output to the next step");
  }
  async function save() {
    try {
      const validation = await post("/pipelines/validate", chosen.definition);
      if (!validation.valid)
        return notify(validation.errors.join(" · "), "error");
      const saved = await api(`/pipelines/${chosen.id}`, {
        method: "PUT",
        body: JSON.stringify(chosen.definition),
      });
      setChosen(saved);
      setDirty(false);
      await load();
      notify(
        `Pipeline saved as version ${saved.version}${validation.warnings.length ? ` · ${validation.warnings.length} warning(s)` : ""}`,
      );
    } catch (error) {
      notify(error.message, "error");
    }
  }
  async function duplicate() {
    try {
      const saved = await post(`/pipelines/${chosen.id}/duplicate`);
      setChosen(saved);
      setDirty(false);
      await load();
      notify("Editable copy created");
    } catch (error) {
      notify(error.message, "error");
    }
  }
  async function compile() {
    if (dirty) return notify("Save the pipeline before compiling it", "error");
    setCompiling(true);
    try {
      const plan = await post(`/pipelines/${chosen.id}/compile?allow_default_contract=true`);
      setCompilation(plan);
      notify(`Compiled ${plan.nodes.length} typed nodes against Assurance Contract v${plan.contract_version}`);
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setCompiling(false);
    }
  }
  return (
    <>
      <Topbar
        project={project}
        title="Pipeline editor"
        action={
          chosen && (
            <>
              <button onClick={compile} disabled={compiling || dirty}>
                <ShieldCheck /> {compiling ? "Compiling…" : "Compile pipeline"}
              </button>
              <button onClick={duplicate}>
                <Copy /> Duplicate
              </button>
              <button className="primary" disabled={!dirty} onClick={save}>
                <Save /> {dirty ? "Save pipeline" : "Saved"}
              </button>
            </>
          )
        }
      />
      <div className="page pipelinePage">
        <section className="explainPanel">
          <GitBranch />
          <div>
            <span className="eyebrow">EXECUTABLE RESEARCH PIPELINE</span>
            <h3>Drag, connect, branch, vote, merge, verify.</h3>
            <p>
              Drag nodes by their headers. Select a node to edit every property.
              Start a connection and select its destination. Select multiple
              branch nodes to create an all/any/vote/synthesis merge. “Merge inputs” are completed branches whose outputs will be joined or compared by a newly created merge node. Click a
              line to label or delete it.
            </p>
          </div>
        </section>
        {compilation && (
          <section className="compilationReport">
            <header><ShieldCheck /><div><span className="eyebrow">ASSURANCE-AWARE EXECUTION PLAN</span><h3>Compilation valid · Contract v{compilation.contract_version}</h3></div></header>
            <p>{compilation.nodes.length} nodes · {compilation.edges.length} typed edges · maximum estimated cost {compilation.cost_estimate.maximum_micros.toLocaleString()} μUSD</p>
            {compilation.warnings.map((warning) => <div className="formNote" key={warning}>{warning}</div>)}
          </section>
        )}
        {!chosen && (
          <>
            <div className="sectionHead">
              <div>
                <h3>Choose a starting topology</h3>
                <p>Templates are fully editable after creation.</p>
              </div>
            </div>
            <div className="templateGrid">
              {templates.map((template, index) => (
                <article className="templateCard" key={template.id}>
                  <div className="templateNum">
                    {String(index + 1).padStart(2, "0")}
                  </div>
                  <GitBranch />
                  <h3>{template.name}</h3>
                  <p>
                    {template.nodes.length} nodes · {template.edges.length}{" "}
                    connections
                  </p>
                  <button onClick={() => instantiate(template)}>
                    <Plus /> Create pipeline
                  </button>
                </article>
              ))}
            </div>
          </>
        )}
        {pipelines.length > 0 && (
          <section className="pipelinePicker">
            <label>
              Saved pipeline
              <select
                value={chosen?.id || ""}
                onChange={(event) => {
                  const pipeline = pipelines.find(
                    (item) => item.id === event.target.value,
                  );
                  setChosen(pipeline || null);
                  setSelectedId(null);
                  setDirty(false);
                }}
              >
                <option value="">Choose a pipeline</option>
                {pipelines.map((pipeline) => (
                  <option key={pipeline.id} value={pipeline.id}>
                    {pipeline.name} · v{pipeline.version}
                  </option>
                ))}
              </select>
            </label>
            {chosen && (
              <>
                <button onClick={() => openNode()}>
                  <Plus /> Add node
                </button>
                <button
                  className={connectFrom ? "active" : ""}
                  disabled={!selectedId}
                  onClick={() =>
                    setConnectFrom(connectFrom ? null : selectedId)
                  }
                >
                  <GitBranch />{" "}
                  {connectFrom ? "Cancel connection" : "Connect selected"}
                </button>
              </>
            )}
          </section>
        )}
        {chosen && (
          <section className="editorShell">
            <div className="editorTools">
              <span>
                {connectFrom
                  ? "Select a destination node"
                  : "Select nodes to inspect or edit"}
              </span>
              <div>
                <button onClick={() => setZoom(Math.max(0.55, zoom - 0.1))}>
                  −
                </button>
                <b>{Math.round(zoom * 100)}%</b>
                <button onClick={() => setZoom(Math.min(1.5, zoom + 0.1))}>
                  +
                </button>
              </div>
            </div>
            <div className="pipelineWorkbench fullEditor">
              <aside className="nodePalette">
                <span className="eyebrow">NODE PALETTE</span>
                <button onClick={() => openNode("ai")}>
                  <Bot />
                  <span>
                    <b>AI model</b>
                    <small>Plan, critique, compare, synthesize</small>
                  </span>
                  <Plus />
                </button>
                <button onClick={() => openNode("human")}>
                  <Hand />
                  <span>
                    <b>Researcher</b>
                    <small>Write code, Lean, evidence, decisions</small>
                  </span>
                  <Plus />
                </button>
                <button onClick={() => openNode("plugin")}>
                  <Plug />
                  <span>
                    <b>Plugin</b>
                    <small>Lean, SymPy, simulation, literature</small>
                  </span>
                  <Plus />
                </button>
                {plugins.map((plugin) => (
                  <button key={plugin.plugin_id} onClick={() => openNode("plugin", plugin.plugin_id)}>
                    <Plug />
                    <span><b>{plugin.name}</b><small>{plugin.capabilities?.join(" · ") || plugin.plugin_id}</small></span>
                    <Plus />
                  </button>
                ))}
                <div className="mergeBox">
                  <b>Merge selected branches</b>
                  <select
                    value={mergeBehavior}
                    onChange={(event) => setMergeBehavior(event.target.value)}
                  >
                    <option value="all">All — wait for every branch</option>
                    <option value="any">Any — first successful branch</option>
                    <option value="vote">
                      Vote — elect and preserve others
                    </option>
                    <option value="synthesis">
                      Synthesis — combine all results
                    </option>
                  </select>
                  <button
                    disabled={mergeSources.length < 2}
                    onClick={createMerge}
                  >
                    <GitBranch /> Merge {mergeSources.length} nodes
                  </button>
                </div>
              </aside>
              <div className="pipelineViewport">
                <div
                  className="pipelineCanvas editable"
                  style={{
                    transform: `scale(${zoom})`,
                    transformOrigin: "0 0",
                  }}
                >
                  <svg>
                    {definition.edges.map((edge, index) => {
                      const source = layout.find(
                          (item) => item.id === edge.source,
                        ),
                        target = layout.find((item) => item.id === edge.target);
                      if (!source || !target) return null;
                      const path = `M${source.x + 166},${source.y + 39} C${source.x + 195},${source.y + 39} ${target.x - 30},${target.y + 39} ${target.x},${target.y + 39}`;
                      return (
                        <g
                          key={`${edge.source}-${edge.target}-${index}`}
                          className={
                            selectedEdge === index ? "selectedEdge" : ""
                          }
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelectedEdge(index);
                            setSelectedId(null);
                          }}
                        >
                          <path className="edgeHit" d={path} />
                          <path d={path} />
                          <text
                            x={(source.x + target.x) / 2 + 80}
                            y={(source.y + target.y) / 2 + 32}
                          >
                            {edge.relation || "dependency"}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                  {layout.map((item) => {
                    const compiledNode = compilation?.nodes.find((candidate) => candidate.id === item.id);
                    const owner = item.config?.human_input
                      ? "human"
                      : item.config?.plugin
                        ? "plugin"
                        : item.config?.provider
                          ? "ai"
                          : "kernel";
                    return (
                      <button
                        key={item.id}
                        className={`pipelineNode ${selectedId === item.id ? "selected" : ""} ${mergeSources.includes(item.id) ? "mergeSelected" : ""} ${item.config?.unexplored || item.config?.preserved ? "unexplored" : ""}`}
                        data-owner={owner}
                        style={{ left: item.x, top: item.y }}
                        onClick={() => selectNode(item.id)}
                        onPointerDown={(event) => {
                          if (event.button !== 0) return;
                          event.stopPropagation();
                          setDrag({ id: item.id, clientX: event.clientX, clientY: event.clientY, x: item.x, y: item.y });
                        }}
                      >
                        <span className="nodeDrag">
                          <small>
                            {owner} · {item.type.replaceAll("_", " ")}
                          </small>
                          <i>⠿</i>
                        </span>
                        <b>{item.config?.label || item.id}</b>
                        <em>
                          {item.config?.provider ||
                            item.config?.plugin ||
                            (owner === "human" ? "Researcher input" : "Kernel")}
                        </em>
                        <span className="ports">
                          <i
                            className="inputPortHandle"
                            title={compiledNode?.interface.input_ports.map((port) => `${port.name}: ${port.schema_id}`).join("\n") || "Drop a connection here"}
                            onPointerDown={(event) => event.stopPropagation()}
                            onPointerUp={(event) => {
                              event.preventDefault();
                              event.stopPropagation();
                              if (connectFrom && connectFrom !== item.id) connectNodes(connectFrom, item.id);
                            }}
                          />
                          <i
                            className="outputPortHandle"
                            title={compiledNode?.interface.output_ports.map((port) => `${port.name}: ${port.schema_id}`).join("\n") || "Drag from here to another node"}
                            onPointerDown={(event) => {
                              event.preventDefault();
                              event.stopPropagation();
                              setConnectFrom(item.id);
                              setSelectedId(item.id);
                              notify("Drag to an input handle and release");
                            }}
                          />
                        </span>
                        {compiledNode && <span className="portLabels"><small>{compiledNode.interface.input_ports[0]?.name || ""}</small><small>{compiledNode.interface.output_ports[0]?.name || "result"}</small></span>}
                      </button>
                    );
                  })}
                </div>
              </div>
              {selected && (
                <aside className="nodeInspector editorInspector">
                  <header>
                    <div>
                      <span className="eyebrow">EDIT NODE</span>
                      <h3>{selected.config?.label || selected.id}</h3>
                    </div>
                    <button onClick={() => setSelectedId(null)}>
                      <X />
                    </button>
                  </header>
                  <label>
                    Step name
                    <input
                      value={selected.config?.label || ""}
                      onChange={(event) =>
                        mutateNode(selected.id, (item) => ({
                          ...item,
                          config: { ...item.config, label: event.target.value },
                        }))
                      }
                    />
                  </label>
                  <label>
                    Node type
                    <select
                      value={selected.type}
                      onChange={(event) =>
                        mutateNode(selected.id, (item) => ({
                          ...item,
                          type: event.target.value,
                        }))
                      }
                    >
                      {[
                        "formalization",
                        "hypothesis_generation",
                        "literature_search",
                        "counterexample_search",
                        "independent_review",
                        "synthesis",
                        "merge",
                        "plugin",
                        "human_review",
                        "report_generation",
                      ].map((type) => (
                        <option key={type}>{type}</option>
                      ))}
                    </select>
                  </label>
                  {selected.config?.provider && (
                    <>
                      <label>
                        Provider
                        <select
                          value={selected.config.provider}
                          onChange={(event) =>
                            mutateNode(selected.id, (item) => ({
                              ...item,
                              config: {
                                ...item.config,
                                provider: event.target.value,
                              },
                            }))
                          }
                        >
                          {[
                            "openai",
                            "anthropic",
                            "google",
                            "xai",
                            "deepseek",
                            "ollama",
                          ].map((provider) => (
                            <option key={provider}>{provider}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Model
                        <input
                          value={selected.config.model || ""}
                          onChange={(event) =>
                            mutateNode(selected.id, (item) => ({
                              ...item,
                              config: {
                                ...item.config,
                                model: event.target.value,
                              },
                            }))
                          }
                        />
                      </label>
                    </>
                  )}
                  {selected.config?.plugin && (
                    <label>
                      Plugin
                      <select
                        value={selected.config.plugin}
                        onChange={(event) =>
                          mutateNode(selected.id, (item) => ({
                            ...item,
                            config: {
                              ...item.config,
                              plugin: event.target.value,
                            },
                          }))
                        }
                      >
                        {plugins.map((plugin) => (
                          <option
                            key={plugin.plugin_id}
                            value={plugin.plugin_id}
                          >
                            {plugin.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  <label>
                    Instructions
                    <button type="button" className="inlineReference" onClick={() => mutateNode(selected.id, (item) => ({...item, config: {...item.config, instructions: `${item.config?.instructions || ""}\\researchquestion`, prompt: `${item.config?.instructions || ""}\\researchquestion`}}))}>
                      Insert <code>\researchquestion</code>
                    </button>
                    <textarea
                      value={
                        selected.config?.instructions ||
                        selected.config?.prompt ||
                        ""
                      }
                      onChange={(event) =>
                        mutateNode(selected.id, (item) => ({
                          ...item,
                          config: {
                            ...item.config,
                            instructions: event.target.value,
                            prompt: event.target.value,
                          },
                        }))
                      }
                    />
                  </label>
                  <label>
                    Merge behavior
                    <select
                      value={selected.config?.branch_behavior || "all"}
                      onChange={(event) =>
                        mutateNode(selected.id, (item) => ({
                          ...item,
                          config: {
                            ...item.config,
                            branch_behavior: event.target.value,
                            preserve_unselected: event.target.value === "vote",
                          },
                        }))
                      }
                    >
                      <option value="all">All dependencies</option>
                      <option value="any">Any successful dependency</option>
                      <option value="vote">
                        Vote and preserve alternatives
                      </option>
                      <option value="synthesis">Synthesize all branches</option>
                    </select>
                  </label>
                  {compilation && (() => {
                    const compiled = compilation.nodes.find((item) => item.id === selected.id);
                    return compiled ? <div className="compiledPreview">
                      <b>Compiled interface</b>
                      <small>Inputs: {compiled.interface.input_ports.map((port) => `${port.name} · ${port.schema_id}`).join(", ") || "none"}</small>
                      <small>Outputs: {compiled.interface.output_ports.map((port) => `${port.name} · ${port.schema_id}`).join(", ")}</small>
                      <b>Assurance requirements</b><small>{compiled.assurance.rules.join(" · ")}</small>
                      <b>Downstream expectations</b><small>{compiled.downstream.map((item) => `${item.target_pipeline_node_id}.${item.target_port}`).join(", ") || "final sink"}</small>
                    </div> : null;
                  })()}
                  <div className="inspectorActions">
                    <button
                      className={
                        mergeSources.includes(selected.id) ? "active" : ""
                      }
                      onClick={() => toggleMerge(selected.id)}
                    >
                      <CheckCircle2 />{" "}
                      {mergeSources.includes(selected.id)
                        ? "Included as merge input"
                        : "Add as merge input"}
                    </button>
                    <small className="connectionHint">Drag the output circle on the right edge to an input circle on another node.</small>
                    <button className="danger" onClick={removeNode}>
                      <Trash2 /> Delete node
                    </button>
                  </div>
                </aside>
              )}
              {selectedEdge !== null && (
                <aside className="nodeInspector editorInspector">
                  <header>
                    <div>
                      <span className="eyebrow">EDIT CONNECTION</span>
                      <h3>
                        {definition.edges[selectedEdge].source} →{" "}
                        {definition.edges[selectedEdge].target}
                      </h3>
                    </div>
                    <button onClick={() => setSelectedEdge(null)}>
                      <X />
                    </button>
                  </header>
                  <label>
                    Relationship
                    <select
                      value={
                        definition.edges[selectedEdge].relation || "dependency"
                      }
                      onChange={(event) =>
                        updateEdge("relation", event.target.value)
                      }
                    >
                      <option value="dependency">Dependency</option>
                      <option value="support">Support</option>
                      <option value="fallback">Fallback</option>
                      <option value="candidate">Vote candidate</option>
                      <option value="rejected">Rejected route</option>
                      <option value="preserved">
                        Preserved unexplored route
                      </option>
                    </select>
                  </label>
                  <label>
                    Condition
                    <input
                      value={definition.edges[selectedEdge].condition || ""}
                      onChange={(event) =>
                        updateEdge("condition", event.target.value)
                      }
                      placeholder="Optional routing condition"
                    />
                  </label>
                  <button className="danger" onClick={removeEdge}>
                    <Trash2 /> Delete connection
                  </button>
                </aside>
              )}
            </div>
          </section>
        )}
      </div>
      {showNode && (
        <Modal title="Add executable node" close={() => setShowNode(false)}>
          <form className="stack" onSubmit={addNode}>
            <label>
              Who performs this step?
              <select
                value={node.owner}
                onChange={(event) =>
                  setNode({ ...node, owner: event.target.value })
                }
              >
                <option value="human">
                  Researcher — direct independent contribution
                </option>
                <option value="ai">AI provider — autonomous contributor</option>
                <option value="plugin">
                  Plugin — deterministic or external tool
                </option>
              </select>
            </label>
            {node.owner === "ai" && (
              <label>
                Provider
                <select
                  value={node.provider}
                  onChange={(event) =>
                    setNode({ ...node, provider: event.target.value })
                  }
                >
                  {[
                    "openai",
                    "anthropic",
                    "google",
                    "xai",
                    "deepseek",
                    "ollama",
                  ].map((provider) => (
                    <option key={provider}>{provider}</option>
                  ))}
                </select>
              </label>
            )}
            {node.owner === "plugin" && (
              <>
              <label>Installed plugin
                <select
                  value={node.plugin}
                  onChange={(event) =>
                    setNode(emptyNode("plugin", event.target.value))
                  }
                >
                  {plugins.map((plugin) => (
                    <option key={plugin.plugin_id} value={plugin.plugin_id}>
                      {plugin.name} · {plugin.plugin_id}
                    </option>
                  ))}
                </select>
              </label>
              <label>Plugin input (JSON)
                <textarea className="codeInput" value={node.pluginInput} onChange={(event) => setNode({...node, pluginInput: event.target.value})} placeholder='{"expression":"sum(1/k**3, (k,1,n))","symbols":["k","n"]}' />
              </label>
              </>
            )}
            <label>
              Step name
              <input
                required
                value={node.label}
                onChange={(event) =>
                  setNode({ ...node, label: event.target.value })
                }
              />
            </label>
            <label>
              Instructions
              <button type="button" className="inlineReference" onClick={() => setNode({...node, instructions: `${node.instructions}\\researchquestion`})}>Insert <code>\researchquestion</code></button>
              <textarea
                required
                value={node.instructions}
                onChange={(event) =>
                  setNode({ ...node, instructions: event.target.value })
                }
              />
            </label>
            <button className="primary">
              <Plus /> Add to canvas
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}

const PipelinePage = EditablePipelinePage;

function RunsPage({ project, notify }) {
  const [goal, setGoal] = useState(
      "Investigate the project question with independent critique, falsification, and verification.",
    ),
    [mode, setMode] = useState("mock"),
    [pipelines, setPipelines] = useState([]),
    [pipelineId, setPipelineId] = useState(""),
    [run, setRun] = useState(null),
    [steps, setSteps] = useState([]),
    [human, setHuman] = useState({ summary: "", content: "", confidence: 0.8, contribution_type: "claim" });
  useEffect(() => {
    get(`/projects/${project.id}/pipelines`)
      .then((p) => {
        setPipelines(p);
        if (p[0]) setPipelineId(p[0].id);
      })
      .catch((e) => notify(e.message, "error"));
  }, [project.id]);
  useEffect(() => {
    if (!run) return;
    const refresh = () =>
      Promise.all([get(`/runs/${run.id}`), get(`/runs/${run.id}/steps`)])
        .then(([r, s]) => {
          setRun(r);
          setSteps(s);
        })
        .catch(() => {});
    refresh();
    const timer = setInterval(refresh, 2000);
    return () => clearInterval(timer);
  }, [run?.id]);
  async function launch() {
    if (!pipelineId)
      return notify("Choose or create a pipeline first", "error");
    try {
      if (mode === "live") {
        const selectedPipeline = pipelines.find((item) => item.id === pipelineId);
        const requiredProviders = [...new Set((selectedPipeline?.definition?.nodes || []).map((item) => item.config?.provider).filter(Boolean))];
        const readiness = await get("/providers/status?live=true");
        const missing = requiredProviders.filter((name) => {
          const item = readiness.find((candidate) => candidate.provider === name);
          return !item || !item.configured || ["unconfigured", "unavailable", "failed"].includes(item.health);
        });
        if (missing.length) {
          const local = missing.includes("ollama");
          return notify(local
            ? "Ollama is unavailable. Start the Ollama app, pull a model, then retry—or use Rehearsal/Human-led mode. Ollama does not accept an API or device key."
            : `${missing.join(", ")} API key${missing.length > 1 ? "s are" : " is"} not configured or reachable. Add credentials in Settings & API keys, or use Rehearsal/Human-led mode.`, "error");
        }
      }
      const r = await post(`/projects/${project.id}/runs`, {
        goal,
        pipeline_id: pipelineId,
        execution_mode: mode,
      });
      setRun(r);
      await post(`/runs/${r.id}/execute`);
      notify("Governed research run queued");
    } catch (e) {
      notify(e.message, "error");
    }
  }
  async function act(a) {
    try {
      setRun(await post(`/runs/${run.id}/${a}`));
    } catch (e) {
      notify(e.message, "error");
    }
  }
  async function contribute(e) {
    e.preventDefault();
    const pending = steps.find(
      (s) => s.status === "waiting_for_user",
    );
    if (!pending) return notify("No human checkpoint is waiting", "error");
    try {
      await post(`/runs/${run.id}/human-input`, {
        pipeline_node_id: pending.pipeline_node_id,
        payload: {
          ...human,
          contributed_by: "researcher",
          submitted_at: new Date().toISOString(),
        },
      });
      setHuman({ summary: "", content: "", confidence: 0.8, contribution_type: "claim" });
      notify("Contribution recorded; pipeline resumed");
    } catch (err) {
      notify(err.message, "error");
    }
  }
  const pending =
    run?.status === "waiting_for_user" &&
    steps.find(
      (s) => s.status === "waiting_for_user",
    );
  return (
    <>
      <Topbar project={project} title="Runs & autonomy" />
      <div className="page narrow">
        <section className="runComposer autonomyComposer">
          <div className="runIcon">
            <Play />
          </div>
          <div>
            <span className="eyebrow">CONTROLLED RESEARCH KERNEL</span>
            <h3>Choose how intelligence is allocated</h3>
            <p>
              AI can lead the investigation without taking away your ability to
              replace, pause, challenge, or formally verify any step.
            </p>
          </div>
          <label>
            Pipeline
            <select
              value={pipelineId}
              onChange={(e) => setPipelineId(e.target.value)}
            >
              <option value="">Choose a saved pipeline</option>
              {pipelines.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Execution policy
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="mock">Rehearsal — no paid model calls</option>
              <option value="live">
                AI-led — live providers with human gates
              </option>
              <option value="disabled">
                Human-led — AI nodes become checkpoints
              </option>
            </select>
          </label>
          <label className="goalField">
            Research objective
            <textarea value={goal} onChange={(e) => setGoal(e.target.value)} />
          </label>
          <button className="primary" onClick={launch}>
            <Zap size={17} /> Launch governed run
          </button>
        </section>
        <section className="assuranceGrid">
          <article>
            <Bot />
            <b>AI is the main contributor</b>
            <p>
              Generation, critique, synthesis, and tool selection can remain
              automated.
            </p>
          </article>
          <article>
            <Hand />
            <b>You retain authorship control</b>
            <p>
              Manual steps accept your proof, code, evidence, objections, and
              decisions.
            </p>
          </article>
          <article>
            <ShieldCheck />
            <b>Outputs are provisional</b>
            <p>
              Support, falsification, verification, and provenance remain
              distinct states.
            </p>
          </article>
        </section>
        {run && (
          <section className="runCard">
            <header>
              <div>
                <span className={`runState ${run.status}`} />
                <div>
                  <small>
                    RUN {run.id.slice(0, 8)} · {run.execution_mode}
                  </small>
                  <h3>{run.goal}</h3>
                </div>
              </div>
              <span className="statusPill">{run.status}</span>
            </header>
            <div className="stepLedger">
              {steps.length ? (
                steps.map((s) => (
                  <div key={s.id}>
                    <span className={`stepDot ${s.status}`} />
                    <b>{s.pipeline_node_id.replaceAll("_", " ")}</b>
                    <small>{s.output?.execution_mode || s.status}</small>
                  </div>
                ))
              ) : (
                <p>Waiting for the worker to claim this run…</p>
              )}
            </div>
            <footer>
              {run.status === "running" && (
                <button onClick={() => act("pause")}>Pause</button>
              )}
              {run.status === "paused" && (
                <button className="primary" onClick={() => act("resume")}>
                  <Play size={16} /> Resume
                </button>
              )}
              {!["cancelled", "completed", "failed"].includes(run.status) && (
                <button className="danger" onClick={() => act("cancel")}>
                  Cancel
                </button>
              )}
            </footer>
          </section>
        )}
        {pending && (
          <section className="humanGate">
            <header>
              <Hand />
              <div>
                <span className="eyebrow">RESEARCHER CHECKPOINT</span>
                <h3>{pending.pipeline_node_id.replaceAll("_", " ")}</h3>
              </div>
            </header>
            <p>
              The pipeline is paused without discarding completed work. Supply
              your independent reasoning, code, proof, evidence, or decision
              below.
            </p>
            <form className="stack" onSubmit={contribute}>
              <label>Contribution type
                <select value={human.contribution_type} onChange={(e) => setHuman({...human, contribution_type: e.target.value})}>
                  <option value="claim">Claim or conclusion</option><option value="hypothesis">Hypothesis</option><option value="evidence">Evidence</option><option value="computation">Computation</option><option value="formal_verification">Formal verification</option><option value="human_review">Review or decision</option>
                </select>
              </label>
              <label>
                Contribution summary
                <input
                  required
                  value={human.summary}
                  onChange={(e) =>
                    setHuman({ ...human, summary: e.target.value })
                  }
                />
              </label>
              <label>
                Independent work
                <textarea
                  required
                  value={human.content}
                  onChange={(e) =>
                    setHuman({ ...human, content: e.target.value })
                  }
                  placeholder="Enter your proof, Lean code, implementation, evidence, critique, or decision."
                />
              </label>
              <label>
                Confidence: {Number(human.confidence).toFixed(2)}
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={human.confidence}
                  onChange={(e) =>
                    setHuman({ ...human, confidence: Number(e.target.value) })
                  }
                />
              </label>
              <button className="primary">
                <CheckCircle2 /> Record contribution and resume
              </button>
            </form>
          </section>
        )}
      </div>
    </>
  );
}

function VerificationPage({ project, notify }) {
  const [tab, setTab] = useState("lean"),
    [input, setInput] = useState("theorem identity : 1 = 1 := by\n  rfl"),
    [result, setResult] = useState(null),
    [busy, setBusy] = useState(false);
  async function verify() {
    setBusy(true);
    setResult(null);
    try {
      let r;
      if (tab === "lean")
        r = await post(`/projects/${project.id}/tools/core.lean`, {
          payload: { theorem: input },
        });
      else if (tab === "sympy")
        r = await post(`/projects/${project.id}/tools/core.sympy`, {
          payload: { expression: input, symbols: ["x"], action: "simplify" },
        });
      else
        r = await post(
          `/projects/${project.id}/literature/resolve?${input.includes("/") ? "doi" : "arxiv_id"}=${encodeURIComponent(input)}`,
        );
      setResult(r);
      notify(
        tab === "literature" ? "Source resolved" : "Verification completed",
      );
    } catch (e) {
      notify(e.message, "error");
      setResult({ status: "failed", detail: e.message });
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Topbar project={project} title="Verification lab" />
      <div className="page narrow">
        <section className="verificationHero">
          <Scale />
          <div>
            <span className="eyebrow">
              DETERMINISTIC AND SOURCE-GROUNDED CHECKS
            </span>
            <h3>Do not ask a language model to certify itself.</h3>
            <p>
              Submit your own work or AI-generated work to independent
              compilers, symbolic computation, and scholarly metadata services.
            </p>
          </div>
        </section>
        <div className="verifyTabs">
          <button
            className={tab === "lean" ? "active" : ""}
            onClick={() => {
              setTab("lean");
              setInput("theorem identity : 1 = 1 := by\n  rfl");
            }}
          >
            <Code2 /> Lean 4
          </button>
          <button
            className={tab === "sympy" ? "active" : ""}
            onClick={() => {
              setTab("sympy");
              setInput("(x+1)**2-(x**2+2*x+1)");
            }}
          >
            <SquareFunction /> SymPy
          </button>
          <button
            className={tab === "literature" ? "active" : ""}
            onClick={() => {
              setTab("literature");
              setInput("2106.09685");
            }}
          >
            <FileSearch /> arXiv / DOI
          </button>
        </div>
        <section className="verifyWorkbench">
          <label>
            {tab === "lean"
              ? "Lean theorem and proof"
              : tab === "sympy"
                ? "Symbolic expression"
                : "arXiv identifier or DOI"}
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
          </label>
          <button className="primary" disabled={busy} onClick={verify}>
            {busy ? <RefreshCw className="spin" /> : <ShieldCheck />}{" "}
            {tab === "literature" ? "Resolve source" : "Run independent check"}
          </button>
          {result && (
            <div
              className={`verificationResult ${result.verified || result.status === "success" ? "passed" : ""}`}
            >
              <header>
                {result.verified || result.status === "success" ? (
                  <CheckCircle2 />
                ) : (
                  <Activity />
                )}
                <b>
                  {result.verification_status ||
                    result.status ||
                    "Source recorded"}
                </b>
              </header>
              <pre>{JSON.stringify(result, null, 2)}</pre>
            </div>
          )}
        </section>
        <p className="methodNote">
          <ShieldCheck /> A compiler success establishes only that the submitted
          formal statement type-checks. It does not establish that the
          formalization matches the intended real-world claim.
        </p>
      </div>
    </>
  );
}

function DiscoveryPage({ project, notify }) {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const load = () => get(`/projects/${project.id}/opportunities`).then(setItems);
  useEffect(() => { load().catch((error) => notify(error.message, "error")); }, [project.id]);
  async function scan() {
    setBusy(true);
    try { setItems(await post(`/discovery/scan?project_id=${project.id}`)); notify("Grounded opportunity scan complete"); }
    catch (error) { notify(error.message, "error"); }
    finally { setBusy(false); }
  }
  async function pipeline(id) {
    try { await post(`/opportunities/${id}/instantiate-pipeline`); notify("Suggested pipeline created and saved"); }
    catch (error) { notify(error.message, "error"); }
  }
  return <><Topbar project={project} title="Discovery" action={<button className="primary" onClick={scan} disabled={busy}><Compass />{busy ? "Scanning…" : "Scan grounded gaps"}</button>} />
    <div className="page narrow"><section className="explainPanel"><Compass /><div><span className="eyebrow">OPPORTUNITY ENGINE</span><h3>Find missing tests, proofs, replications, and changed-assumption routes.</h3><p>Novelty statements are scoped to indexed project records and never presented as universal priority claims.</p></div></section>
      <div className="pluginGrid">{items.map((item) => <article key={item.id}><Compass /><div><code>{item.opportunity_type.replaceAll("_", " ")}</code><h3>{item.title}</h3><p>{item.why_gap || item.rationale}</p><small>{item.novelty_scope}</small><button onClick={() => pipeline(item.id)}><GitBranch /> Create suggested pipeline</button></div></article>)}</div>
    </div></>;
}

const contractDefaults = {
  evidence_standard:
    "At least one directly relevant source or reproducible result must support each material claim.",
  falsification_criteria:
    "Actively search for counterexamples, contradictory findings, and assumptions that would make the claim fail.",
  source_requirements:
    "Prefer primary sources. Preserve stable identifiers and distinguish source statements from model interpretation.",
  verification_requirements:
    "Use Lean for formal statements and SymPy or reproducible computation for algebraic or numerical claims where applicable.",
  human_checkpoints:
    "The researcher approves the contract, resolves material conflicts, and signs off before a conclusion is treated as accepted.",
};

function ContractPage({ project, notify, onContinue }) {
  const [form, setForm] = useState(contractDefaults);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    get(`/projects/${project.id}/epistemic-contract`)
      .then((data) => {
        if (data.content) {
          setForm(data.content);
          setSaved(true);
        }
      })
      .catch((e) => notify(e.message, "error"));
  }, [project.id]);
  async function submit(e) {
    e.preventDefault();
    try {
      await api(`/projects/${project.id}/epistemic-contract`, {
        method: "PUT",
        body: JSON.stringify(form),
      });
      setSaved(true);
      notify("Epistemic Contract accepted");
    } catch (err) {
      notify(err.message, "error");
    }
  }
  return (
    <>
      <Topbar
        project={project}
        title="Epistemic contract"
        action={
          saved && (
            <button onClick={onContinue}>
              Continue to research plan <ArrowRight size={16} />
            </button>
          )
        }
      />
      <div className="page narrow">
        <section className="contractIntro">
          <Target />
          <div>
            <span className="eyebrow">RESEARCHER-DEFINED AUTHORITY</span>
            <h3>Decide what counts before the model answers.</h3>
            <p>
              This contract prevents the pipeline from quietly changing its
              standard of proof after seeing a convenient result.
            </p>
          </div>
        </section>
        <form className="contractForm" onSubmit={submit}>
          <label>
            <span>
              <b>01</b> Evidence standard
            </span>
            <textarea
              value={form.evidence_standard}
              onChange={(e) =>
                setForm({ ...form, evidence_standard: e.target.value })
              }
            />
          </label>
          <label>
            <span>
              <b>02</b> Falsification criteria
            </span>
            <textarea
              value={form.falsification_criteria}
              onChange={(e) =>
                setForm({ ...form, falsification_criteria: e.target.value })
              }
            />
          </label>
          <label>
            <span>
              <b>03</b> Source requirements
            </span>
            <textarea
              value={form.source_requirements}
              onChange={(e) =>
                setForm({ ...form, source_requirements: e.target.value })
              }
            />
          </label>
          <label>
            <span>
              <b>04</b> Independent verification
            </span>
            <textarea
              value={form.verification_requirements}
              onChange={(e) =>
                setForm({ ...form, verification_requirements: e.target.value })
              }
            />
          </label>
          <label>
            <span>
              <b>05</b> Human authority
            </span>
            <textarea
              value={form.human_checkpoints}
              onChange={(e) =>
                setForm({ ...form, human_checkpoints: e.target.value })
              }
            />
          </label>
          <button className="primary">
            <ShieldCheck size={17} />
            {saved ? "Update contract" : "Accept contract"}
          </button>
        </form>
      </div>
    </>
  );
}

function flattenResearchContent(value) {
  if (value == null) return [];
  if (typeof value === "string") return value.trim() ? [value.trim()] : [];
  if (typeof value === "number" || typeof value === "boolean") return [];
  if (Array.isArray(value)) return value.flatMap(flattenResearchContent);
  return Object.entries(value).flatMap(([key, item]) =>
    ["statement", "summary", "result", "conclusion", "answer", "explanation", "content", "detail", "reasoning"].includes(key)
      ? flattenResearchContent(item)
      : [],
  );
}

function buildResearchBrief(passport, graph, replay, mode = "executive") {
  const claims = passport?.claims || [];
  const nodes = graph?.nodes || [];
  const accepted = claims.filter((item) => ["accepted", "verified", "supported", "concluded"].includes(item.status));
  const challenged = claims.filter((item) => ["challenged", "rejected", "failed", "contradicted", "inconclusive"].includes(item.status));
  const finalNode = [...nodes].reverse().find((item) => item.kind === "conclusion") || [...nodes].reverse().find((item) => item.status === "accepted") || nodes.at(-1);
  const finalText = flattenResearchContent(finalNode?.content)[0] || accepted.at(-1)?.statement || challenged.at(-1)?.statement || "The investigation has not yet produced a recorded conclusion.";
  const verified = nodes.filter((item) => item.kind === "formal_verification" || item.status === "verified");
  const evidence = nodes.filter((item) => item.kind === "evidence" || item.kind === "computation");
  const failures = nodes.filter((item) => ["contradiction", "counterexample", "dead_end"].includes(item.kind) || ["failed", "rejected", "contradicted"].includes(item.status));
  const eventCount = replay?.event_count || replay?.events?.length || 0;
  const question = passport?.project?.question || "No research question recorded.";

  const common = {
    question,
    outcome: finalText,
    accepted,
    challenged,
    verified,
    evidence,
    failures,
    eventCount,
    nodes,
  };

  if (mode === "technical") {
    return {
      ...common,
      title: "Technical research brief",
      overview: `Pico Probe compiled this investigation into ${nodes.length} typed graph nodes and ${graph?.edges?.length || 0} semantic relationships. The run recorded ${eventCount} replay events, ${verified.length} verification artifacts, ${evidence.length} evidence or computation nodes, and ${failures.length} failed or contradictory routes.`,
      interpretation: accepted.length
        ? `${accepted.length} claim${accepted.length === 1 ? "" : "s"} reached an accepted, supported, or verified state. The strongest recorded outcome is: ${finalText}`
        : `No claim reached an accepted state. The terminal recorded outcome is: ${finalText}`,
      nextStep: challenged.length || failures.length
        ? "Inspect the challenged claims and failed branches before treating the terminal outcome as settled. Re-run the relevant verification nodes after changing assumptions or evidence requirements."
        : "Convert the strongest informal claim into a formal or reproducible verification step, then request researcher sign-off.",
    };
  }

  if (mode === "audit") {
    return {
      ...common,
      title: "Evidence and assurance brief",
      overview: `This brief is generated from the stored Claim Passport, Research Graph, and immutable replay—not from a new model response. The record contains ${passport?.assurance?.total_claims || claims.length} claims, ${passport?.assurance?.sources || 0} sources, ${passport?.assurance?.independent_checks || verified.length} independent checks, and ${passport?.assurance?.human_decisions || 0} human decisions.`,
      interpretation: `Recorded outcome: ${finalText}`,
      nextStep: passport?.contract
        ? "Compare the outcome against the attached Epistemic Contract, especially its evidence standard and falsification criteria, before final acceptance."
        : "Attach an Epistemic Contract before treating the result as an accepted research conclusion.",
    };
  }

  return {
    ...common,
    title: "Plain-language research summary",
    overview: `Pico Probe investigated “${question}” by preserving model proposals, computations, objections, verification attempts, and researcher decisions in one graph.`,
    interpretation: accepted.length
      ? `The investigation produced ${accepted.length} supported or accepted claim${accepted.length === 1 ? "" : "s"}. Its clearest recorded conclusion is: ${finalText}`
      : `The investigation did not establish a supported final claim. Its clearest recorded outcome is: ${finalText}`,
    nextStep: failures.length || challenged.length
      ? "The most useful next step is to inspect the failed or challenged route, identify the blocking assumption, and launch a revised branch rather than repeating the same pipeline."
      : "The most useful next step is to add an independent symbolic, formal, or numerical check and then record researcher sign-off.",
  };
}

function ResearchBriefModal({ passport, graph, replay, close, notify }) {
  const [mode, setMode] = useState("executive");
  const brief = useMemo(() => buildResearchBrief(passport, graph, replay, mode), [passport, graph, replay, mode]);
  const text = `${brief.title}\n\nResearch question\n${brief.question}\n\nSummary\n${brief.overview}\n\nOutcome\n${brief.interpretation}\n\nRecommended next step\n${brief.nextStep}`;
  async function copyBrief() {
    try {
      await navigator.clipboard.writeText(text);
      notify("Research summary copied");
    } catch {
      notify("Could not access the clipboard", "error");
    }
  }
  return (
    <Modal wide title="Research summary" close={close}>
      <div className="researchBrief">
        <header className="briefHeader">
          <div>
            <span className="eyebrow">ONE-PAGE INTERPRETATION</span>
            <h3>{brief.title}</h3>
            <p>Generated from stored research artifacts so it remains available even when no AI provider is configured.</p>
          </div>
          <div className="briefActions">
            <select value={mode} onChange={(event) => setMode(event.target.value)} aria-label="Summary style">
              <option value="executive">Plain language</option>
              <option value="technical">Technical</option>
              <option value="audit">Evidence & assurance</option>
            </select>
            <button onClick={copyBrief}><Copy size={15} /> Copy</button>
          </div>
        </header>

        <section className="briefQuestion">
          <span>Research question</span>
          <h4>{brief.question}</h4>
        </section>

        <div className="briefMetrics">
          <article><b>{brief.nodes.length}</b><span>graph nodes</span></article>
          <article><b>{brief.evidence.length}</b><span>evidence / computations</span></article>
          <article><b>{brief.verified.length}</b><span>verification records</span></article>
          <article><b>{brief.failures.length}</b><span>failed or contrary routes</span></article>
        </div>

        <section className="briefSection">
          <span className="eyebrow">WHAT HAPPENED</span>
          <p>{brief.overview}</p>
        </section>
        <section className="briefSection outcome">
          <span className="eyebrow">RECORDED OUTCOME</span>
          <p>{brief.interpretation}</p>
        </section>
        <section className="briefSection">
          <span className="eyebrow">RECOMMENDED NEXT STEP</span>
          <p>{brief.nextStep}</p>
        </section>

        {(brief.accepted.length > 0 || brief.challenged.length > 0) && (
          <div className="briefClaims">
            {brief.accepted.length > 0 && <section><h4>Supported claims</h4>{brief.accepted.slice(0, 4).map((item) => <p key={item.id}><CheckCircle2 size={15} /> {item.statement}</p>)}</section>}
            {brief.challenged.length > 0 && <section><h4>Unresolved or challenged</h4>{brief.challenged.slice(0, 4).map((item) => <p key={item.id}><Activity size={15} /> {item.statement}</p>)}</section>}
          </div>
        )}

        <footer className="briefFooter">
          <ShieldCheck size={16} />
          <span>This summary explains the stored record. It does not upgrade an unverified claim into a proof.</span>
        </footer>
      </div>
    </Modal>
  );
}

function PassportPage({ project, notify }) {
  const [passport, setPassport] = useState(null);
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [replay, setReplay] = useState({ events: [], event_count: 0 });
  const [showBrief, setShowBrief] = useState(false);
  const load = () =>
    Promise.all([
      get(`/projects/${project.id}/claim-passport`),
      get(`/projects/${project.id}/graph`),
      get(`/projects/${project.id}/replay`),
    ])
      .then(([passportData, graphData, replayData]) => {
        setPassport(passportData);
        setGraph(graphData);
        setReplay(replayData);
      })
      .catch((e) => notify(e.message, "error"));
  useEffect(() => {
    void load();
  }, [project.id]);
  if (!passport)
    return (
      <>
        <Topbar project={project} title="Claim passport" />
        <div className="page narrow">
          <div className="empty">
            <RefreshCw className="spin" />
          </div>
        </div>
      </>
    );
  const a = passport.assurance;
  return (
    <>
      <Topbar
        project={project}
        title="Claim passport"
        action={
          <>
            <button className="primary" onClick={() => setShowBrief(true)}>
              <Compass size={16} /> Research summary
            </button>
            <button onClick={() => window.print()}>
              <FileCheck2 size={16} /> Print passport
            </button>
          </>
        }
      />
      <div className="page narrow">
        <section className="passportHero">
          <div>
            <span className="eyebrow">INSPECTABLE RESEARCH RECORD</span>
            <h3>{passport.project.title}</h3>
            <p>{passport.project.question}</p>
          </div>
          <div className="passportSeal">
            <span>{a.independent_checks}</span>
            <small>
              independent
              <br />
              checks
            </small>
          </div>
        </section>
        <section className="summaryPrompt">
          <Compass />
          <div>
            <b>Need the result, not the raw record?</b>
            <p>Open a one-page summary of what happened, what the pipeline concluded, what remains unresolved, and what to do next.</p>
          </div>
          <button onClick={() => setShowBrief(true)}>Open research summary <ArrowRight size={15} /></button>
        </section>
        <div className="passportStats">
          <article>
            <b>{a.total_claims}</b>
            <span>Claims</span>
          </article>
          <article>
            <b>{a.sources}</b>
            <span>Evidence sources</span>
          </article>
          <article>
            <b>{a.challenges}</b>
            <span>Challenges</span>
          </article>
          <article>
            <b>{a.human_decisions}</b>
            <span>Human decisions</span>
          </article>
        </div>
        {passport.contract ? (
          <section className="passportContract">
            <Target />
            <div>
              <b>Epistemic Contract attached</b>
              <p>{passport.contract.evidence_standard}</p>
            </div>
          </section>
        ) : (
          <section className="passportWarning">
            No Epistemic Contract has been accepted for this investigation.
          </section>
        )}
        <section className="passportClaims">
          <header>
            <div>
              <span className="eyebrow">CLAIM REGISTER</span>
              <h3>What is known—and what is not</h3>
            </div>
            <button onClick={load}>
              <RefreshCw size={15} /> Refresh
            </button>
          </header>
          {passport.claims.length ? (
            passport.claims.map((claim, index) => (
              <article key={claim.id}>
                <div className="claimIndex">
                  {String(index + 1).padStart(2, "0")}
                </div>
                <div className="claimMain">
                  <span className={`claimState ${claim.status}`}>
                    {claim.status.replaceAll("_", " ")}
                  </span>
                  <h4>{claim.statement}</h4>
                  {claim.assumptions.length > 0 && (
                    <p>Assumes: {claim.assumptions.join("; ")}</p>
                  )}
                  <div className="claimChecks">
                    <span>
                      <FileSearch /> {claim.supporting_evidence} evidence
                    </span>
                    <span>
                      <Activity /> {claim.challenges} challenges
                    </span>
                    <span>
                      <ShieldCheck /> {claim.independent_checks} checks
                    </span>
                  </div>
                </div>
              </article>
            ))
          ) : (
            <div className="empty compact">
              <p>
                No claims have been added yet. Run the research plan or add a
                claim in the graph.
              </p>
            </div>
          )}
        </section>
        <p className="passportDisclaimer">{passport.disclaimer}</p>
      </div>
      {showBrief && <ResearchBriefModal passport={passport} graph={graph} replay={replay} close={() => setShowBrief(false)} notify={notify} />}
    </>
  );
}

const tourSteps = [
  {
    title: "Enter an open research question",
    body: "The demo begins with a real mathematical problem, not a prewritten answer. Pico Probe will preserve competing routes, evidence, failures, and final researcher sign-off.",
    inputLabel: "Research question",
    typed:
      "Given P(x)=Σₜ(sₜ·x)ᵈ with sₜ∈{±1}ᵐ, can we characterize and count every surviving monomial without expanding each multinomial?",
    page: "library",
    target: '[data-tour="new"]',
    action: "demo",
    dwell: 5200,
  },
  {
    title: "Inspect the initial research graph",
    body: "Pico Probe creates a persistent question node and records the investigation before any model proposes an answer.",
    inputLabel: "Kernel instruction",
    typed:
      "Keep the conclusion unknown. Record each proposal as a typed artifact with provenance and explicit dependencies.",
    page: "graph",
    target: '[data-tour="graph"]',
    stage: 1,
    dwell: 4200,
  },
  {
    title: "Define the assurance contract",
    body: "The researcher specifies what evidence is required before the system may promote a pattern into a conclusion.",
    inputLabel: "Acceptance criterion",
    typed:
      "Require an explicit survival criterion, a counting formula, independent finite examples, boundary conditions, and researcher approval.",
    page: "contract",
    target: '[data-tour="contract"]',
    stage: 2,
    dwell: 4600,
  },
  {
    title: "Compile a custom multi-model pipeline",
    body: "The saved canvas uses three independent model routes, a comparator, synthesis, skeptical review, SymPy, Lean, and human sign-off. The pipeline remains editable after the rehearsal.",
    inputLabel: "Comparator configuration",
    typed:
      "Compare structural, harmonic-analysis, and computational routes. Elect the strongest derivation without deleting rejected approaches.",
    page: "pipeline",
    target: '[data-tour="pipeline"]',
    stage: 2,
    dwell: 5600,
  },
  {
    title: "Run independent research routes",
    body: "OpenAI, Claude, and Gemini contribute separate proposals. Pico Probe stores each branch before the comparator selects a theoretical route.",
    inputLabel: "Researcher instruction",
    typed:
      "Preserve sign-profile grouping, Walsh character analysis, and brute-force expansion as independent branches.",
    page: "runs",
    target: '[data-tour="runs"]',
    stage: 3,
    dwell: 5000,
  },
  {
    title: "Challenge the emerging claim",
    body: "A skeptical route records a non-affine counterexample boundary while character orthogonality supplies evidence for the affine case.",
    inputLabel: "Independent critique",
    typed:
      "Try to break factorization outside affine binary subspaces. Do not generalize the parity theorem to arbitrary sign configurations.",
    page: "graph",
    target: '[data-tour="graph"]',
    stage: 4,
    dwell: 5000,
  },
  {
    title: "Verify with independent tools",
    body: "SymPy checks finite examples and Lean checks scoped parity lemmas. Tool output is evidence, not permission for the model to certify itself.",
    inputLabel: "Verification request",
    typed:
      "Check the degree-4 eight-expansion cube predicts exactly 10 survivors; separately type-check the parity factorization lemmas.",
    page: "verification",
    target: '[data-tour="verification"]',
    stage: 5,
    dwell: 5600,
  },
  {
    title: "Review the claim passport",
    body: "The final claim exposes its assumptions, evidence, challenges, independent checks, provenance, and unresolved scope before researcher approval.",
    inputLabel: "Researcher sign-off",
    typed:
      "Approve the qualified affine conclusion; retain the converse classification and arbitrary non-affine enumeration as open questions.",
    page: "passport",
    target: '[data-tour="passport"]',
    stage: 6,
    dwell: 5200,
  },
  {
    title: "Replay the complete investigation",
    body: "Pico Probe preserves the evolution of the research itself: proposals, comparisons, computations, rejected routes, verification, and human decisions.",
    inputLabel: "Replay objective",
    typed:
      "Reconstruct how the conclusion was generated, challenged, verified, bounded, and accepted—not merely the final answer.",
    page: "replay",
    target: '[data-tour="replay"]',
    dwell: 5200,
  },
];

function TypingField({ item, onComplete }) {
  const [typed, setTyped] = useState("");
  useEffect(() => {
    let index = 0;
    const timer = setInterval(() => {
      index += 3;
      const value = item.typed.slice(0, index);
      setTyped(value);
      if (index >= item.typed.length) {
        clearInterval(timer);
        onComplete?.();
      }
    }, 17);
    return () => clearInterval(timer);
  }, [item.typed]);
  return (
    <label className="tourTyping">
      <span>
        <Hand size={13} /> {item.inputLabel}
      </span>
      <textarea readOnly value={typed} aria-label={item.inputLabel} />
      <i className={typed.length < item.typed.length ? "typing" : ""} />
    </label>
  );
}

function Tutorial({
  step,
  setStep,
  project,
  setPage,
  onDemo,
  onAdvance,
  onClose,
}) {
  const item = tourSteps[step];
  const [playing, setPlaying] = useState(true);
  const [completedTypingStep, setCompletedTypingStep] = useState(null);
  const typingDone = completedTypingStep === step;
  const [cursor, setCursor] = useState({ x: 36, y: 90, visible: false });
  const [clicking, setClicking] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (item.page && (project || item.page === "library")) setPage(item.page);
  }, [step]);

  useEffect(() => {
    const move = () => {
      const target = document.querySelector(item.target);
      if (!target) {
        setCursor({ x: window.innerWidth - 80, y: 96, visible: true });
        return;
      }
      const rect = target.getBoundingClientRect();
      setCursor({
        x: rect.left + Math.min(rect.width * 0.66, rect.width - 10),
        y: rect.top + rect.height * 0.55,
        visible: true,
      });
      target.classList.add("tourTarget");
      return () => target.classList.remove("tourTarget");
    };
    const cleanup = move();
    const timer = setTimeout(move, 180);
    window.addEventListener("resize", move);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("resize", move);
      cleanup?.();
    };
  }, [step, item.target, item.page, project]);

  async function next() {
    if (busy) return;
    setBusy(true);
    setClicking(true);
    await new Promise((resolve) => setTimeout(resolve, 340));
    try {
      if (item.action === "demo" && !project) await onDemo();
      else if (item.stage) await onAdvance(item.stage, project);

      if (step === tourSteps.length - 1) {
        localStorage.setItem("picoprobe_tutorial_seen", "1");
        onClose();
        return;
      }
      setStep(step + 1);
    } finally {
      setClicking(false);
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!playing || !typingDone || busy) return;
    const timer = setTimeout(next, Math.max(1100, item.dwell - item.typed.length * 17));
    return () => clearTimeout(timer);
  }, [playing, typingDone, step, busy]);

  return (
    <div className="tourLayer" aria-live="polite">
      <div
        className={`magicCursor ${cursor.visible ? "visible" : ""} ${clicking ? "clicking" : ""}`}
        style={{ transform: `translate3d(${cursor.x}px, ${cursor.y}px, 0)` }}
        aria-hidden="true"
      >
        <span />
        <Hand size={25} />
      </div>

      <section className="tourDock">
        <header>
          <div>
            <span className="tourLive"><i /> GUIDED RESEARCH REHEARSAL</span>
            <b>{String(step + 1).padStart(2, "0")} / {String(tourSteps.length).padStart(2, "0")}</b>
          </div>
          <div className="tourControls">
            <button onClick={() => setPlaying(!playing)} aria-label={playing ? "Pause demo" : "Resume demo"}>
              {playing ? <Pause size={15} /> : <Play size={15} />}
            </button>
            <button onClick={onClose} aria-label="Close demo"><X size={16} /></button>
          </div>
        </header>
        <div className="tourProgress"><i style={{ width: `${((step + 1) / tourSteps.length) * 100}%` }} /></div>
        <h3>{item.title}</h3>
        <p>{item.body}</p>
        <TypingField key={step} item={item} onComplete={() => setCompletedTypingStep(step)} />
        <footer>
          <span>{playing ? (typingDone ? "Executing next research action…" : "Typing configuration…") : "Demo paused"}</span>
          <div>
            {step > 0 && <button onClick={() => setStep(step - 1)}>Back</button>}
            <button className="primary" onClick={next} disabled={busy}>
              {step === tourSteps.length - 1 ? "Finish" : "Next"} <ArrowRight size={14} />
            </button>
          </div>
        </footer>
      </section>
    </div>
  );
}

function ReplayPage({ project, notify }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    get(`/projects/${project.id}/replay`)
      .then(setData)
      .catch((e) => notify(e.message, "error"));
  }, [project.id]);
  return (
    <>
      <Topbar project={project} title="Research replay" />
      <div className="page narrow">
        <div className="replayIntro">
          <Radio />
          <div>
            <h3>Immutable investigation timeline</h3>
            <p>Reconstruct every meaningful mutation from the event store.</p>
          </div>
          <span>{data?.event_count || 0} events</span>
        </div>
        <div className="timeline">
          {data?.events.map((e, i) => (
            <article key={e.id}>
              <div className="timeMark">
                <span />
                {i < data.events.length - 1 && <i />}
              </div>
              <div>
                <header>
                  <b>{e.event_type.replaceAll("_", " ")}</b>
                  <time>{fmt(e.timestamp)}</time>
                </header>
                <p>Actor: {e.actor_id}</p>
                <pre>{JSON.stringify(e.payload, null, 2)}</pre>
              </div>
            </article>
          ))}
        </div>
      </div>
    </>
  );
}

function PublicLibraryPage({ notify }) {
  const [projects, setProjects] = useState([]);
  const [filter, setFilter] = useState("");
  const [snapshot, setSnapshot] = useState(null);
  useEffect(() => {
    get("/public/projects")
      .then(setProjects)
      .catch((error) => notify(error.message, "error"));
  }, []);
  const visible = projects.filter((project) =>
    `${project.title} ${project.question} ${(project.tags || []).join(" ")}`
      .toLowerCase()
      .includes(filter.toLowerCase()),
  );
  async function inspect(project) {
    try {
      setSnapshot(await get(`/public/snapshots/${project.snapshot_id}`));
    } catch (error) {
      notify(error.message, "error");
    }
  }
  return (
    <>
      <Topbar title="Public library" />
      <div className="page">
        <section className="explainPanel">
          <Globe />
          <div>
            <span className="eyebrow">COMMUNITY RESEARCH</span>
            <h3>Published investigations are immutable snapshots.</h3>
            <p>
              Explore the exact claim graph, assurance contract, saved
              pipelines, sources, discarded routes, and replay that an author
              chose to publish. Private work never appears here until its owner
              creates a snapshot.
            </p>
          </div>
        </section>
        <div className="sectionHead">
          <div>
            <h3>Community investigations</h3>
            <p>{projects.length} published snapshots</p>
          </div>
          <div className="filter">
            <Search />
            <input
              aria-label="Filter public investigations"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder="Filter community research"
            />
          </div>
        </div>
        {visible.length ? (
          <div className="projectGrid">
            {visible.map((project) => (
              <button
                className="projectCard"
                key={project.id}
                onClick={() => inspect(project)}
              >
                <div className="projectIcon">
                  <Globe />
                </div>
                <div className="statusPill">
                  <span /> public snapshot
                </div>
                <h3>{project.title}</h3>
                <p>{project.question}</p>
                <div className="cardMeta">
                  <span>
                    {(project.tags || []).slice(0, 2).join(" · ") ||
                      "community"}
                  </span>
                  <span>{fmt(project.updated_at)}</span>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="empty">
            <Globe />
            <h3>No matching public investigations</h3>
            <p>
              Publish one of your private investigations from its Claim Graph to
              demonstrate the community library.
            </p>
          </div>
        )}
      </div>
      {snapshot && (
        <Modal
          wide
          title={snapshot.payload.project.title}
          close={() => setSnapshot(null)}
        >
          <div className="snapshotView">
            <div className="snapshotMeta">
              <span>Snapshot v{snapshot.version}</span>
              <code>{snapshot.integrity_hash.slice(0, 20)}…</code>
            </div>
            <section>
              <h4>Research question</h4>
              <p>{snapshot.payload.project.question}</p>
            </section>
            <section>
              <h4>Assurance contract</h4>
              <pre>
                {JSON.stringify(
                  snapshot.payload.epistemic_contract || "Not attached",
                  null,
                  2,
                )}
              </pre>
            </section>
            <section>
              <h4>Claim graph</h4>
              <p>
                {snapshot.payload.graph.nodes.length} nodes ·{" "}
                {snapshot.payload.graph.edges.length} relationships
              </p>
              <pre>{JSON.stringify(snapshot.payload.graph, null, 2)}</pre>
            </section>
            <section>
              <h4>Research pipelines</h4>
              <pre>
                {JSON.stringify(snapshot.payload.pipelines || [], null, 2)}
              </pre>
            </section>
            <section>
              <h4>Replay</h4>
              <p>{snapshot.payload.replay.length} immutable events</p>
            </section>
          </div>
        </Modal>
      )}
    </>
  );
}

function PluginsPage({ notify }) {
  const [plugins, setPlugins] = useState([]);
  const [packages, setPackages] = useState([]);
  const [show, setShow] = useState(false);
  const [manifest, setManifest] = useState(
    '{\n  "plugin_id": "community.example",\n  "name": "Example research tool",\n  "version": "1.0.0",\n  "capabilities": ["research"]\n}',
  );
  const [file, setFile] = useState(null);
  const load = () =>
    Promise.all([get("/plugins"), get("/plugin-packages")]).then(
      ([builtIn, installed]) => {
        setPlugins(builtIn);
        setPackages(installed);
      },
    );
  useEffect(() => {
    load().catch((error) => notify(error.message, "error"));
  }, []);
  async function install(event) {
    event.preventDefault();
    if (!file) return notify("Choose a signed ZIP package", "error");
    const body = new FormData();
    body.append("manifest", manifest);
    body.append("package", file);
    body.append("source", "competition-ui");
    try {
      await api("/plugin-packages", { method: "POST", body });
      setShow(false);
      await load();
      notify("Plugin package uploaded for signature and administrator review");
    } catch (error) {
      notify(error.message, "error");
    }
  }
  return (
    <>
      <Topbar
        title="Plugins"
        action={
          <button className="primary" onClick={() => setShow(true)}>
            <Upload /> Add plugin package
          </button>
        }
      />
      <div className="page">
        <section className="explainPanel">
          <Plug />
          <div>
            <span className="eyebrow">REPLACEABLE RESEARCH CAPABILITIES</span>
            <h3>Plugins perform deterministic or specialized steps.</h3>
            <p>
              Lean, SymPy, simulations, and experiments are installed
              capabilities. Add them to any pipeline through “Who performs this
              step?”. Uploaded community packages are checksum-verified,
              signature-checked, administrator-approved, and sandboxed before
              execution.
            </p>
          </div>
        </section>
        <div className="pluginGrid">
          {plugins.map((plugin) => (
            <article key={plugin.plugin_id}>
              <Plug />
              <div>
                <h3>{plugin.name}</h3>
                <code>
                  {plugin.plugin_id} · v{plugin.version}
                </code>
                <p>{(plugin.capabilities || []).join(" · ")}</p>
              </div>
              <span className="statusPill">installed</span>
            </article>
          ))}
        </div>
        {packages.length > 0 && (
          <section className="packageList">
            <h3>Uploaded packages</h3>
            {packages.map((item) => (
              <div key={item.id}>
                <code>
                  {item.plugin_id} · {item.version}
                </code>
                <span className="statusPill">
                  {item.approval_status || item.status}
                </span>
              </div>
            ))}
          </section>
        )}
      </div>
      {show && (
        <Modal
          wide
          title="Add a signed plugin package"
          close={() => setShow(false)}
        >
          <form className="stack" onSubmit={install}>
            <div className="formNote">
              <ShieldCheck /> Contest safety: uploads are never executable
              merely because they were uploaded. The backend verifies the
              declared checksum/signature and requires approval before enabling
              sandboxed execution.
            </div>
            <label>
              Plugin manifest JSON
              <textarea
                className="codeInput"
                value={manifest}
                onChange={(event) => setManifest(event.target.value)}
              />
            </label>
            <label>
              Signed ZIP package
              <input
                required
                type="file"
                accept=".zip,application/zip"
                onChange={(event) => setFile(event.target.files[0])}
              />
            </label>
            <button className="primary">
              <Upload /> Upload for review
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}

function SettingsPage({ notify }) {
  const providers = ["openai", "anthropic", "google", "xai", "deepseek", "ollama"];
  const [status, setStatus] = useState([]);
  const [credentials, setCredentials] = useState([]);
  const [provider, setProvider] = useState("openai");
  const [key, setKey] = useState("");
  const [billing, setBilling] = useState(false);
  const [ollama, setOllama] = useState({
    reachable: false,
    running: false,
    installed: false,
    binary_found: false,
    base_url: "http://127.0.0.1:11434",
    default_model: "",
    models: [],
    approved_model_presets: [],
  });
  const [ollamaBusy, setOllamaBusy] = useState("");
  const [ollamaModel, setOllamaModel] = useState("");

  const load = () =>
    Promise.all([
      get("/providers/status"),
      get("/user/api-keys"),
      get("/providers/ollama/status").catch(() => null),
    ]).then(([providersStatus, keys, ollamaStatus]) => {
      setStatus(providersStatus);
      setCredentials(keys.credentials);
      if (ollamaStatus) {
        setOllama(ollamaStatus);
        setOllamaModel(
          ollamaStatus.default_model || ollamaStatus.models?.[0] || "",
        );
      }
    });

  useEffect(() => {
    load().catch((error) => notify(error.message, "error"));
  }, []);

  async function saveKey(event) {
    event.preventDefault();
    try {
      await post("/user/api-key", { provider, api_key: key });
      setKey("");
      await load();
      notify(`${provider} key encrypted in the server vault`);
    } catch (error) {
      notify(error.message, "error");
    }
  }

  async function remove(name) {
    try {
      await api(`/user/api-key/${name}`, { method: "DELETE" });
      await load();
      notify(`${name} credential removed`);
    } catch (error) {
      notify(error.message, "error");
    }
  }

  async function configureOllama(event) {
    event.preventDefault();
    setOllamaBusy("save");
    try {
      await post("/providers/ollama/configure", {
        base_url: ollama.base_url,
        default_model: ollamaModel || null,
      });
      await load();
      notify("Ollama configuration saved");
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setOllamaBusy("");
    }
  }

  async function checkOllama() {
    setOllamaBusy("check");
    try {
      const result = await get("/providers/ollama/status");
      setOllama(result);
      if (!ollamaModel) setOllamaModel(result.default_model || result.models?.[0] || "");
      notify(result.reachable ? "Ollama is reachable" : "Ollama is not reachable", result.reachable ? "success" : "error");
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setOllamaBusy("");
    }
  }

  async function startOllama() {
    setOllamaBusy("start");
    try {
      const result = await post("/providers/ollama/start");
      setOllama((current) => ({ ...current, ...result }));
      notify(result.message || "Ollama started");
    } catch (error) {
      notify(`${error.message}. If Pico Probe is running in Docker, start the Ollama app on your Mac instead.`, "error");
    } finally {
      setOllamaBusy("");
    }
  }

  async function pullOllama() {
    if (!ollamaModel) return notify("Choose a model first", "error");
    setOllamaBusy("pull");
    try {
      await post("/providers/ollama/pull-model", {
        model: ollamaModel,
        confirmed: true,
      });
      await load();
      notify(`${ollamaModel} downloaded through Ollama`);
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setOllamaBusy("");
    }
  }

  async function testOllama() {
    if (!ollamaModel) return notify("Choose an installed model first", "error");
    setOllamaBusy("test");
    try {
      const result = await post("/providers/ollama/test", { model: ollamaModel });
      notify(result.success ? `Ollama ${ollamaModel} passed the structured-output test` : "Ollama test failed", result.success ? "success" : "error");
    } catch (error) {
      notify(error.message, "error");
    } finally {
      setOllamaBusy("");
    }
  }

  return (
    <>
      <Topbar title="Settings & providers" />
      <div className="page">
        <section className="settingsGrid">
          <article className="settingsCard">
            <header>
              <KeyRound />
              <div>
                <h3>Private API-key vault</h3>
                <p>Bring your own model credentials for cloud live runs.</p>
              </div>
            </header>
            <div className="securityCallout">
              <ShieldCheck /> Keys are sent once over the authenticated API,
              encrypted by the backend vault, and never returned to this
              interface or inserted into prompts.
            </div>
            {provider === "ollama" ? (
              <form className="stack" onSubmit={configureOllama}>
                <label>
                  Provider
                  <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                    {providers.map((name) => <option key={name}>{name}</option>)}
                  </select>
                </label>
                <div className="securityCallout">
                  <Bot /> Ollama runs locally and does not use an API key. Enter the local Ollama HTTP endpoint and model name instead.
                </div>
                <label>
                  Ollama base URL
                  <input
                    value={ollama.base_url || ""}
                    onChange={(event) => setOllama({ ...ollama, base_url: event.target.value })}
                    placeholder="http://127.0.0.1:11434"
                  />
                  <small className="fieldHint">Use http://127.0.0.1:11434 when Pico Probe runs directly on your machine. Use http://host.docker.internal:11434 when the backend runs in Docker.</small>
                </label>
                <label>
                  Ollama model
                  <input
                    value={ollamaModel}
                    onChange={(event) => setOllamaModel(event.target.value)}
                    placeholder="llama3.1:8b"
                  />
                </label>
                <div className="ollamaActions">
                  <button type="button" onClick={checkOllama} disabled={Boolean(ollamaBusy)}><RefreshCw /> {ollamaBusy === "check" ? "Checking…" : "Check"}</button>
                  <button type="button" onClick={pullOllama} disabled={Boolean(ollamaBusy) || !ollamaModel}><DownloadIcon /> {ollamaBusy === "pull" ? "Downloading…" : "Pull model"}</button>
                  <button type="button" onClick={testOllama} disabled={Boolean(ollamaBusy) || !ollamaModel}><Zap /> {ollamaBusy === "test" ? "Testing…" : "Test model"}</button>
                  <button className="primary" disabled={Boolean(ollamaBusy)}><Save /> Save Ollama</button>
                </div>
              </form>
            ) : (
              <form className="stack" onSubmit={saveKey}>
                <label>
                  Provider
                  <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                    {providers.map((name) => <option key={name}>{name}</option>)}
                  </select>
                </label>
                <label>
                  API key
                  <input type="password" required autoComplete="off" value={key}
                    onChange={(event) => setKey(event.target.value)}
                    placeholder="Paste once; the UI cannot retrieve it" />
                </label>
                <button className="primary"><Lock /> Store securely</button>
              </form>
            )}
            <div className="credentialList">
              {credentials.map((credential) => (
                <div key={credential.provider}>
                  <span><b>{credential.provider}</b><small>{credential.key_fingerprint} · {credential.status}</small></span>
                  <button aria-label={`Delete ${credential.provider} key`} onClick={() => remove(credential.provider)}><Trash2 /></button>
                </div>
              ))}
            </div>
          </article>

          <article className="settingsCard ollamaCard">
            <header>
              <Bot />
              <div>
                <h3>Configure local Ollama</h3>
                <p>Use local models with no API key and no provider-token cost.</p>
              </div>
            </header>
            <div className={`ollamaStatus ${ollama.reachable ? "connected" : "offline"}`}>
              <i />
              <div>
                <b>{ollama.reachable ? "Ollama connected" : "Ollama not reachable"}</b>
                <small>
                  {ollama.reachable
                    ? `${ollama.version || ollama.binary_version || "local service"} · ${ollama.models?.length || 0} model(s)`
                    : ollama.binary_found
                      ? "Ollama is installed on the backend machine but not running."
                      : "Install/start Ollama, then check again."}
                </small>
              </div>
            </div>
            <form className="stack" onSubmit={configureOllama}>
              <label>
                Ollama base URL
                <input value={ollama.base_url || ""}
                  onChange={(event) => setOllama({ ...ollama, base_url: event.target.value })}
                  placeholder="http://127.0.0.1:11434" />
                <small className="fieldHint">Direct Mac run: 127.0.0.1. Docker on macOS: host.docker.internal.</small>
              </label>
              <label>
                Default model
                <select value={ollamaModel} onChange={(event) => setOllamaModel(event.target.value)}>
                  <option value="">Choose a model</option>
                  {[...(ollama.models || []), ...(ollama.approved_model_presets || [])]
                    .filter((name, index, values) => values.indexOf(name) === index)
                    .map((name) => <option key={name} value={name}>{name}{ollama.models?.includes(name) ? " · installed" : " · preset"}</option>)}
                </select>
              </label>
              <div className="ollamaActions">
                <button type="button" onClick={checkOllama} disabled={Boolean(ollamaBusy)}><RefreshCw /> {ollamaBusy === "check" ? "Checking…" : "Check"}</button>
                <button type="button" onClick={startOllama} disabled={Boolean(ollamaBusy)}><Play /> {ollamaBusy === "start" ? "Starting…" : "Start local service"}</button>
                <button type="button" onClick={pullOllama} disabled={Boolean(ollamaBusy) || !ollamaModel}><DownloadIcon /> {ollamaBusy === "pull" ? "Downloading…" : "Pull model"}</button>
                <button type="button" onClick={testOllama} disabled={Boolean(ollamaBusy) || !ollamaModel}><Zap /> {ollamaBusy === "test" ? "Testing…" : "Test model"}</button>
                <button className="primary" disabled={Boolean(ollamaBusy)}><Save /> Save</button>
              </div>
            </form>
            {!ollama.binary_found && !ollama.reachable && (
              <div className="formNote">
                <HelpCircle /> A web app cannot silently install third-party software on your Mac. Install the official Ollama app, or run the included secure local companion for start/pull controls.
              </div>
            )}
          </article>

          <article className="settingsCard">
            <header><Radio /><div><h3>Provider readiness</h3><p>Cloud credentials and local provider availability.</p></div></header>
            {status.map((item) => (
              <div className="providerRow" key={item.provider}>
                <span><b>{item.provider}</b><small>{item.local ? "local" : item.source === "byok" ? "your encrypted key" : item.source === "platform" ? "platform key" : "not configured"}</small></span>
                <i className={item.configured ? "ready" : ""} />
              </div>
            ))}
          </article>

          <article className="settingsCard billingPreview">
            <header><CreditCard /><div><h3>Pico Probe credits</h3><p>Platform-paid model access preview.</p></div></header>
            <p>Transactions are disabled in this Build Week submission. Use rehearsal mode, local Ollama, or a private BYOK credential.</p>
            <button onClick={() => setBilling(true)}>Preview paid-plan experience</button>
          </article>
        </section>
      </div>
      {billing && (
        <Modal title="Competition demo—no transaction" close={() => setBilling(false)}>
          <div className="demoBilling">
            <CreditCard />
            <h3>Purchases are disabled in this submission.</h3>
            <p>A production release would open Stripe-hosted checkout and credit an auditable usage ledger after a signed webhook.</p>
          </div>
        </Modal>
      )}
    </>
  );
}

function DownloadIcon() {
  return <ArrowDownIcon />;
}

function ArrowDownIcon() {
  return <span aria-hidden="true" className="downloadGlyph">↓</span>;
}

export default function App() {
  const [authed, setAuthed] = useState(Boolean(token()));
  const [page, setPage] = useState("library");
  const [project, setProject] = useState(null);
  const [toast, setToast] = useState(null);
  const [tourOpen, setTourOpen] = useState(
    () => !localStorage.getItem("picoprobe_tutorial_seen"),
  );
  const [tourStep, setTourStep] = useState(0);
  const [theme, setThemeState] = useState(
    () =>
      localStorage.getItem("picoprobe_theme") ||
      (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"),
  );
  const setTheme = (value) => {
    localStorage.setItem("picoprobe_theme", value);
    setThemeState(value);
  };
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  const notify = (message, type = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };
  async function createDemo() {
    try {
      const existing = await get("/projects");
      const found = existing.find(
        (p) =>
          p.title ===
          "Which monomials survive signed multinomial cancellation?",
      );
      if (found) {
        setProject(found);
        setPage("graph");
        return found;
      }
      const p = await post("/projects", {
        title: "Which monomials survive signed multinomial cancellation?",
        question:
          "Given P(x)=Σₜ(sₜ·x)ᵈ with sign vectors sₜ∈{±1}ᵐ, can the surviving monomials be characterized and counted without expanding every multinomial?",
        abstract:
          "A guided, initially open investigation into sign profiles, finite binary geometry, parity constraints, and enumeration. The conclusion is intentionally withheld until independent routes are compared and checked.",
        tags: ["guided-demo", "combinatorics", "signed-multinomials", "parity"],
      });
      await api(`/projects/${p.id}/epistemic-contract`, {
        method: "PUT",
        body: JSON.stringify(contractDefaults),
      });
      await post(`/projects/${p.id}/graph/nodes`, {
        kind: "question",
        title: "Count surviving monomials without brute-force expansion",
        content: {
          statement:
            "Characterize and enumerate monomials with nonzero total coefficient in Σₜ(sₜ·x)ᵈ.",
          unknowns: [
            "Which sign structures factor?",
            "What parity constraints govern survival?",
            "How are admissible exponent allocations counted?",
          ],
        },
        status: "open",
        position: { x: 90, y: 110 },
        provenance: { actor: "researcher", execution_mode: "guided-rehearsal" },
      });
      await post(
        `/pipeline-templates/independent-route-election/instantiate?project_id=${p.id}`,
      );
      setProject(p);
      setPage("graph");
      notify("Guided investigation created");
      return p;
    } catch (e) {
      notify(e.message, "error");
      throw e;
    }
  }
  async function advanceDemo(stage, targetProject = project) {
    if (!targetProject) return;
    const graph = await get(`/projects/${targetProject.id}/graph`);
    const byTitle = new Map(graph.nodes.map((item) => [item.title, item]));
    async function ensureNode(data) {
      if (byTitle.has(data.title)) return byTitle.get(data.title);
      const created = await post(
        `/projects/${targetProject.id}/graph/nodes`,
        data,
      );
      byTitle.set(data.title, created);
      return created;
    }
    async function ensureEdge(source, target, edgeType) {
      const exists = graph.edges.some(
        (edge) =>
          edge.source_id === source.id &&
          edge.target_id === target.id &&
          edge.edge_type === edgeType,
      );
      if (!exists)
        await post(`/projects/${targetProject.id}/graph/edges`, {
          source_id: source.id,
          target_id: target.id,
          edge_type: edgeType,
        });
    }
    const question = byTitle.get(
      "Count surviving monomials without brute-force expansion",
    );
    if (stage === 1) {
      const profile = await ensureNode({
        kind: "hypothesis",
        title: "Route A · sign-profile partition",
        content: {
          proposal:
            "Group variables by their complete sign histories, then count exponent totals per group.",
        },
        status: "proposed",
        provenance: {
          provider: "openai",
          model: "gpt-5.6",
          execution_mode: "guided-rehearsal",
        },
      });
      const fourier = await ensureNode({
        kind: "hypothesis",
        title: "Route B · Walsh character sum",
        content: {
          proposal:
            "Encode signs over F₂ and interpret cancellation through character orthogonality.",
        },
        status: "proposed",
        provenance: {
          provider: "anthropic",
          model: "claude-sonnet-4-5",
          execution_mode: "guided-rehearsal",
        },
      });
      const brute = await ensureNode({
        kind: "unexplored_branch",
        title: "Route C · direct symbolic expansion",
        content: {
          proposal: "Expand every signed multinomial and compare coefficients.",
          reason_preserved:
            "Useful as a finite check but not an optimal general proof strategy.",
        },
        status: "unexplored",
        provenance: {
          provider: "google",
          model: "gemini-2.5-pro",
          execution_mode: "guided-rehearsal",
        },
      });
      for (const hypothesis of [profile, fourier, brute])
        await ensureEdge(question, hypothesis, "motivates");
    }
    if (stage === 3) {
      const profile =
        byTitle.get("Route A · sign-profile partition") ||
        (await ensureNode({
          kind: "hypothesis",
          title: "Route A · sign-profile partition",
          content: {},
          status: "proposed",
        }));
      const fourier =
        byTitle.get("Route B · Walsh character sum") ||
        (await ensureNode({
          kind: "hypothesis",
          title: "Route B · Walsh character sum",
          content: {},
          status: "proposed",
        }));
      const reduction = await ensureNode({
        kind: "claim",
        title: "Coefficient survival reduces to a parity-state function",
        content: {
          statement:
            "For group exponent vector e, a monomial survives iff C(e)=Σₜ∏g σₜg^e_g ≠ 0.",
          assumptions: [
            "Identical sign profiles are grouped",
            "All multinomial weights are +1",
          ],
        },
        status: "under_test",
        provenance: {
          role: "route-comparator",
          execution_mode: "guided-rehearsal",
        },
      });
      await ensureEdge(profile, reduction, "supports");
      await ensureEdge(fourier, reduction, "supports");
    }
    if (stage === 4) {
      const reduction = byTitle.get(
        "Coefficient survival reduces to a parity-state function",
      );
      const challenge = await ensureNode({
        kind: "contradiction",
        title: "Non-affine sign rows need not factor",
        content: {
          objection:
            "C(e) remains a character sum, but arbitrary row sets do not necessarily yield independent linear parity constraints.",
          example: "{000,100,010,111}",
        },
        status: "unresolved",
        provenance: {
          role: "independent-skeptic",
          provider: "anthropic",
          execution_mode: "guided-rehearsal",
        },
      });
      const evidence = await ensureNode({
        kind: "evidence",
        title: "Affine-subspace character orthogonality",
        content: {
          result:
            "For H=v₀+U, the character sum vanishes off U⊥ and equals ±|U| on U⊥.",
          method: "finite-group character calculation",
        },
        status: "supported",
        provenance: { provider: "openai", execution_mode: "guided-rehearsal" },
      });
      await ensureEdge(challenge, reduction, "critiques");
      await ensureEdge(evidence, reduction, "supports");
    }
    if (stage === 5) {
      const reduction = byTitle.get(
        "Coefficient survival reduces to a parity-state function",
      );
      const sympy = await ensureNode({
        kind: "computation",
        title: "SymPy checks r=2, r=4, and r=8 examples",
        content: {
          checks: [
            "Two expansions: one even-parity constraint",
            "Four expansions: e₂,e₃,e₄ share parity",
            "Eight-expansion degree-4 cube: 10 surviving monomials",
          ],
          reproducible: true,
        },
        status: "independently_confirmed",
        provenance: { plugin: "core.sympy", execution_mode: "local" },
      });
      const proof = await ensureNode({
        kind: "formal_verification",
        title: "Lean-checkable parity factorization lemmas",
        content: {
          scope:
            "Binary parity identities and finite products; semantic match remains researcher-reviewed.",
          verification_status: "formally_verified",
        },
        status: "formally_verified",
        provenance: { plugin: "core.lean", execution_mode: "local" },
      });
      await ensureEdge(sympy, reduction, "verifies");
      await ensureEdge(proof, reduction, "verifies");
    }
    if (stage === 6) {
      const reduction = byTitle.get(
        "Coefficient survival reduces to a parity-state function",
      );
      const conclusion = await ensureNode({
        kind: "conclusion",
        title:
          "Affine sign structures yield explicit surviving-monomial counts",
        content: {
          statement:
            "If the binary sign rows form an affine k-dimensional subspace, survival is exactly a system of k linear parity equations; admissible group exponent vectors are then counted by weighted Stars and Bars.",
          formula: "N(d)=Σ_{e∈S(d)} ∏ᵢ binom(eᵢ+vᵢ−1,vᵢ−1)",
          boundary:
            "A converse classification and general non-affine enumeration remain open.",
        },
        status: "independently_confirmed",
        provenance: {
          synthesis: [
            "openai",
            "anthropic",
            "google",
            "core.sympy",
            "core.lean",
            "researcher",
          ],
          execution_mode: "guided-rehearsal",
        },
      });
      const report = await ensureNode({
        kind: "human_review",
        title: "Generated research report · signed multinomial parity",
        content: {
          title:
            "Counting Surviving Monomials in Signed Multinomial Sums via Parity Constraints",
          sections: [
            "Sign-profile partition",
            "Coefficient evaluation function",
            "Binary encoding",
            "Affine factorization",
            "Stars-and-Bars enumeration",
            "Computational examples",
            "Scope and open problems",
          ],
          abstract:
            "Variables are partitioned by complete sign profile. Their group exponent sums determine a finite character sum C(e). When the binary sign rows form an affine subspace, character orthogonality turns survival into independent linear parity constraints; weighted Stars and Bars then counts every surviving monomial.",
          principal_result:
            "For an affine k-dimensional sign configuration, C(e) is nonzero exactly on the orthogonal parity subspace, and N(d)=Σ_{e∈S(d)}∏ᵢ binom(eᵢ+vᵢ−1,vᵢ−1).",
          verification_summary: [
            "The r=2 formula reduces to one even-parity constraint.",
            "The r=4 affine square forces e₂,e₃,e₄ to share parity.",
            "The degree-4 r=8 affine cube has exactly 10 surviving monomials.",
            "Lean checks scoped parity lemmas; the researcher retains responsibility for semantic correspondence.",
          ],
          open_questions: [
            "Classify all non-affine sign matrices with factorable coefficient functions.",
            "Enumerate perturbations of affine configurations.",
            "Extend the method to weighted signed sums.",
          ],
          disclaimer:
            "Guided rehearsal assembled from researcher-supplied mathematics; novelty and literature priority require external scholarly review.",
        },
        status: "accepted",
        provenance: {
          authority: "researcher",
          generated_by: "Pico Probe report assembler",
        },
      });
      await ensureEdge(reduction, conclusion, "derives_from");
      await ensureEdge(conclusion, report, "produces");
    }
  }
  if (!authed)
    return (
      <>
        <Auth
          onDone={() => setAuthed(true)}
          theme={theme}
          setTheme={setTheme}
        />
        <Toast toast={toast} onClose={() => setToast(null)} />
      </>
    );
  let content;
  const startGuided = () => {
    setTourStep(0);
    setTourOpen(true);
  };
  if (!project && page === "public")
    content = <PublicLibraryPage notify={notify} />;
  else if (!project && page === "plugins")
    content = <PluginsPage notify={notify} />;
  else if (!project && page === "settings")
    content = <SettingsPage notify={notify} />;
  else if (!project)
    content = (
      <LibraryPage
        openProject={(p, destination = "graph") => {
          setProject(p);
          setPage(destination);
        }}
        notify={notify}
        onDemo={startGuided}
      />
    );
  else if (page === "graph")
    content = <GraphPage project={project} notify={notify} />;
  else if (page === "contract")
    content = (
      <ContractPage
        project={project}
        notify={notify}
        onContinue={() => setPage("pipeline")}
      />
    );
  else if (page === "pipeline")
    content = <PipelinePage project={project} notify={notify} />;
  else if (page === "runs")
    content = <RunsPage project={project} notify={notify} />;
  else if (page === "verification")
    content = <VerificationPage project={project} notify={notify} />;
  else if (page === "passport")
    content = <PassportPage project={project} notify={notify} />;
  else if (page === "discovery")
    content = <DiscoveryPage project={project} notify={notify} />;
  else content = <ReplayPage project={project} notify={notify} />;
  return (
    <div className="app">
      <Sidebar
        page={page}
        setPage={setPage}
        project={project}
        theme={theme}
        setTheme={setTheme}
        onTutorial={() => {
          setTourStep(0);
          setTourOpen(true);
        }}
        onExit={(destination = "library") => {
          setProject(null);
          setPage(destination);
        }}
      />
      <main className="content">{content}</main>
      {tourOpen && (
        <Tutorial
          step={tourStep}
          setStep={setTourStep}
          project={project}
          setPage={setPage}
          onDemo={createDemo}
          onAdvance={advanceDemo}
          onClose={() => setTourOpen(false)}
        />
      )}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
