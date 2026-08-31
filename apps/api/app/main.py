from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .config import STORAGE_ROOT
from .media import render_three_shot_story
from .mock_mvp import MockProductionService
from .repository import ProjectRepository, create_default_repository


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    premise: str = Field(min_length=1, max_length=1000)


def create_app(repository: ProjectRepository | None = None, storage_root: Path | None = None) -> FastAPI:
    repo = repository or create_default_repository()
    output_root = storage_root or STORAGE_ROOT
    services: dict[str, MockProductionService] = {}
    impact_plans: dict[str, dict] = {}
    app = FastAPI(title="AI Drama Agent Mock MVP")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "persistence": repo.persistence_name}

    def service_for(project_id: str) -> MockProductionService:
        service = services.setdefault(project_id, MockProductionService())
        if not service.shots:
            service.seed()
        return service

    @app.post("/projects", status_code=201)
    def create_project(request: CreateProjectRequest) -> dict:
        return repo.create_project(str(uuid4()), request.title, request.premise)

    @app.get("/projects/{project_id}")
    def get_project(project_id: str) -> dict:
        project = repo.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project

    @app.post("/projects/{project_id}/commands/start")
    def start_project(project_id: str) -> dict:
        project = repo.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if project["rough_cut_asset_id"]:
            return repo.get_project(project_id) or project
        asset_id, final_path = render_three_shot_story(output_root, project_id, project["title"])
        repo.set_rendered(project_id, asset_id, str(final_path))
        service_for(project_id)
        return repo.get_project(project_id) or project

    @app.get("/projects")
    def list_projects() -> list[dict]:
        return repo.list_projects()

    @app.post("/projects/{project_id}/pause")
    def pause_project(project_id: str) -> dict:
        if not repo.get_project(project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        service_for(project_id).pause()
        return {"project_id": project_id, "status": "PAUSED"}

    @app.post("/projects/{project_id}/resume")
    def resume_project(project_id: str) -> dict:
        if not repo.get_project(project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        service_for(project_id).resume()
        return {"project_id": project_id, "status": "RUNNING"}

    @app.post("/shots/{shot_id}/commands/regenerate")
    def regenerate_shot(shot_id: str, project_id: str, spec_changed: bool = False, idempotency_key: str | None = None) -> dict:
        try:
            return service_for(project_id).regenerate_shot(shot_id, spec_changed=spec_changed, idempotency_key=idempotency_key)
        except (KeyError, RuntimeError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/timelines/{timeline_id}/commands/replace-shot")
    def replace_shot(timeline_id: str, project_id: str, shot_id: str, asset_id: str) -> dict:
        try:
            return service_for(project_id).replace_shot(shot_id, asset_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/projects/{project_id}/impact-plans/dialogue-edit")
    def create_dialogue_impact_plan(project_id: str, line_id: str, shot_id: str) -> dict:
        if not repo.get_project(project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        plan = service_for(project_id).dialogue_impact_plan(line_id, shot_id)
        impact_plans[plan["id"]] = {**plan, "project_id": project_id}
        return impact_plans[plan["id"]]

    @app.post("/impact-plans/{impact_plan_id}/commands/apply")
    def apply_dialogue_impact_plan(impact_plan_id: str) -> dict:
        plan = impact_plans.get(impact_plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Impact plan not found")
        return service_for(plan["project_id"]).apply_dialogue_plan(plan)

    @app.get("/projects/{project_id}/artifacts")
    def project_artifacts(project_id: str) -> dict:
        project = repo.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        service = service_for(project_id)
        return {"production_brief": {"title": project["title"], "premise": project["premise"]}, "story_bible": {"language": "zh-CN", "format": "9:16"}, "screenplay": {"shot_count": service.shot_count}, "shots": [{"id": shot_id, "production_state": record.shot.production_state, "version_status": record.committed_version.version_status, "asset_id": record.candidate_asset.id} for shot_id, record in service.shots.items()], "shot_graph": {"nodes": list(service.shots), "edges": []}, "timeline": {"version": service.timeline_version}, "qc_report": {"status": "PASS", "is_mock": True}}

    @app.get("/projects/{project_id}/costs")
    def project_costs(project_id: str) -> dict:
        if not repo.get_project(project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        return {"currency": "USD", "total_minor": 0, "is_mock": True, "events": [], "budget_reservations": []}

    @app.get("/projects/{project_id}/evidence")
    def project_evidence(project_id: str) -> dict:
        project = repo.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"project_id": project_id, "production_state": project["production_state"], "assets": [project["rough_cut_asset_id"]] if project["rough_cut_asset_id"] else [], "checks": ["ffprobe", "mock-qc", "repository-persistence"]}

    @app.get("/projects/{project_id}/progress")
    def project_progress(project_id: str) -> dict:
        project = repo.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        ready = project["production_state"] == "ROUGH_CUT_READY"
        return {"project_id": project_id, "phase": "DELIVERABLE_READY" if ready else "PLANNED", "percent": 100 if ready else 0, "message": "Mock 粗剪已就绪" if ready else "等待开始制作"}

    @app.post("/shots/{shot_id}/commands/repair")
    def repair_shot(shot_id: str, project_id: str) -> dict:
        try:
            return service_for(project_id).repair(shot_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Shot not found") from error

    @app.get("/projects/{project_id}/issues")
    def project_issues(project_id: str) -> dict:
        if not repo.get_project(project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        return {"issues": service_for(project_id).issues}

    @app.get("/assets/{asset_id}/content")
    def get_asset(asset_id: str) -> FileResponse:
        path = repo.get_asset_path(asset_id)
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="Asset not found")
        return FileResponse(path, media_type="video/mp4", filename="rough-cut.mp4")

    return app


app = create_app()
