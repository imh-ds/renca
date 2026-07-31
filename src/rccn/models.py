"""Versioned, language-neutral analysis configuration contracts."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0.0"


class MissingDataPolicy(StrEnum):
    """Predeclared policy for handling missing observations."""

    COMPLETE_CASE = "complete_case"
    MULTIPLE_IMPUTATION = "multiple_imputation"
    MODEL_BASED = "model_based"


class OutcomeType(StrEnum):
    """Outcome types supported by the first confirmatory engine."""

    CONTINUOUS = "continuous"
    BINARY = "binary"


class LossName(StrEnum):
    """Losses supported by the first confirmatory engine."""

    SQUARED = "squared"
    BRIER = "brier"


class SamplingUnit(StrEnum):
    """Sampling-unit declaration used by the later audit stage."""

    IID = "iid"
    CLUSTERED = "clustered"


class Model(BaseModel):
    """Shared strict model configuration."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SplitSpec(Model):
    """Predeclared outer-split and inference-fold settings."""

    selection_fraction: Annotated[float, Field(gt=0, lt=0.5)] = 0.2
    inference_folds: Annotated[int, Field(ge=2)] = 5


class DesignSpec(Model):
    """Declared sampling design metadata."""

    sampling_unit: SamplingUnit
    cluster_id_column: str | None = None

    @model_validator(mode="after")
    def require_cluster_identifier_when_clustered(self) -> "DesignSpec":
        if self.sampling_unit is SamplingUnit.CLUSTERED and not self.cluster_id_column:
            raise ValueError("cluster_id_column is required for clustered designs")
        if self.sampling_unit is SamplingUnit.IID and self.cluster_id_column is not None:
            raise ValueError("cluster_id_column is only valid for clustered designs")
        return self


class NodeSpec(Model):
    """Target-specific outcome, loss, and practical-resolution settings."""

    node_id: Annotated[str, Field(min_length=1, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")]
    outcome_type: OutcomeType
    loss: LossName
    delta: Annotated[float, Field(gt=0)]

    @model_validator(mode="after")
    def require_supported_loss_for_outcome(self) -> "NodeSpec":
        expected_loss = {
            OutcomeType.CONTINUOUS: LossName.SQUARED,
            OutcomeType.BINARY: LossName.BRIER,
        }[self.outcome_type]
        if self.loss is not expected_loss:
            raise ValueError(
                f"loss must be '{expected_loss.value}' for a {self.outcome_type.value} outcome"
            )
        return self


class ArtifactHeader(Model):
    """Metadata required at every external artifact boundary."""

    schema_version: Literal[SCHEMA_VERSION]
    analysis_id: UUID
    artifact_type: Annotated[str, Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")]


class ProjectSpec(Model):
    """Predeclared configuration required before an analysis can start."""

    schema_version: Literal[SCHEMA_VERSION]
    analysis_id: UUID
    missing_data_policy: MissingDataPolicy
    design: DesignSpec
    split: SplitSpec = Field(default_factory=SplitSpec)
    nodes: Annotated[list[NodeSpec], Field(min_length=2)]

    @model_validator(mode="after")
    def require_unique_node_ids(self) -> "ProjectSpec":
        node_ids = [node.node_id for node in self.nodes]
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("node_id values must be unique")
        return self


def load_project_spec(path: str | Path) -> ProjectSpec:
    """Load and validate a project specification from YAML or JSON."""

    project_path = Path(path)
    try:
        raw_text = project_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Unable to read project specification '{project_path}': {error}") from error

    try:
        if project_path.suffix.lower() == ".json":
            payload = json.loads(raw_text)
        else:
            payload = yaml.safe_load(raw_text)
    except (json.JSONDecodeError, yaml.YAMLError) as error:
        format_name = "JSON" if project_path.suffix.lower() == ".json" else "YAML"
        raise ValueError(f"Invalid {format_name} in '{project_path}': {error}") from error

    if not isinstance(payload, dict):
        raise ValueError(f"Project specification '{project_path}' must contain an object")
    return ProjectSpec.model_validate(payload)


def write_json_schemas(destination: str | Path) -> dict[str, Path]:
    """Write deterministic JSON Schemas for externally shared contracts."""

    output_directory = Path(destination)
    output_directory.mkdir(parents=True, exist_ok=True)
    contracts = {
        "project": (ProjectSpec, "project_spec.schema.json"),
        "node": (NodeSpec, "node_spec.schema.json"),
        "artifact_header": (ArtifactHeader, "artifact_header.schema.json"),
    }
    paths: dict[str, Path] = {}
    for contract_name, (model, filename) in contracts.items():
        output_path = output_directory / filename
        serialized_schema = json.dumps(
            model.model_json_schema(), indent=2, sort_keys=True, ensure_ascii=False
        )
        output_path.write_text(f"{serialized_schema}\n", encoding="utf-8")
        paths[contract_name] = output_path
    return paths
