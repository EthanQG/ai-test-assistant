from dataclasses import dataclass


@dataclass(frozen=True)
class UploadedDocument:
    filename: str
    content: bytes


@dataclass(frozen=True)
class CreateTaskCommand:
    requirement: str = ""
    uploaded_document: UploadedDocument | None = None


@dataclass(frozen=True)
class SubmitClarificationsCommand:
    answers: dict[str, str | None]


@dataclass(frozen=True)
class ConfirmBusinessRulesCommand:
    feedback_id: str
    confirmed: bool


@dataclass(frozen=True)
class SubmitFeedbackCommand:
    action: str
    feedback_type: str
    target: str
    content: str
    reason: str


@dataclass(frozen=True)
class ConfirmKnowledgeAssetCommand:
    user_confirmed: bool
    data_safety_confirmed: bool
