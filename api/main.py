from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from application.bootstrap import build_session_application_service
from application.background_runner import TaskBackgroundRunner
from application.commands import (
    ConfirmBusinessRulesCommand,
    CreateTaskCommand,
    SubmitClarificationsCommand,
    SubmitFeedbackCommand,
    UploadedDocument,
)
from application.service import TestAnalysisApplicationService
from repositories import TaskNotFoundError

from .schemas import (
    BusinessRuleConfirmationRequest,
    ClarificationsRequest,
    CreateTaskRequest,
    FeedbackRequest,
    BackgroundRunResponse,
    TaskProgressResponse,
    TaskResponse,
    TaskSummaryPageResponse,
)
from .progress import build_task_progress


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def _response(view) -> TaskResponse:
    return TaskResponse.model_validate(jsonable_encoder(view.to_dict()))


def create_app(
    service: TestAnalysisApplicationService | None = None,
    background_runner: TaskBackgroundRunner | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Test Analysis Agent API",
        version="1.0.0",
        description="受控测试分析Agent的同步应用接口。",
    )
    app.state.application_service = service
    app.state.background_runner = background_runner

    def get_service() -> TestAnalysisApplicationService:
        current = app.state.application_service
        if current is None:
            current = build_session_application_service()
            app.state.application_service = current
        return current

    def get_background_runner() -> TaskBackgroundRunner:
        current = app.state.background_runner
        if current is None:
            current = TaskBackgroundRunner(get_service())
            app.state.background_runner = current
        return current

    @app.exception_handler(TaskNotFoundError)
    async def task_not_found_handler(_, exc: TaskNotFoundError):
        return _error_response(status.HTTP_404_NOT_FOUND, str(exc))

    @app.exception_handler(ValueError)
    async def invalid_action_handler(_, exc: ValueError):
        return _error_response(status.HTTP_409_CONFLICT, str(exc))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

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


app = create_app()
