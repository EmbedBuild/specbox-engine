"""Tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from src.models import (
    WORKFLOW_LIST_NAMES,
    LIST_NAME_TO_STATE,
    AcceptanceCriterion,
    ImportSpec,
    UseCaseSpec,
    UserStorySpec,
)


class TestWorkflowStates:
    def test_list_names(self):
        assert WORKFLOW_LIST_NAMES["backlog"] == "Backlog"
        assert WORKFLOW_LIST_NAMES["done"] == "Done"
        assert len(WORKFLOW_LIST_NAMES) == 5

    def test_reverse_mapping(self):
        assert LIST_NAME_TO_STATE["Backlog"] == "backlog"
        assert LIST_NAME_TO_STATE["In Progress"] == "in_progress"


class TestImportSpec:
    def test_minimal_spec(self):
        spec = ImportSpec(user_stories=[
            UserStorySpec(
                us_id="US-01",
                name="Auth",
                use_cases=[
                    UseCaseSpec(uc_id="UC-001", name="Login"),
                ],
            ),
        ])
        assert len(spec.user_stories) == 1
        assert spec.user_stories[0].us_id == "US-01"
        assert len(spec.user_stories[0].use_cases) == 1

    def test_full_spec(self):
        spec = ImportSpec(user_stories=[
            UserStorySpec(
                us_id="US-01",
                name="Auth",
                hours=11,
                screens="1A, 1B",
                description="Full auth system",
                use_cases=[
                    UseCaseSpec(
                        uc_id="UC-001",
                        name="Login",
                        actor="Todos",
                        hours=3,
                        screens="1A",
                        acceptance_criteria=["Validates email", "Shows error"],
                        context="Supabase Auth",
                    ),
                    UseCaseSpec(
                        uc_id="UC-002",
                        name="Register",
                        actor="Todos",
                        hours=4,
                    ),
                ],
            ),
        ])
        assert spec.user_stories[0].hours == 11
        assert len(spec.user_stories[0].use_cases[0].acceptance_criteria) == 2

    def test_empty_stories(self):
        spec = ImportSpec(user_stories=[])
        assert spec.user_stories == []


class TestAcceptanceCriterion:
    def test_defaults(self):
        ac = AcceptanceCriterion(id="AC-01", text="Validates email")
        assert ac.done is False

    def test_done(self):
        ac = AcceptanceCriterion(id="AC-01", text="Validates email", done=True)
        assert ac.done is True
