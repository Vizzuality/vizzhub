"""Enum constants for the devstack module."""

from enum import StrEnum


class EntryType(StrEnum):
    SKILL = "skill"
    COMMAND = "command"
    PLUGIN = "plugin"
    CONFIG = "config"
    AGENT = "agent"


class InstallMethod(StrEnum):
    GITHUB = "github"
    NPM = "npm"


class EntryOrigin(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"
