"""Tests for the command line choosing between the router and the coordinator."""

from __future__ import annotations

from types import SimpleNamespace

from contoso_aero import cli
from contoso_aero.agents.common import AgentReply
from contoso_aero.coordination import Plan, PlanStep
from contoso_aero.routing import PipelineResult


def _result(label: str, **extra: object) -> PipelineResult:
    return PipelineResult(
        question="q", label=label, answer="The answer.", refused=False, intent=None,
        agent=AgentReply(agent=label, answer="The answer."), intent_seconds=0.5,
        agent_seconds=2.0, total_seconds=2.5, **extra)


def _patch_environment(monkeypatch, tmp_path, router, coordinator) -> None:
    database = tmp_path / "db.sqlite3"
    database.write_text("")
    monkeypatch.setattr(cli, "DataSettings",
                        lambda: SimpleNamespace(database_path=database, knowledge_dir=tmp_path))
    monkeypatch.setattr(cli, "load_model_settings",
                        lambda: SimpleNamespace(max_agent_steps=2))
    monkeypatch.setattr(cli, "ChatCompletionClient", lambda settings: object())
    monkeypatch.setattr(cli, "ask", router)
    monkeypatch.setattr(cli, "ask_coordinated", coordinator)


def test_given_no_flag_when_cli_runs_then_router_answers(monkeypatch, tmp_path, capsys) -> None:
    _patch_environment(monkeypatch, tmp_path, lambda q, c: _result("telemetry"),
                       lambda q, c: (_ for _ in ()).throw(AssertionError("coordinator used")))

    code = cli.main(["How many engines?"])

    assert code == 0 and "[telemetry]" in capsys.readouterr().out


def test_given_coordinator_flag_when_cli_runs_then_coordinator_answers(
    monkeypatch, tmp_path, capsys
) -> None:
    plan = Plan("plan", (PlanStep("s1", "service", "Why removed?", ()),
                         PlanStep("s2", "production", "Which plant?", ("s1",))))
    coordinated = _result("coordinator", agents_called=["service", "production"], plan=plan,
                          plan_seconds=0.4, step_seconds={"s1": 1.0, "s2": 1.5},
                          synthesis_seconds=0.6)
    _patch_environment(monkeypatch, tmp_path,
                       lambda q, c: (_ for _ in ()).throw(AssertionError("router used")),
                       lambda q, c: coordinated)

    code = cli.main(["--coordinator", "Why removed and where built?"])

    out = capsys.readouterr().out
    assert code == 0
    assert "service, production" in out
    assert "plan 0.40s" in out and "synthesis 0.60s" in out
