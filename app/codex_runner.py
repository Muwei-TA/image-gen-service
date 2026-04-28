from __future__ import annotations

from pathlib import Path
import shlex

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
    codex_args = [
        str(settings.codex_bin),
        "exec",
        "--skip-git-repo-check",
        "--color",
        "never",
        "-C",
        job.workdir,
    ]
    codex_args.append(build_prompt(settings.batch_prefix, job.batch_id, job.index, job.prompt, getattr(job, "reference_images", [])))
    for image_path in getattr(job, "reference_images", []):
        codex_args.extend(["--image", image_path])
    return [
        " ".join(
            [
                f"HOME={shlex.quote(str(settings.codex_user_home))}",
                f"CODEX_HOME={shlex.quote(str(settings.codex_home))}",
                "TERM=xterm-256color",
                shlex.join(codex_args),
            ]
        ),
    ]


def command_string(job: JobRecord, settings: Settings) -> str:
    return command_parts(job, settings)[0]


def prepare_job(job: JobRecord, settings: Settings) -> None:
    job_dir = Path(job.log_path).parent
    job_dir.mkdir(parents=True, exist_ok=True)
    Path(job.prompt_path).write_text(job.prompt, encoding='utf-8')
