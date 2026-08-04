from dataclasses import dataclass, field
from typing import Callable

# Default per-design stances: cycled across the parallel designs in an iteration (design m gets
# stance m % len(design_stances)) so they explore different regions of the solution space without
# any extra LLM calls - just a different one-line steer in each orchestrator prompt.
DEFAULT_DESIGN_STANCES = [
    "Conventional & robust - take the most direct, straightforward approach that reliably satisfies the criteria.",
    "Depth-first - pick the single most important question or requirement and answer it far more thoroughly than the rest; keep everything else minimal.",
    "Contrarian - name one assumption a conventional approach here would rely on, then design an approach that doesn't depend on it.",
]


@dataclass
class PipelineConfig:
    """Configuration for the multi-agent code-generation pipeline.

    This is the swap point for adapting the pipeline to a new domain.
    Create a new config file (e.g. bioimage_config.py) and pass an instance
    of PipelineConfig to generate_and_optimize().
    """
    orchestrator_model: str
    worker_model: str
    compiler_model: str
    requirements_evaluator_model: str
    # D2 ideation stage (generate_angles): cheap tier, no default here - set explicitly per config
    # like the other model-role fields above, so every domain config stays deliberate about it
    # (relevant for e.g. cbias, where model routing is a data-sensitivity decision, not just cost).
    angle_model: str
    # D5 judging (judge_insight/judge_soundness): frontier Anthropic tier, no default here - once
    # req_score is gone these two judges are the entire quality bar (DIVERGER_PLAN.md §5), so every
    # domain config stays deliberate about it rather than inheriting a cost-driven default.
    judge_model: str
    docker_image: str
    available_libraries: str
    domain_notes: str
    extract_input_metadata: Callable[[str], str]
    design_stances: list[str] = field(default_factory=lambda: list(DEFAULT_DESIGN_STANCES))
    # D4 dedup: token-set Jaccard threshold (over hypothesis + variables_involved + rough_method)
    # above which two angles are treated as near-duplicates. 0.22 is measured, not guessed - two
    # live cbias runs put near-duplicates at 0.23 and 0.30-0.40, and genuinely distinct angles at
    # 0.08-0.19 (see DIVERGER_PLAN.md D4). A real default (unlike angle_model/judge_model) since
    # it's a calibrated constant, not a per-domain judgment call.
    angle_similarity_threshold: float = 0.22
