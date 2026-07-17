"""Fail-closed disclosure and public release-role policy."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Mapping
import tomllib

from erhni.config import ConfigError, REPOSITORY_ROOT


DISCLOSURE_CLASSES = frozenset(
    {
        "public_snapshot",
        "public_aggregate",
        "restricted_source",
        "restricted_derived",
        "review_only",
    }
)
RELEASE_ROLES = frozenset(
    {
        "public_code",
        "public_config",
        "public_documentation",
        "public_evidence",
        "public_snapshot",
        "public_aggregate",
    }
)
PUBLIC_DISCLOSURE_CLASSES = frozenset({"public_snapshot", "public_aggregate"})


@dataclass(frozen=True, slots=True)
class DisclosureRule:
    pattern: str
    disclosure_class: str


@dataclass(frozen=True, slots=True)
class ReleaseRoleRule:
    pattern: str
    release_role: str


@dataclass(frozen=True, slots=True)
class DisclosureConfig:
    disclosure_rules: tuple[DisclosureRule, ...]
    release_role_rules: tuple[ReleaseRoleRule, ...]
    rights_change_requires_reviewed_config_commit: bool
    _disclosure_by_pattern: Mapping[str, DisclosureRule]
    _release_by_pattern: Mapping[str, ReleaseRoleRule]


def _resolve(path: str | Path | None) -> Path:
    candidate = REPOSITORY_ROOT / "config" / "disclosure.toml" if path is None else Path(path)
    if not candidate.is_absolute():
        candidate = REPOSITORY_ROOT / candidate
    return candidate.resolve()


def _read(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"cannot read disclosure configuration {path}: {error}") from error


def _table_rules(
    raw: Any, field: str, allowed: frozenset[str], rule_type: type[DisclosureRule] | type[ReleaseRoleRule]
) -> tuple[DisclosureRule, ...] | tuple[ReleaseRoleRule, ...]:
    if not isinstance(raw, list) or not raw:
        raise ConfigError(f"{field} must be a nonempty array of TOML tables")
    rules = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ConfigError(f"{field} entries must be TOML tables")
        pattern = entry.get("pattern")
        value = entry.get(field)
        if not isinstance(pattern, str) or not pattern:
            raise ConfigError(f"{field} rule pattern must be a nonempty string")
        if value not in allowed:
            raise ConfigError(f"invalid {field}: {value}")
        rules.append(rule_type(pattern=pattern, **{field: value}))
    if len({rule.pattern for rule in rules}) != len(rules):
        raise ConfigError(f"{field} rule patterns must be unique")
    return tuple(rules)


def load_disclosure(path: str | Path | None = None) -> DisclosureConfig:
    """Load the explicit disclosure and release allow-list policy."""

    data = _read(_resolve(path))
    disclosure_rules = _table_rules(
        data.get("disclosure_rule"),
        "disclosure_class",
        DISCLOSURE_CLASSES,
        DisclosureRule,
    )
    release_role_rules = _table_rules(
        data.get("release_role_rule"),
        "release_role",
        RELEASE_ROLES,
        ReleaseRoleRule,
    )
    policy = data.get("policy")
    if not isinstance(policy, dict) or policy.get("rights_change_requires_reviewed_config_commit") is not True:
        raise ConfigError("rights classification changes must require a reviewed config commit")
    return DisclosureConfig(
        disclosure_rules=disclosure_rules,  # type: ignore[arg-type]
        release_role_rules=release_role_rules,  # type: ignore[arg-type]
        rights_change_requires_reviewed_config_commit=True,
        _disclosure_by_pattern=MappingProxyType(
            {rule.pattern: rule for rule in disclosure_rules}
        ),
        _release_by_pattern=MappingProxyType(
            {rule.pattern: rule for rule in release_role_rules}
        ),
    )


def _normalise(path: str | Path) -> str:
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ConfigError(f"path must be repository-relative: {path}")
    return candidate.as_posix()


def _matches(path: str, rules: tuple[DisclosureRule, ...] | tuple[ReleaseRoleRule, ...]):
    return [rule for rule in rules if fnmatchcase(path, rule.pattern)]


def classify_path(config: DisclosureConfig, path: str | Path) -> str | None:
    """Return the one scientific disclosure class for an artifact, or fail closed."""

    normalized = _normalise(path)
    matches = _matches(normalized, config.disclosure_rules)
    if len(matches) > 1:
        raise ConfigError(f"path matches multiple disclosure rules: {normalized}")
    if len(matches) == 1:
        return matches[0].disclosure_class
    if normalized.startswith(("data/", "outputs/")) and normalized != "data/derived/source_manifest.json":
        raise ConfigError(f"path has no disclosure classification: {normalized}")
    return None


def release_role_for_path(config: DisclosureConfig, path: str | Path) -> str:
    """Return the one public release role for an allow-listed repository path."""

    normalized = _normalise(path)
    matches = _matches(normalized, config.release_role_rules)
    if len(matches) != 1:
        detail = "no" if not matches else "multiple"
        raise ConfigError(f"path has {detail} release role matches: {normalized}")
    return matches[0].release_role


def validate_staged_path(config: DisclosureConfig, path: str | Path) -> str:
    """Validate a release candidate without granting any deny-list fallback."""

    disclosure_class = classify_path(config, path)
    if disclosure_class is not None and disclosure_class not in PUBLIC_DISCLOSURE_CLASSES:
        raise ConfigError(f"non-public disclosure class cannot be staged: {path}")
    release_role = release_role_for_path(config, path)
    if disclosure_class is not None and release_role != disclosure_class:
        raise ConfigError(f"disclosure class and release role disagree: {path}")
    return release_role
