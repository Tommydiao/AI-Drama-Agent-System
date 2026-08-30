"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type Project = { id: string; title: string; premise: string; production_state: string; rough_cut_asset_id: string | null };
type Shot = { id: string; production_state: string; version_status: string; asset_id: string };
type Artifacts = { production_brief: { title: string; premise: string }; story_bible: { language: string; format: string }; screenplay: { shot_count: number }; shots: Shot[]; timeline: { version: number }; qc_report: { status: string } };
type Issue = { id: string; shot_id: string; kind: string; status: string };

export default function Home() {
  const [project, setProject] = useState<Project | null>(null);
  const [artifacts, setArtifacts] = useState<Artifacts | null>(null);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [activePanel, setActivePanel] = useState<"story" | "shots" | "cost" | "evidence">("story");
  const [candidateByShot, setCandidateByShot] = useState<Record<string, string>>({});

  const ready = project?.production_state === "ROUGH_CUT_READY";
  const selectedCount = useMemo(() => artifacts?.shots.length ?? 0, [artifacts]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const projects = await getJson<Project[]>(`${api}/projects`);
        if (!cancelled && projects[0]) { setProject(projects[0]); await refresh(projects[0].id); }
      } catch { /* A first-time visitor simply sees the create form. */ }
    })();
    return () => { cancelled = true; };
  // The API origin is a module constant and intentionally stable for this local app.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function getJson<T>(url: string, options?: RequestInit): Promise<T> {
    const response = await fetch(url, options);
    if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "请求未完成");
    return response.json() as Promise<T>;
  }

  async function refresh(projectId: string) {
    const next = await getJson<Artifacts>(`${api}/projects/${projectId}/artifacts`);
    setArtifacts(next);
    const issuePayload = await getJson<{ issues: Issue[] }>(`${api}/projects/${projectId}/issues`);
    setIssues(issuePayload.issues);
  }

  async function createAndRender(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice(""); setProgress(8);
    const form = new FormData(event.currentTarget);
    const timer = window.setInterval(() => setProgress((value) => Math.min(value + 7, 88)), 900);
    try {
      const created = await getJson<Project>(`${api}/projects`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: form.get("title"), premise: form.get("premise") }) });
      setProject(created); setProgress(18);
      const rendered = await getJson<Project>(`${api}/projects/${created.id}/commands/start`, { method: "POST" });
      setProject(rendered); await refresh(rendered.id); setProgress(100); setNotice("生产完成：粗剪已就绪");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "生产失败，请重试"); }
    finally { window.clearInterval(timer); setBusy(false); }
  }

  async function runAction(action: () => Promise<void>, success: string) {
    setError(""); setNotice("");
    try { await action(); setNotice(success); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "操作失败"); }
  }

  async function regenerate(shotId: string) {
    if (!project) return;
    await runAction(async () => {
      const result = await getJson<{ asset_id: string }>(`${api}/shots/${shotId}/commands/regenerate?project_id=${encodeURIComponent(project.id)}&idempotency_key=ui-${shotId}`, { method: "POST" });
      setCandidateByShot((current) => ({ ...current, [shotId]: result.asset_id }));
      await refresh(project.id);
    }, `${shotId} 已生成新候选版本`);
  }

  async function replaceCandidate(shotId: string) {
    if (!project || !candidateByShot[shotId]) return;
    await runAction(async () => {
      await getJson(`${api}/timelines/timeline-${project.id}/commands/replace-shot?project_id=${encodeURIComponent(project.id)}&shot_id=${encodeURIComponent(shotId)}&asset_id=${encodeURIComponent(candidateByShot[shotId])}`, { method: "POST" });
      await refresh(project.id);
    }, `${shotId} 已替换，时间线已更新`);
  }

  async function editDialogue() {
    if (!project) return;
    await runAction(async () => {
      const plan = await getJson<{ id: string; impacted_shot_ids: string[] }>(`${api}/projects/${project.id}/impact-plans/dialogue-edit?line_id=line-1&shot_id=shot-3`, { method: "POST" });
      await getJson(`${api}/impact-plans/${plan.id}/commands/apply`, { method: "POST" });
      await refresh(project.id);
    }, "台词已更新，仅重算受影响的镜头与音频");
  }

  async function exhaustRepair() {
    if (!project) return;
    await runAction(async () => {
      await getJson(`${api}/shots/shot-3/commands/repair?project_id=${project.id}`, { method: "POST" });
      await getJson(`${api}/shots/shot-3/commands/repair?project_id=${project.id}`, { method: "POST" });
      await getJson(`${api}/shots/shot-3/commands/repair?project_id=${project.id}`, { method: "POST" });
      await refresh(project.id);
    }, "自动修复已达到上限，Issue 已转人工处理");
  }

  async function pauseOrResume() {
    if (!project) return;
    const paused = notice === "项目已暂停";
    await runAction(async () => { await getJson(`${api}/projects/${project.id}/${paused ? "resume" : "pause"}`, { method: "POST" }); }, paused ? "项目已恢复" : "项目已暂停");
  }

  return <main>
    <header className="hero"><p className="eyebrow">AI DRAMA AGENT · LOCAL MOCK MVP</p><h1>把一个故事，变成可播放的竖屏短剧。</h1><p className="lede">从一句创意开始，自动生成可追溯的故事结构、镜头和粗剪成片。</p></header>
    <form onSubmit={createAndRender} className="project-form" data-testid="project-form">
      <label>短剧标题<input name="title" defaultValue="门外的人" required /></label>
      <label>一句话故事创意<textarea name="premise" defaultValue="深夜，门外传来一个本不该出现的熟悉声音。" required /></label>
      <button disabled={busy} data-testid="start-production">{busy ? "正在生成素材与粗剪…" : "开始自动制作"}</button>
      {busy && <div className="progress-wrap" aria-live="polite"><div className="progress-bar" style={{ width: `${progress}%` }} /><span>生产进度 {progress}% · 规划 → 镜头 → 音频 → QC → 粗剪</span></div>}
    </form>
    {error && <p className="error" role="alert">{error}</p>}
    {project && <section className="workspace" data-testid="workspace">
      <div className="workspace-head"><div><p className="eyebrow">PROJECT READY</p><h2>{project.title}</h2><p>{project.premise}</p></div><span className={`state state-${project.production_state}`}>{project.production_state}</span></div>
      {notice && <p className="notice" role="status">{notice}</p>}
      <nav className="tabs" aria-label="项目视图"><button className={activePanel === "story" ? "active" : ""} onClick={() => setActivePanel("story")}>故事结构</button><button className={activePanel === "shots" ? "active" : ""} onClick={() => setActivePanel("shots")}>分镜 ({selectedCount})</button><button className={activePanel === "cost" ? "active" : ""} onClick={() => setActivePanel("cost")}>成本</button><button className={activePanel === "evidence" ? "active" : ""} onClick={() => setActivePanel("evidence")}>证据 / Issue</button></nav>
      {ready && project.rough_cut_asset_id && <video className="rough-cut" controls autoPlay data-testid="rough-cut" src={`${api}/assets/${project.rough_cut_asset_id}/content`} />}
      {!ready && <div className="empty-state">项目尚未开始生产。</div>}
      {activePanel === "story" && artifacts && <div className="card-grid"><article><span>ProductionBrief</span><strong>{artifacts.production_brief.title}</strong><p>{artifacts.production_brief.premise}</p></article><article><span>StoryBible</span><strong>{artifacts.story_bible.language} · {artifacts.story_bible.format}</strong><p>Mock-first，结构化状态持续保存。</p></article><article><span>Screenplay</span><strong>{artifacts.screenplay.shot_count} 个镜头</strong><p>完整 60 秒竖屏粗剪。</p></article><article><span>QCReport</span><strong>{artifacts.qc_report.status}</strong><p>技术规格与媒体完整性检查通过。</p></article></div>}
      {activePanel === "shots" && artifacts && <div className="shot-panel"><div className="toolbar"><button onClick={pauseOrResume}>{notice === "项目已暂停" ? "恢复生产" : "暂停生产"}</button><button onClick={editDialogue}>编辑 shot-3 台词</button><button onClick={exhaustRepair}>运行自动修复上限</button></div><div className="shot-list">{artifacts.shots.map((shot, index) => <article className="shot-row" key={shot.id}><span className="shot-number">{String(index + 1).padStart(2, "0")}</span><div><strong>{shot.id}</strong><p>{shot.production_state} · {shot.version_status}</p></div><div className="shot-actions"><button onClick={() => regenerate(shot.id)}>重新生成</button><button disabled={!candidateByShot[shot.id]} onClick={() => replaceCandidate(shot.id)}>替换候选</button></div></article>)}</div></div>}
      {activePanel === "cost" && <div className="detail-card"><h3>Mock CostReport</h3><p className="metric">$0.00 <small>USD · is_mock=true</small></p><p>本地 Mock 生成不调用付费服务。每项操作均保留可追溯记录。</p></div>}
      {activePanel === "evidence" && <div className="detail-card"><h3>Evidence & Issues</h3><p>检查：ffprobe · mock-qc · repository-persistence</p>{issues.length ? <ul>{issues.map((issue) => <li key={issue.id}>{issue.shot_id} · {issue.kind} · {issue.status}</li>)}</ul> : <p>当前没有开放 Issue。</p>}</div>}
    </section>}
  </main>;
}
