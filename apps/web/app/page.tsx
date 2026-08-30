"use client";

import { FormEvent, useState } from "react";

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
type Project = { id: string; title: string; production_state: string; rough_cut_asset_id: string | null };
type Artifacts = { screenplay: { shot_count: number }; shots: { id: string; production_state: string; version_status: string; asset_id: string }[]; timeline: { version: number }; qc_report: { status: string } };

export default function Home() {
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [artifacts, setArtifacts] = useState<Artifacts | null>(null);
  const [notice, setNotice] = useState("");
  async function createAndRender(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      const created = await fetch(`${api}/projects`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: form.get("title"), premise: form.get("premise") }) });
      if (!created.ok) throw new Error("项目创建失败");
      const item = await created.json() as Project;
      const rendered = await fetch(`${api}/projects/${item.id}/commands/start`, { method: "POST" });
      if (!rendered.ok) throw new Error("Mock 制作失败");
      const next = await rendered.json() as Project;
      setProject(next);
      setArtifacts(await (await fetch(`${api}/projects/${next.id}/artifacts`)).json() as Artifacts);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "发生未知错误"); }
    finally { setBusy(false); }
  }
  async function action(path: string, options?: RequestInit) {
    if (!project) return;
    const response = await fetch(`${api}${path}`, options);
    if (!response.ok) { setError("操作未完成"); return; }
    setNotice((await response.json()).status ?? "操作已完成");
  }
  return <main><p className="eyebrow">AI DRAMA AGENT · MOCK MVP</p><h1>把一个故事，变成可播放的竖屏短剧。</h1><form onSubmit={createAndRender}><label>短剧标题<input name="title" defaultValue="门外的人" required /></label><label>故事梗概<textarea name="premise" defaultValue="深夜，门外传来一个本不该出现的熟悉声音。" required /></label><button disabled={busy}>{busy ? "正在制作 15 镜头样片…" : "生成可播放样片"}</button></form>{error && <p role="alert">{error}</p>}{project && <section><p>状态：{project.production_state}</p><div className="actions"><button onClick={() => action(`/projects/${project.id}/pause`)}>暂停</button><button onClick={() => action(`/projects/${project.id}/resume`)}>恢复</button><button onClick={() => action(`/projects/${project.id}/evidence`)}>查看证据</button></div>{notice && <p className="notice">{notice}</p>}{project.rough_cut_asset_id && <video controls autoPlay src={`${api}/assets/${project.rough_cut_asset_id}/content`} />}{artifacts && <div className="summary"><p>{artifacts.screenplay.shot_count} 个镜头 · Timeline v{artifacts.timeline.version} · QC {artifacts.qc_report.status}</p><ul>{artifacts.shots.slice(0, 5).map((shot) => <li key={shot.id}>{shot.id} · {shot.production_state} · {shot.version_status}</li>)}</ul></div>}</section>}</main>;
}
