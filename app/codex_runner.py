from __future__ import annotations

from pathlib import Path
import os
import shlex
import subprocess

from app.config import Settings
from app.models import JobRecord


def build_prompt(batch_prefix: str, batch_id: str, index: int, prompt: str, reference_images: list[str] | None = None) -> str:
    lines = [
        batch_prefix,
        f'Batch: {batch_id}',
        f'Job: {index + 1}',
    ]
    if reference_images:
        lines.extend(["Reference images:"])
        lines.extend(f"- {path}" for path in reference_images)
    lines.extend([
        "Request:",
        prompt.strip(),
        "",
        "Use the reference images when provided, following their relevant composition, subject, style, colors, or layout as requested.",
        "Return the generated image result and any output paths or status details.",
    ])
    return '\n'.join(lines)


def command_parts(job: JobRecord, settings: Settings) -> list[str]:
    command = [
        str(settings.codex_bin),
        "exec",
        "--model",
        settings.codex_model,
        "--skip-git-repo-check",
        "--color",
        "never",
        "-C",
        job.workdir,
    ]
    command.append(build_prompt(settings.batch_prefix, job.batch_id, job.index, job.prompt, getattr(job, "reference_images", [])))
    for image_path in getattr(job, "reference_images", []):
        command.extend(["--image", image_path])
    return command


def command_string(job: JobRecord, settings: Settings) -> str:
    command = command_parts(job, settings)
    rendered = subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)
    return f"HOME={settings.codex_user_home} CODEX_HOME={settings.codex_home} TERM=xterm-256color {rendered}"


def prepare_job(job: JobRecord, settings: Settings) -> None:
    job_dir = Path(job.log_path).parent
    job_dir.mkdir(parents=True, exist_ok=True)
    Path(job.prompt_path).write_text(job.prompt, encoding='utf-8')
