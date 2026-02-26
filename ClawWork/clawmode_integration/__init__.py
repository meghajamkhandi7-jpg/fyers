"""
ClawMode Integration — ClawWork economic tracking for nanobot.

Extends nanobot's AgentLoop with economic tools so every conversation
is cost-tracked and the agent can check its balance and survival status.
"""

from importlib import import_module

__all__ = [
    "ClawWorkAgentLoop",
    "ClawWorkState",
    "DecideActivityTool",
    "SubmitWorkTool",
    "LearnTool",
    "GetStatusTool",
    "TaskClassifier",
    "TrackedProvider",
]


def __getattr__(name):
    if name == "ClawWorkAgentLoop":
        return import_module("clawmode_integration.agent_loop").ClawWorkAgentLoop
    if name == "TaskClassifier":
        return import_module("clawmode_integration.task_classifier").TaskClassifier
    if name == "TrackedProvider":
        return import_module("clawmode_integration.provider_wrapper").TrackedProvider
    if name in {
        "ClawWorkState",
        "DecideActivityTool",
        "SubmitWorkTool",
        "LearnTool",
        "GetStatusTool",
    }:
        module = import_module("clawmode_integration.tools")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
