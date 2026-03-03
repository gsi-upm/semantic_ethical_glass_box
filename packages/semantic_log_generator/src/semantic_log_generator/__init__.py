"""Production SEGB semantic logging library for robots."""

from importlib.metadata import PackageNotFoundError, version

from .logger import SemanticSEGBLogger
from .publisher import SEGBPublisher
from .shared_context import HTTPSharedContextResolver, build_http_shared_context_resolver_from_env
from .types import (
    ActivityKind,
    EmotionCategory,
    EmotionScore,
    ModelUsage,
    RobotStateSnapshot,
    SharedEventPolicy,
    SharedEventResolver,
    SharedEventRequest,
)

try:
    __version__ = version("semantic-log-generator")
except PackageNotFoundError:
    __version__ = "1.0.0"

__all__ = [
    "__version__",
    "ActivityKind",
    "EmotionCategory",
    "EmotionScore",
    "ModelUsage",
    "RobotStateSnapshot",
    "HTTPSharedContextResolver",
    "SEGBPublisher",
    "SemanticSEGBLogger",
    "SharedEventPolicy",
    "SharedEventResolver",
    "SharedEventRequest",
    "build_http_shared_context_resolver_from_env",
]
