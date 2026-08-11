from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.encoders import jsonable_encoder

from application.bootstrap import build_session_application_service
from application.commands import (
    ConfirmBusinessRulesCommand,
    CreateTaskCommand,
    SubmitClarificationsCommand,
    SubmitFeedbackCommand,
)
from application.service import TestAnalysisApplicationService
from repositories import TaskNotFoundError

from .schemas import (
    BusinessRuleConfirmationRequest,
    ClarificationsRequest,
    CreateTaskRequest,
    FeedbackRequest,
    TaskResponse,
)


def _response(view) -> TaskResponse:
    return TaskResponse.model_validate(jsonable_encoder(view.to_dict()))


def create_app(
    service: TestAnalysisApplicationService | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Test Analysis Agent API",
        version="1.0.0",
        description="受控测试分析Agent的同步应用接口。",
    )
    app.state.application_service = service

    def get_service() -> TestAnalysisApplicationService:
        current = app.state.application_service
        if current is None:
            current = build_session_application_service()
            app.state.application_service = current
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

    @app.post(
        "/api/v1/tasks",
        response_model=TaskResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_task(payload: CreateTaskRequest) -> TaskResponse:
        return _response(get_service().create_task(
            CreateTaskCommand(requirement=payload.requirement)
        ))

    @app.get("/api/v1/tasks", response_model=list[TaskResponse])
    def list_tasks() -> list[TaskResponse]:
        return [_response(view) for view in get_service().list_tasks()]

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

    return app


def _error_response(status_code: int, message: str):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={"detail": message},
    )


app = create_app()
