from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from application.bootstrap import (
    build_application_services,
)
from application.background_runner import TaskBackgroundRunner
from application.commands import (
    ConfirmBusinessRulesCommand,
    ConfirmKnowledgeAssetCommand,
    CreateTaskCommand,
    SubmitClarificationsCommand,
    SubmitFeedbackCommand,
    UploadedDocument,
)
from application.service import TestAnalysisApplicationService
from application.knowledge_asset_indexing_service import (
    KnowledgeAssetIndexingError,
    KnowledgeAssetIndexingService,
)
from application.knowledge_asset_service import KnowledgeAssetApplicationService
from knowledge_assets import KnowledgeAssetStatus
from repositories import (
    KnowledgeAssetAlreadyExistsError,
    KnowledgeAssetNotFoundError,
    TaskNotFoundError,
)

from .schemas import (
    BusinessRuleConfirmationRequest,
    ClarificationsRequest,
    CreateTaskRequest,
    FeedbackRequest,
    BackgroundRunResponse,
    TaskProgressResponse,
    TaskResponse,
    TaskSummaryPageResponse,
    RenameTaskRequest,
    KnowledgeAssetConfirmationRequest,
    KnowledgeAssetPublicationResponse,
    KnowledgeAssetDetailResponse,
    KnowledgeAssetSummaryPageResponse,
    KnowledgeAssetManagementResponse,
)
from .progress import build_task_progress


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def _response(view) -> TaskResponse:
    return TaskResponse.model_validate(jsonable_encoder(view.to_dict()))


def create_app(
    service: TestAnalysisApplicationService | None = None,
    background_runner: TaskBackgroundRunner | None = None,
    knowledge_asset_service: KnowledgeAssetApplicationService | None = None,
    knowledge_indexing_service: KnowledgeAssetIndexingService | None = None,
) -> FastAPI:
    app = FastAPI(
        title="AI 测试分析助手 API",
        version="1.0.0",
        description="受控测试分析Agent的同步应用接口。",
    )
    app.state.application_service = service
    app.state.background_runner = background_runner
    app.state.knowledge_asset_service = knowledge_asset_service
    app.state.knowledge_indexing_service = knowledge_indexing_service

    def ensure_services() -> None:
        if app.state.application_service is not None:
            return
        services = build_application_services()
        app.state.application_service = services.task_service
        app.state.knowledge_asset_service = services.knowledge_asset_service
        app.state.knowledge_indexing_service = services.knowledge_indexing_service

    def get_service() -> TestAnalysisApplicationService:
        current = app.state.application_service
        if current is None:
            ensure_services()
            current = app.state.application_service
        return current

    def get_knowledge_services():
        if app.state.knowledge_asset_service is None:
            if app.state.application_service is not None:
                raise RuntimeError(
                    "knowledge services must be injected with a custom task service"
                )
            ensure_services()
        return (
            app.state.knowledge_asset_service,
            app.state.knowledge_indexing_service,
        )

    def get_background_runner() -> TaskBackgroundRunner:
        current = app.state.background_runner
        if current is None:
            current = TaskBackgroundRunner(get_service())
            app.state.background_runner = current
        return current

    @app.exception_handler(TaskNotFoundError)
    async def task_not_found_handler(_, exc: TaskNotFoundError):
        return _error_response(status.HTTP_404_NOT_FOUND, str(exc))

    @app.exception_handler(KnowledgeAssetAlreadyExistsError)
    async def knowledge_asset_exists_handler(
        _, exc: KnowledgeAssetAlreadyExistsError
    ):
        return _error_response(status.HTTP_409_CONFLICT, str(exc))

    @app.exception_handler(KnowledgeAssetNotFoundError)
    async def knowledge_asset_not_found_handler(
        _, exc: KnowledgeAssetNotFoundError
    ):
        return _error_response(status.HTTP_404_NOT_FOUND, str(exc))

    @app.exception_handler(ValueError)
    async def invalid_action_handler(_, exc: ValueError):
        return _error_response(status.HTTP_409_CONFLICT, str(exc))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/api/v1/knowledge-assets",
        response_model=KnowledgeAssetSummaryPageResponse,
    )
    def list_knowledge_assets(
        query: str = Query(default="", max_length=200),
        asset_status: KnowledgeAssetStatus | None = Query(
            default=None,
            alias="status",
        ),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> KnowledgeAssetSummaryPageResponse:
        asset_service, _ = get_knowledge_services()
        page = asset_service.list_asset_summaries(
            query=query,
            status=asset_status,
            offset=offset,
            limit=limit,
        )
        return KnowledgeAssetSummaryPageResponse.model_validate(
            jsonable_encoder(page)
        )

    @app.get(
        "/api/v1/knowledge-assets/{asset_id}",
        response_model=KnowledgeAssetDetailResponse,
    )
    def get_knowledge_asset(asset_id: str) -> KnowledgeAssetDetailResponse:
        asset_service, _ = get_knowledge_services()
        asset = asset_service.get_asset(asset_id)
        return KnowledgeAssetDetailResponse.model_validate(
            jsonable_encoder(asset)
        )

    @app.post(
        "/api/v1/knowledge-assets/{asset_id}/retire",
        response_model=KnowledgeAssetManagementResponse,
    )
    def retire_knowledge_asset(asset_id: str) -> KnowledgeAssetManagementResponse:
        _, indexing_service = get_knowledge_services()
        try:
            result = indexing_service.retire_asset(asset_id)
        except KnowledgeAssetIndexingError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        return KnowledgeAssetManagementResponse(
            asset_id=result.asset_id,
            status=result.status.value,
            vector_cleanup_completed=result.vector_cleanup_completed,
        )

    @app.post(
        "/api/v1/knowledge-assets/{asset_id}/restore",
        response_model=KnowledgeAssetManagementResponse,
    )
    def restore_knowledge_asset(asset_id: str) -> KnowledgeAssetManagementResponse:
        _, indexing_service = get_knowledge_services()
        try:
            result = indexing_service.restore_asset(asset_id)
        except KnowledgeAssetIndexingError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        return _index_management_response(result)

    @app.post(
        "/api/v1/knowledge-assets/{asset_id}/retry-index",
        response_model=KnowledgeAssetManagementResponse,
    )
    def retry_knowledge_asset_index(asset_id: str) -> KnowledgeAssetManagementResponse:
        _, indexing_service = get_knowledge_services()
        try:
            result = indexing_service.retry_failed_asset(
                asset_id,
                f"web-{uuid4()}",
            )
        except KnowledgeAssetIndexingError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        return _index_management_response(result)

    @app.post(
        "/api/v1/tasks/{task_id}/knowledge-assets",
        response_model=KnowledgeAssetPublicationResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def publish_knowledge_asset(
        task_id: str,
        payload: KnowledgeAssetConfirmationRequest,
    ) -> KnowledgeAssetPublicationResponse:
        asset_service, indexing_service = get_knowledge_services()
        asset = asset_service.confirm_task_result(
            task_id,
            ConfirmKnowledgeAssetCommand(
                user_confirmed=payload.user_confirmed,
                data_safety_confirmed=payload.data_safety_confirmed,
            ),
        )
        try:
            indexed = indexing_service.index_asset(asset.asset_id)
        except KnowledgeAssetIndexingError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "知识资产已保存到MySQL，但向量索引失败；"
                    "可稍后通过索引重试功能恢复。"
                ),
            ) from exc
        return KnowledgeAssetPublicationResponse(
            asset_id=asset.asset_id,
            source_task_id=asset.source_task_id,
            asset_version=asset.asset_version,
            status=indexed.status.value,
            test_point_count=asset.test_point_count,
            reviewer_score=asset.reviewer_score,
            chunk_count=indexed.chunk_count,
            omitted_chunk_count=indexed.omitted_chunk_count,
        )

    @app.get("/", include_in_schema=False)
    def frontend_home() -> RedirectResponse:
        return RedirectResponse("/app/")

    @app.post(
        "/api/v1/tasks",
        response_model=TaskResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_task(payload: CreateTaskRequest) -> TaskResponse:
        return _response(get_service().create_task(
            CreateTaskCommand(requirement=payload.requirement)
        ))

    @app.post(
        "/api/v1/tasks/from-document",
        response_model=TaskResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_task_from_document(
        file: UploadFile = File(...),
    ) -> TaskResponse:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if not content:
            raise HTTPException(422, "uploaded document cannot be empty")
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "uploaded document exceeds 20 MB")
        try:
            view = get_service().create_task(CreateTaskCommand(
                uploaded_document=UploadedDocument(
                    filename=file.filename or "",
                    content=content,
                )
            ))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return _response(view)

    @app.get("/api/v1/tasks", response_model=list[TaskResponse])
    def list_tasks() -> list[TaskResponse]:
        return [_response(view) for view in get_service().list_tasks()]

    @app.get(
        "/api/v1/task-summaries",
        response_model=TaskSummaryPageResponse,
    )
    def list_task_summaries(
        query: str = Query(default="", max_length=100),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=10, ge=1, le=100),
    ) -> TaskSummaryPageResponse:
        page = get_service().list_task_summaries(
            query=query,
            offset=offset,
            limit=limit,
        )
        return TaskSummaryPageResponse.model_validate(jsonable_encoder({
            "items": [vars(item) for item in page.items],
            "total": page.total,
            "offset": page.offset,
            "limit": page.limit,
        }))

    @app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
    def get_task(task_id: str) -> TaskResponse:
        return _response(get_service().get_task(task_id))

    @app.patch(
        "/api/v1/tasks/{task_id}/name",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def rename_task(task_id: str, payload: RenameTaskRequest) -> Response:
        get_service().rename_task(task_id, payload.task_name)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post(
        "/api/v1/tasks/{task_id}/advance",
        response_model=TaskResponse,
    )
    def advance_task(task_id: str) -> TaskResponse:
        return _response(get_service().advance_task(task_id))

    @app.post(
        "/api/v1/tasks/{task_id}/run",
        response_model=BackgroundRunResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def run_task(task_id: str) -> BackgroundRunResponse:
        return BackgroundRunResponse.model_validate(
            get_background_runner().start(task_id).__dict__
        )

    @app.get(
        "/api/v1/tasks/{task_id}/execution",
        response_model=BackgroundRunResponse,
    )
    def get_execution(task_id: str) -> BackgroundRunResponse:
        return BackgroundRunResponse.model_validate(
            get_background_runner().get_status(task_id).__dict__
        )

    @app.get(
        "/api/v1/tasks/{task_id}/progress",
        response_model=TaskProgressResponse,
    )
    def get_progress(task_id: str) -> TaskProgressResponse:
        view = get_service().get_task(task_id)
        execution = get_background_runner().get_status(task_id)
        return TaskProgressResponse.model_validate(
            build_task_progress(view, execution)
        )

    @app.post(
        "/api/v1/tasks/{task_id}/clarifications",
        response_model=TaskResponse,
    )
    def submit_clarifications(
        task_id: str,
        payload: ClarificationsRequest,
    ) -> TaskResponse:
        return _response(get_service().submit_clarifications(
            task_id,
            SubmitClarificationsCommand(answers=payload.answers),
        ))

    @app.post(
        "/api/v1/tasks/{task_id}/business-rules/confirmation",
        response_model=TaskResponse,
    )
    def confirm_business_rule(
        task_id: str,
        payload: BusinessRuleConfirmationRequest,
    ) -> TaskResponse:
        return _response(get_service().confirm_business_rules(
            task_id,
            ConfirmBusinessRulesCommand(
                feedback_id=payload.feedback_id,
                confirmed=payload.confirmed,
            ),
        ))

    @app.post(
        "/api/v1/tasks/{task_id}/feedback",
        response_model=TaskResponse,
    )
    def submit_feedback(
        task_id: str,
        payload: FeedbackRequest,
    ) -> TaskResponse:
        return _response(get_service().submit_feedback(
            task_id,
            SubmitFeedbackCommand(**payload.model_dump()),
        ))

    @app.post(
        "/api/v1/tasks/{task_id}/retry",
        response_model=TaskResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def retry_task(task_id: str) -> TaskResponse:
        return _response(get_service().retry_task(task_id))

    @app.delete(
        "/api/v1/tasks/{task_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def delete_task(task_id: str) -> Response:
        get_service().delete_task(task_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    app.mount(
        "/app",
        StaticFiles(directory=FRONTEND_DIR, html=True),
        name="frontend",
    )

    return app


def _error_response(status_code: int, message: str):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={"detail": message},
    )


def _index_management_response(result) -> KnowledgeAssetManagementResponse:
    return KnowledgeAssetManagementResponse(
        asset_id=result.asset_id,
        status=result.status.value,
        chunk_count=result.chunk_count,
        omitted_chunk_count=result.omitted_chunk_count,
    )


app = create_app()
