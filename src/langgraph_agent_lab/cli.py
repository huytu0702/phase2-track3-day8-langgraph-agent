"""CLI for the lab."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
import yaml

from .metrics import MetricsReport, write_metrics
from .report import write_report
from .runner import resume_thread, run_scenario_by_id
from .runner import run_scenarios as run_scenario_batch
from .web_server import serve

app = typer.Typer(no_args_is_help=True)


def load_config(config: Path) -> dict:
    return yaml.safe_load(config.read_text(encoding="utf-8"))


@app.command("run-scenario")
def run_one_scenario(
    scenario_id: Annotated[str, typer.Option("--id")],
    thread_id: Annotated[str | None, typer.Option("--thread-id")] = None,
    config: Annotated[Path, typer.Option("--config")] = Path("configs/lab.yaml"),
) -> None:
    cfg = load_config(config)
    result = run_scenario_by_id(
        scenario_id,
        scenarios_path=Path(cfg["scenarios_path"]),
        checkpointer_kind=cfg.get("checkpointer", "memory"),
        database_url=cfg.get("database_url"),
        thread_id=thread_id,
    )
    typer.echo(json.dumps({"state": result.state, "metric": result.metric.model_dump()}, indent=2))


@app.command("run-scenarios")
def run_scenarios(
    config: Annotated[Path, typer.Option("--config")],
    output: Annotated[Path, typer.Option("--output")],
) -> None:
    cfg = load_config(config)
    report = run_scenario_batch(
        scenarios_path=Path(cfg["scenarios_path"]),
        checkpointer_kind=cfg.get("checkpointer", "memory"),
        database_url=cfg.get("database_url"),
        include_hitl=False,
    )
    write_metrics(report, output)
    if cfg.get("report_path"):
        write_report(report, cfg["report_path"])
    typer.echo(f"Wrote metrics to {output}")


@app.command("resume")
def resume(
    thread_id: Annotated[str, typer.Option("--thread-id")],
    approve: Annotated[bool, typer.Option("--approve")],
    comment: Annotated[str, typer.Option("--comment")] = "",
    config: Annotated[Path, typer.Option("--config")] = Path("configs/lab.yaml"),
) -> None:
    cfg = load_config(config)
    state = resume_thread(
        thread_id=thread_id,
        approval={"approved": approve, "reviewer": "cli", "comment": comment},
        checkpointer_kind=cfg.get("checkpointer", "memory"),
        database_url=cfg.get("database_url"),
    )
    typer.echo(json.dumps(state, indent=2))


@app.command("serve-ui")
def serve_ui(config: Annotated[Path, typer.Option("--config")] = Path("configs/lab.yaml")) -> None:
    cfg = load_config(config)
    web = cfg.get("web", {})
    serve(
        host=web.get("host", "127.0.0.1"),
        port=int(web.get("port", 8765)),
        scenarios_path=Path(cfg["scenarios_path"]),
        checkpointer_kind=cfg.get("checkpointer", "memory"),
        database_url=cfg.get("database_url"),
    )


@app.command("validate-metrics")
def validate_metrics(metrics: Annotated[Path, typer.Option("--metrics")]) -> None:
    payload = json.loads(metrics.read_text(encoding="utf-8"))
    report = MetricsReport.model_validate(payload)
    if report.total_scenarios < 6:
        raise typer.BadParameter("Expected at least 6 scenarios")
    typer.echo(f"Metrics valid. success_rate={report.success_rate:.2%}")


if __name__ == "__main__":
    app()
