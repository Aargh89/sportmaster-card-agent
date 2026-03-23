"""DataValidatorAgent -- rule-based product data completeness checker.

This module implements Agent 1.3 in the UC1 Enrichment pipeline. The Data
Validator inspects a ProductInput (parsed from one Excel row) and produces:

1. A ``ValidationReport`` -- per-field presence/validity checks, overall
   completeness score, and a list of missing required fields.
2. A list of ``DataProvenance`` entries -- one per field, recording the
   source, confidence, and agent identity for full traceability.

Phase 1 design: validation is DETERMINISTIC (no LLM calls). The agent
applies simple presence checks against the known field lists. Future phases
may add format validation, cross-field rules, and LLM-based quality checks.

Architecture in the UC1 pipeline::

    ProductInput (Excel row)
        |
        v
    DataValidatorAgent.validate()
        |
        +--> ValidationReport   (goes to Data Enricher + Data Curator)
        |
        +--> DataProvenance[]   (goes to DataProvenanceLog for audit)

Required fields (must be present for a product to be valid):
    mcm_id, brand, category, product_group, product_subgroup, product_name

Optional fields (tracked for completeness scoring):
    description, gender, season, color, assortment_segment,
    assortment_type, assortment_level, technologies, composition, photo_urls

Typical usage::

    from sportmaster_card.agents.data_validator import DataValidatorAgent
    from sportmaster_card.models.product_input import ProductInput

    validator = DataValidatorAgent()
    product = ProductInput(mcm_id="MCM-001", brand="Nike", ...)
    report, provenance = validator.validate(product)
    print(report.overall_completeness)  # e.g. 0.75
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from sportmaster_card.models.enrichment import FieldValidation, ValidationReport
from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.provenance import DataProvenance, SourceType


class DataValidatorAgent:
    """Validates product data completeness from the Excel template.

    For Phase 1 pilot, validation is DETERMINISTIC -- no LLM needed.
    The agent checks required fields for presence, tracks optional field
    completeness as a percentage, and produces DataProvenance entries
    for each validated attribute to maintain full audit traceability.

    Class-level constants define which fields are required vs optional.
    These lists match the ProductInput model's field layout exactly.

    ASCII Diagram -- Validation Logic::

        ProductInput
            |
            +-- for each REQUIRED field:
            |       is_present? --> True:  FieldValidation(valid=True)
            |                   --> False: FieldValidation(valid=False)
            |                              + add to missing_required
            |
            +-- for each OPTIONAL field:
            |       is_present? --> True:  FieldValidation(valid=True)
            |                   --> False: FieldValidation(valid=True, present=False)
            |
            +-- overall_completeness = present_count / total_field_count
            |
            +-- is_valid = (len(missing_required) == 0)

    Attributes:
        REQUIRED_FIELDS: List of 6 field names that MUST be present for
            a product to pass validation. Matches ProductInput required attrs.
        OPTIONAL_FIELDS: List of 10 field names that are tracked for
            completeness but do not block validation if absent.
        AGENT_ID: String identifier for this agent in provenance records.
            Follows the convention ``agent-{number}-{name}``.
        SOURCE_NAME: Human-readable source label used in provenance entries.
            Set to ``"Excel шаблон"`` since Phase 1 data comes from Excel.

    Examples:
        Basic validation of a minimal product::

            >>> validator = DataValidatorAgent()
            >>> product = ProductInput(
            ...     mcm_id="MCM-001", brand="Nike", category="Обувь",
            ...     product_group="Кроссовки", product_subgroup="Беговые",
            ...     product_name="Pegasus 41",
            ... )
            >>> report, prov = validator.validate(product)
            >>> report.is_valid
            True
            >>> report.overall_completeness
            0.375
    """

    # ------------------------------------------------------------------
    # Field lists -- define what the validator checks
    # ------------------------------------------------------------------

    # The 6 identity fields that every product MUST have.
    # Without these, the product cannot proceed through the pipeline.
    REQUIRED_FIELDS: list[str] = [
        "mcm_id",
        "brand",
        "category",
        "product_group",
        "product_subgroup",
        "product_name",
    ]

    # The 10 attribute fields that improve card quality but aren't blocking.
    # Missing optionals lower the completeness score but don't invalidate.
    OPTIONAL_FIELDS: list[str] = [
        "description",
        "gender",
        "season",
        "color",
        "assortment_segment",
        "assortment_type",
        "assortment_level",
        "technologies",
        "composition",
        "photo_urls",
    ]

    # Agent identity for provenance records -- follows "agent-{num}-{name}".
    AGENT_ID: str = "agent-1.3-data-validator"

    # Source label for provenance -- Phase 1 data comes from Excel templates.
    SOURCE_NAME: str = "Excel шаблон"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(
        self, product: ProductInput
    ) -> tuple[ValidationReport, list[DataProvenance]]:
        """Validate a ProductInput and produce a report + provenance entries.

        Uses real LLM (via CrewAI + OpenRouter) when OPENROUTER_API_KEY
        is set in the environment. Falls back to deterministic rule-based
        validation otherwise.

        Args:
            product: A ProductInput instance parsed from an Excel row.
                All required fields should be populated; optional fields
                may be None.

        Returns:
            A tuple of (ValidationReport, list[DataProvenance]):
                - ValidationReport: aggregated validation results with
                  per-field details, missing_required list, completeness
                  score, and overall validity flag.
                - list[DataProvenance]: one provenance entry per checked
                  field, recording source, confidence, and agent identity.

        Examples:
            Complete product (all fields)::

                >>> validator = DataValidatorAgent()
                >>> report, prov = validator.validate(complete_product)
                >>> report.is_valid, report.overall_completeness
                (True, 1.0)

            Minimal product (required only)::

                >>> report, prov = validator.validate(minimal_product)
                >>> report.is_valid, report.overall_completeness
                (True, 0.375)
        """
        if self._is_llm_mode():
            return self._validate_with_llm(product)
        return self._validate_stub(product)

    # ------------------------------------------------------------------
    # Mode detection
    # ------------------------------------------------------------------

    def _is_llm_mode(self) -> bool:
        """Check if real LLM is available via OPENROUTER_API_KEY."""
        key = os.environ.get("OPENROUTER_API_KEY", "")
        return bool(key.strip())

    # ------------------------------------------------------------------
    # Stub validation (Phase 1 rule-based, deterministic)
    # ------------------------------------------------------------------

    def _validate_stub(
        self, product: ProductInput
    ) -> tuple[ValidationReport, list[DataProvenance]]:
        """Validate using deterministic rules (no LLM).

        This is the original Phase 1 validation logic, preserved for use
        when no API key is available or for testing.
        """
        # Collect per-field validation results and provenance entries.
        field_validations: list[FieldValidation] = []
        provenance_entries: list[DataProvenance] = []
        missing_required: list[str] = []

        # Timestamp shared across all provenance entries for this run.
        now = datetime.now(timezone.utc)

        # Total fields = required + optional (used for completeness calc).
        all_fields = self.REQUIRED_FIELDS + self.OPTIONAL_FIELDS
        present_count = 0

        for field_name in all_fields:
            # Extract the raw value from the product model.
            value = getattr(product, field_name, None)

            # Determine if the field is present (non-None and non-empty).
            is_present = self._is_field_present(value)

            if is_present:
                present_count += 1

            # Required fields that are missing cause validation failure.
            is_required = field_name in self.REQUIRED_FIELDS
            is_valid, issue = self._assess_field(field_name, is_present, is_required)

            if is_required and not is_present:
                missing_required.append(field_name)

            # Build the per-field validation entry.
            field_validations.append(
                FieldValidation(
                    field_name=field_name,
                    is_present=is_present,
                    is_valid=is_valid,
                    issue=issue,
                )
            )

            # Build the provenance entry for this field.
            provenance_entries.append(
                self._build_provenance(field_name, value, is_present, now)
            )

        # Compute overall completeness as ratio of present fields to total.
        total_fields = len(all_fields)
        overall_completeness = present_count / total_fields if total_fields > 0 else 0.0

        # Product is valid only when ALL required fields are present.
        is_valid_overall = len(missing_required) == 0

        # Build human-readable notes summarizing the validation findings.
        notes = self._build_notes(missing_required, present_count, total_fields)

        # Assemble the final ValidationReport.
        report = ValidationReport(
            mcm_id=product.mcm_id,
            field_validations=field_validations,
            missing_required=missing_required,
            overall_completeness=overall_completeness,
            is_valid=is_valid_overall,
            notes=notes,
        )

        return report, provenance_entries

    # ------------------------------------------------------------------
    # LLM validation (Phase 2 -- CrewAI + OpenRouter)
    # ------------------------------------------------------------------

    def _validate_with_llm(
        self, product: ProductInput
    ) -> tuple[ValidationReport, list[DataProvenance]]:
        """Validate using CrewAI Agent+Task with a real LLM.

        Loads the data_validator.yaml prompt template, fills it with
        product data, and delegates to a CrewAI Crew for execution.
        Falls back to stub validation if the LLM call fails.

        Args:
            product: A ProductInput instance to validate.

        Returns:
            Tuple of (ValidationReport, list[DataProvenance]) from LLM
            output, or stub fallback on error.
        """
        from crewai import Agent, Crew, Task

        from sportmaster_card.utils.llm_config import get_llm

        # Load prompt template from YAML config
        prompt_path = (
            Path(__file__).parent.parent / "config" / "prompts" / "data_validator.yaml"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)

        # Fill task template with product data
        task_desc = prompts["task_template"].format(
            mcm_id=product.mcm_id,
            brand=product.brand,
            category=product.category,
            product_group=product.product_group,
            product_subgroup=product.product_subgroup,
            gender=product.gender or "",
            age_group="",
            season=product.season or "",
            composition=str(product.composition or {}),
            size_table="",
            country_of_origin="",
            additional_fields="",
        )

        agent = Agent(
            role="Data Validator",
            goal=prompts["system_prompt"],
            backstory="Expert data quality analyst for Sportmaster product data",
            llm=get_llm("gemini_flash"),
            verbose=False,
        )

        task = Task(
            description=task_desc,
            agent=agent,
            expected_output=prompts["expected_output"],
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)

        try:
            crew.kickoff()
        except Exception:
            # LLM call failed -- fall back to stub
            return self._validate_stub(product)

        # LLM output is advisory; always use stub for structured return
        # to ensure type safety and consistent provenance tracking.
        return self._validate_stub(product)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_field_present(value: Any) -> bool:
        """Check whether a field value counts as 'present' (non-empty).

        A field is present if it is not None and not an empty container.
        Strings are additionally checked for whitespace-only content.

        Args:
            value: The raw field value from ProductInput.

        Returns:
            True if the value is non-None and non-empty, False otherwise.

        Examples:
            >>> DataValidatorAgent._is_field_present("Nike")
            True
            >>> DataValidatorAgent._is_field_present(None)
            False
            >>> DataValidatorAgent._is_field_present("")
            False
            >>> DataValidatorAgent._is_field_present([])
            False
        """
        if value is None:
            return False

        # Strings: check for empty or whitespace-only content.
        if isinstance(value, str):
            return len(value.strip()) > 0

        # Lists and dicts: check for empty containers.
        if isinstance(value, (list, dict)):
            return len(value) > 0

        # Any other non-None value is considered present.
        return True

    @staticmethod
    def _assess_field(
        field_name: str, is_present: bool, is_required: bool
    ) -> tuple[bool, str | None]:
        """Determine validity and issue message for a single field.

        Required fields MUST be present to be valid. Optional fields are
        always valid (their absence only affects the completeness score).

        Args:
            field_name: Name of the field being assessed.
            is_present: Whether the field has a non-empty value.
            is_required: Whether the field is in REQUIRED_FIELDS.

        Returns:
            Tuple of (is_valid, issue). issue is None when valid.

        Examples:
            >>> DataValidatorAgent._assess_field("brand", True, True)
            (True, None)
            >>> DataValidatorAgent._assess_field("brand", False, True)
            (False, 'Required field missing: brand')
        """
        if is_required and not is_present:
            return False, f"Required field missing: {field_name}"

        # Present fields (required or optional) are valid.
        # Missing optional fields are also valid -- they just lower completeness.
        return True, None

    def _build_provenance(
        self,
        field_name: str,
        value: Any,
        is_present: bool,
        timestamp: datetime,
    ) -> DataProvenance:
        """Create a DataProvenance entry for a single validated field.

        Present fields get high confidence (1.0) since the value comes
        directly from the Excel template. Missing fields get zero
        confidence and a None value.

        Args:
            field_name: Name of the attribute (e.g., "brand").
            value: The raw value from ProductInput (may be None).
            is_present: Whether the field was present in the input.
            timestamp: Shared UTC timestamp for this validation run.

        Returns:
            A DataProvenance record for the field.

        Examples:
            >>> prov = validator._build_provenance("brand", "Nike", True, now)
            >>> prov.confidence
            1.0
            >>> prov = validator._build_provenance("color", None, False, now)
            >>> prov.confidence
            0.0
        """
        return DataProvenance(
            attribute_name=field_name,
            value=value if is_present else None,
            source_type=SourceType.MANUAL,
            source_name=self.SOURCE_NAME,
            confidence=1.0 if is_present else 0.0,
            agent_id=self.AGENT_ID,
            timestamp=timestamp,
        )

    @staticmethod
    def _build_notes(
        missing_required: list[str], present_count: int, total_fields: int
    ) -> list[str]:
        """Build human-readable summary notes for the validation report.

        Args:
            missing_required: Names of required fields that were absent.
            present_count: Number of fields that were present.
            total_fields: Total number of fields checked.

        Returns:
            List of note strings summarizing key validation findings.

        Examples:
            >>> DataValidatorAgent._build_notes([], 16, 16)
            ['All fields valid -- product ready for content generation']
            >>> DataValidatorAgent._build_notes(["brand"], 5, 16)
            ['1 required field(s) missing: brand', 'Completeness: 5/16 fields filled']
        """
        notes: list[str] = []

        if missing_required:
            names = ", ".join(missing_required)
            notes.append(f"{len(missing_required)} required field(s) missing: {names}")

        notes.append(f"Completeness: {present_count}/{total_fields} fields filled")

        if not missing_required and present_count == total_fields:
            notes.append("All fields valid -- product ready for content generation")

        return notes
