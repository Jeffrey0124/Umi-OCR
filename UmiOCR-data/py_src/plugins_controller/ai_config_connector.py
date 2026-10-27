"""Lazy bridge so non-AI installations do not depend on the AI plugin."""
import copy

from PySide2.QtCore import QObject, Signal, Slot
from ..utils.thread_pool import threadRun


class AiConfigConnector(QObject):
    finished = Signal(str, str, "QVariant", arguments=["requestId", "action", "result"])

    @Slot("QVariant", result=str)
    def evidenceContext(self, profile):
        from AIOCR.profile_store import evidence_context
        return evidence_context(profile.toVariant() if hasattr(profile, "toVariant") else profile)

    @Slot("QVariant", result="QVariant")
    def initialize(self, config):
        from AIOCR.profile_store import migrate_store, provider_catalog
        try:
            return {"store": migrate_store(config.toVariant() if hasattr(config, "toVariant") else config), "providers": provider_catalog()}
        except ValueError as error:
            return {"error": str(error), "providers": provider_catalog()}

    @Slot("QVariant", result="QVariant")
    def validate(self, profile):
        from AIOCR.profile_store import validate_profile
        try:
            return {"profile": validate_profile(profile.toVariant() if hasattr(profile, "toVariant") else profile)}
        except ValueError as error:
            return {"error": str(error)}

    @Slot(str, str, "QVariant")
    def request(self, request_id, action, profile):
        if action not in ("models", "test"):
            return
        draft = copy.deepcopy(profile.toVariant() if hasattr(profile, "toVariant") else profile)

        def work():
            from AIOCR.config_service import execute
            result = execute(action, draft)
            try:
                self.finished.emit(request_id, action, result)
            except RuntimeError:
                pass  # The editor and its connector may already be destroyed.

        threadRun(work)
