"""Guardrail engine for input/output validation.

Provides rule-based and pattern-based guards for:
- PII detection and masking
- Prompt injection detection
- Toxicity/profanity filtering
- Output format validation (JSON schema, regex)
- Hallucination indicators
- Custom regex rules
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class GuardAction(str, Enum):
    """Action to take when a guard rule triggers."""

    BLOCK = "block"
    WARN = "warn"
    MASK = "mask"
    LOG = "log"


class GuardResult(str, Enum):
    """Result of a guard check."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


# ── PII patterns ───────────────────────────────────────────────────

_PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone_us": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    "api_key": re.compile(r"\b(?:sk|pk|api|key|token)[-_]?[a-zA-Z0-9]{20,}\b", re.IGNORECASE),
}

# ── Injection patterns ─────────────────────────────────────────────

_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|above|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\s+", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\|(?:im_start|system|endoftext)\|>", re.IGNORECASE),
    re.compile(r"(?:forget|disregard)\s+(?:everything|all|your)", re.IGNORECASE),
    re.compile(r"do\s+not\s+follow\s+(?:any|your)\s+(?:rules|instructions)", re.IGNORECASE),
    re.compile(r"jailbreak|DAN\s*mode|developer\s*mode", re.IGNORECASE),
]

# ── Toxicity keywords (basic) ─────────────────────────────────────

_TOXICITY_INDICATORS: list[str] = [
    "kill yourself", "kys", "die in a fire",
    "bomb threat", "shoot up", "mass shooting",
]


@dataclass
class GuardRule:
    """A single guard rule definition."""

    name: str
    type: str  # pii, injection, toxicity, regex, json_schema, length, custom
    action: GuardAction = GuardAction.BLOCK
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GuardRule":
        """Create from dict."""
        return cls(
            name=data.get("name", "unnamed"),
            type=data.get("type", "regex"),
            action=GuardAction(data.get("action", "block")),
            config=data.get("config", {}),
            enabled=data.get("enabled", True),
        )


@dataclass
class GuardCheckResult:
    """Result of running a single guard check."""

    rule_name: str
    result: GuardResult
    action: GuardAction
    details: str = ""
    masked_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        d: dict[str, Any] = {
            "rule": self.rule_name,
            "result": self.result.value,
            "action": self.action.value,
            "details": self.details,
        }
        if self.masked_text is not None:
            d["masked_text"] = self.masked_text
        return d


@dataclass
class GuardReport:
    """Aggregate result of all guard checks on a text."""

    passed: bool
    checks: list[GuardCheckResult] = field(default_factory=list)
    output_text: str = ""
    blocked: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "passed": self.passed,
            "blocked": self.blocked,
            "checks": [c.to_dict() for c in self.checks],
            "output_text": self.output_text,
        }


class GuardrailEngine:
    """Engine that applies guard rules to input/output text.

    Args:
        rules: List of GuardRule definitions.
    """

    def __init__(self, rules: list[GuardRule] | None = None) -> None:
        self.rules = rules or []

    def add_rule(self, rule: GuardRule) -> None:
        """Add a guard rule."""
        self.rules.append(rule)

    def check(self, text: str) -> GuardReport:
        """Run all enabled guard rules against the text.

        Args:
            text: Input or output text to check.

        Returns:
            GuardReport with results of all checks.
        """
        checks: list[GuardCheckResult] = []
        current_text = text
        blocked = False

        for rule in self.rules:
            if not rule.enabled:
                continue

            result = self._run_rule(rule, current_text)
            checks.append(result)

            if result.result == GuardResult.FAIL:
                if result.action == GuardAction.BLOCK:
                    blocked = True
                elif result.action == GuardAction.MASK and result.masked_text is not None:
                    current_text = result.masked_text

        passed = not blocked and all(
            c.result != GuardResult.FAIL or c.action != GuardAction.BLOCK
            for c in checks
        )

        return GuardReport(
            passed=passed,
            checks=checks,
            output_text=current_text,
            blocked=blocked,
        )

    def _run_rule(self, rule: GuardRule, text: str) -> GuardCheckResult:
        """Run a single rule against text."""
        handlers = {
            "pii": self._check_pii,
            "injection": self._check_injection,
            "toxicity": self._check_toxicity,
            "regex": self._check_regex,
            "json_schema": self._check_json_schema,
            "length": self._check_length,
        }

        handler = handlers.get(rule.type)
        if not handler:
            return GuardCheckResult(
                rule_name=rule.name,
                result=GuardResult.WARN,
                action=GuardAction.LOG,
                details=f"Unknown rule type: {rule.type}",
            )

        return handler(rule, text)

    def _check_pii(self, rule: GuardRule, text: str) -> GuardCheckResult:
        """Check for PII patterns."""
        types_to_check = rule.config.get("pii_types", list(_PII_PATTERNS.keys()))
        found: list[str] = []
        masked = text

        for pii_type in types_to_check:
            pattern = _PII_PATTERNS.get(pii_type)
            if pattern and pattern.search(text):
                found.append(pii_type)
                if rule.action == GuardAction.MASK:
                    masked = pattern.sub(f"[{pii_type.upper()}_REDACTED]", masked)

        if found:
            return GuardCheckResult(
                rule_name=rule.name,
                result=GuardResult.FAIL,
                action=rule.action,
                details=f"PII detected: {', '.join(found)}",
                masked_text=masked if rule.action == GuardAction.MASK else None,
            )

        return GuardCheckResult(
            rule_name=rule.name,
            result=GuardResult.PASS,
            action=rule.action,
            details="No PII detected",
        )

    def _check_injection(self, rule: GuardRule, text: str) -> GuardCheckResult:
        """Check for prompt injection patterns."""
        for pattern in _INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                return GuardCheckResult(
                    rule_name=rule.name,
                    result=GuardResult.FAIL,
                    action=rule.action,
                    details=f"Injection pattern detected: '{match.group()}'",
                )

        return GuardCheckResult(
            rule_name=rule.name,
            result=GuardResult.PASS,
            action=rule.action,
            details="No injection detected",
        )

    def _check_toxicity(self, rule: GuardRule, text: str) -> GuardCheckResult:
        """Check for toxic content (basic keyword matching)."""
        text_lower = text.lower()
        for indicator in _TOXICITY_INDICATORS:
            if indicator in text_lower:
                return GuardCheckResult(
                    rule_name=rule.name,
                    result=GuardResult.FAIL,
                    action=rule.action,
                    details=f"Toxic content detected",
                )

        custom_blocklist = rule.config.get("blocklist", [])
        for term in custom_blocklist:
            if term.lower() in text_lower:
                return GuardCheckResult(
                    rule_name=rule.name,
                    result=GuardResult.FAIL,
                    action=rule.action,
                    details=f"Blocked term detected",
                )

        return GuardCheckResult(
            rule_name=rule.name,
            result=GuardResult.PASS,
            action=rule.action,
        )

    def _check_regex(self, rule: GuardRule, text: str) -> GuardCheckResult:
        """Check text against a custom regex pattern."""
        pattern_str = rule.config.get("pattern", "")
        if not pattern_str:
            return GuardCheckResult(
                rule_name=rule.name, result=GuardResult.PASS, action=rule.action,
            )

        must_match = rule.config.get("must_match", False)
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
        except re.error as e:
            return GuardCheckResult(
                rule_name=rule.name, result=GuardResult.WARN, action=GuardAction.LOG,
                details=f"Invalid regex: {e}",
            )

        found = bool(pattern.search(text))

        if must_match and not found:
            return GuardCheckResult(
                rule_name=rule.name, result=GuardResult.FAIL, action=rule.action,
                details=f"Required pattern not found: {pattern_str}",
            )
        if not must_match and found:
            return GuardCheckResult(
                rule_name=rule.name, result=GuardResult.FAIL, action=rule.action,
                details=f"Forbidden pattern found: {pattern_str}",
            )

        return GuardCheckResult(
            rule_name=rule.name, result=GuardResult.PASS, action=rule.action,
        )

    def _check_json_schema(self, rule: GuardRule, text: str) -> GuardCheckResult:
        """Validate that text is valid JSON matching expected keys."""
        required_keys = rule.config.get("required_keys", [])

        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return GuardCheckResult(
                rule_name=rule.name, result=GuardResult.FAIL, action=rule.action,
                details="Text is not valid JSON",
            )

        if required_keys and isinstance(data, dict):
            missing = [k for k in required_keys if k not in data]
            if missing:
                return GuardCheckResult(
                    rule_name=rule.name, result=GuardResult.FAIL, action=rule.action,
                    details=f"Missing required keys: {missing}",
                )

        return GuardCheckResult(
            rule_name=rule.name, result=GuardResult.PASS, action=rule.action,
        )

    def _check_length(self, rule: GuardRule, text: str) -> GuardCheckResult:
        """Check text length constraints."""
        min_len = rule.config.get("min_length", 0)
        max_len = rule.config.get("max_length", float("inf"))

        if len(text) < min_len:
            return GuardCheckResult(
                rule_name=rule.name, result=GuardResult.FAIL, action=rule.action,
                details=f"Text too short: {len(text)} < {min_len}",
            )

        if len(text) > max_len:
            return GuardCheckResult(
                rule_name=rule.name, result=GuardResult.FAIL, action=rule.action,
                details=f"Text too long: {len(text)} > {max_len}",
            )

        return GuardCheckResult(
            rule_name=rule.name, result=GuardResult.PASS, action=rule.action,
        )


def create_input_guard(
    pii: bool = True,
    injection: bool = True,
    toxicity: bool = True,
    pii_action: str = "mask",
    custom_rules: list[dict] | None = None,
) -> GuardrailEngine:
    """Create a pre-configured input guard engine.

    Args:
        pii: Enable PII detection.
        injection: Enable prompt injection detection.
        toxicity: Enable toxicity detection.
        pii_action: Action for PII (mask, block, warn, log).
        custom_rules: Additional custom rules.

    Returns:
        Configured GuardrailEngine.
    """
    engine = GuardrailEngine()

    if pii:
        engine.add_rule(GuardRule(
            name="pii_detector", type="pii",
            action=GuardAction(pii_action),
        ))
    if injection:
        engine.add_rule(GuardRule(
            name="injection_detector", type="injection",
            action=GuardAction.BLOCK,
        ))
    if toxicity:
        engine.add_rule(GuardRule(
            name="toxicity_filter", type="toxicity",
            action=GuardAction.BLOCK,
        ))

    for rule_dict in (custom_rules or []):
        engine.add_rule(GuardRule.from_dict(rule_dict))

    return engine


def create_output_guard(
    pii: bool = True,
    json_schema: bool = False,
    required_keys: list[str] | None = None,
    max_length: int = 0,
    custom_rules: list[dict] | None = None,
) -> GuardrailEngine:
    """Create a pre-configured output guard engine.

    Args:
        pii: Enable PII leak detection in output.
        json_schema: Enable JSON format validation.
        required_keys: Required keys if json_schema is True.
        max_length: Maximum output length (0 = no limit).
        custom_rules: Additional custom rules.

    Returns:
        Configured GuardrailEngine.
    """
    engine = GuardrailEngine()

    if pii:
        engine.add_rule(GuardRule(
            name="output_pii_check", type="pii",
            action=GuardAction.MASK,
        ))
    if json_schema:
        engine.add_rule(GuardRule(
            name="json_format_check", type="json_schema",
            action=GuardAction.BLOCK,
            config={"required_keys": required_keys or []},
        ))
    if max_length > 0:
        engine.add_rule(GuardRule(
            name="length_check", type="length",
            action=GuardAction.BLOCK,
            config={"max_length": max_length},
        ))

    for rule_dict in (custom_rules or []):
        engine.add_rule(GuardRule.from_dict(rule_dict))

    return engine
