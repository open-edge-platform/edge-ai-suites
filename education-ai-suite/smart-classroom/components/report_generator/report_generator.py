"""
Deterministic Report Generator for Classroom Evaluation.

Collects all available session data (statistics, summary, mindmap, transcription, etc.)
and passes it to the LLM to generate a structured report. No autonomous decision-making,
no ReAct loop — just a fixed pipeline: collect data → generate report.
"""

import time
import logging
import os

from components.report_generator.data_collector import DataCollector
from components.report_generator.prompts import (
    TEMPLATE_FILL_SYSTEM_EN,
    TEMPLATE_FILL_SYSTEM_ZH,
    TEMPLATE_FILL_GENERATED_PROMPT_EN,
    TEMPLATE_FILL_GENERATED_PROMPT_ZH,
    build_field_definitions,
)
from utils.config_loader import config
from utils.runtime_config_loader import RuntimeConfig
from utils.storage_manager import StorageManager
from utils.locks import audio_pipeline_lock
from components.report_generator.template_manager import (
    get_template_path,
    extract_template_structure,
    fill_template,
    parse_llm_json_response,
)
from components.report_generator.field_catalog import (
    get_field_kinds, get_known_field_codes, get_always_on_codes, get_manual_field_codes,
)
from components.report_generator.raw_field_mapper import resolve_raw_fields
from components.report_generator.field_store import load_store, save_store

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Deterministic report generator.

    Pipeline: Collect all available data → Build prompt → Stream LLM output.
    """

    IMAGE_FIELD_CODES = frozenset({"mindmap"})

    # High-signal, already-distilled sources fed to the generated-field LLM call.
    # The measured numbers from the other sources (transcription/segmentation
    # stats, class statistics) reach the model as Known Facts, so their bulky
    # verbatim samples add prefill cost without adding signal and are dropped.
    _GEN_CONTEXT_SOURCES = ("class_summary", "mindmap", "topic_segmentation")

    # Selection coupling rules: when ``primary`` is unchecked, all ``hide``
    # fields are force-hidden (can override always_on).
    _SELECTION_HIDE_RULES = (
        {"primary": "keywords", "hide": ("keywords_count",)},
    )

    def __init__(self, session_id: str, model=None, template_name: str = None,
                 selected_fields=None, manual_fields=None):
        self.session_id = session_id
        self.model = model
        self.language = config.app.language
        self.template_name = template_name  # selected report template from the library
        self.selected_fields = selected_fields
        self.manual_fields = manual_fields or {}
        self.data_collector = DataCollector(session_id)
        self.collected_data = []
        self.collected_by_source = {}

    def _get_session_dir(self) -> str:
        project_config = RuntimeConfig.get_section("Project")
        return os.path.join(
            project_config.get("location"),
            project_config.get("name"),
            self.session_id,
        )

    def _collect_all_data(self):
        """Deterministically collect all available session data."""
        data_sources = [
            ("class_statistics", "读取课堂统计" if self.language == "zh" else "Read class statistics"),
            ("class_summary", "读取课堂摘要" if self.language == "zh" else "Read class summary"),
            ("mindmap", "读取思维导图" if self.language == "zh" else "Read mind map"),
            ("topic_segmentation", "读取主题分段" if self.language == "zh" else "Read topic segmentation"),
            ("teacher_transcription", "读取教师转录" if self.language == "zh" else "Read teacher transcription"),
            ("content_segmentation", "读取内容分段" if self.language == "zh" else "Read content segmentation"),
        ]

        for source_name, _ in data_sources:
            result = self.data_collector.read(source_name)
            if result is not None:
                self.collected_data.append(f"[{source_name}] {result}")
                self.collected_by_source[source_name] = result

    def _build_generated_fill_prompt(self, template_structure: dict, gen_codes: list, raw_values: dict) -> str:
        """Build the split-fill prompt asking the LLM for ONLY the generated fields.

        Measured raw values are passed as Known Facts for grounding but are not
        requested back from the model.
        """
        import json as _json

        trimmed = [self.collected_by_source[s] for s in self._GEN_CONTEXT_SOURCES
                   if s in self.collected_by_source]
        observations_text = "\n\n---\n\n".join(trimmed) if trimmed \
            else "\n\n---\n\n".join(self.collected_data)
        fields_json = _json.dumps(gen_codes, ensure_ascii=False)
        known_facts = _json.dumps(raw_values, ensure_ascii=False)
        field_definitions = build_field_definitions(gen_codes, self.language)

        if self.language == "zh":
            system_msg = TEMPLATE_FILL_SYSTEM_ZH
            user_content = TEMPLATE_FILL_GENERATED_PROMPT_ZH.format(
                template_raw_text=template_structure["raw_text"],
                known_facts=known_facts,
                collected_data=observations_text,
                fields_json=fields_json,
                field_definitions=field_definitions,
            )
        else:
            system_msg = TEMPLATE_FILL_SYSTEM_EN
            user_content = TEMPLATE_FILL_GENERATED_PROMPT_EN.format(
                template_raw_text=template_structure["raw_text"],
                known_facts=known_facts,
                collected_data=observations_text,
                fields_json=fields_json,
                field_definitions=field_definitions,
            )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_content},
        ]
        return self.model.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )

    def generate_report(self):
        """
        Main entry point. Collects data then generates the report via streaming LLM.
        Yields events: partial_report, report, token, report_ready.
        """
        if self.model is None:
            raise RuntimeError("ReportGenerator requires a model instance.")

        if audio_pipeline_lock.locked():
            busy_msg = (
                "当前音频处理正在进行中，请等待转录/摘要完成后再生成报告。"
                if self.language == "zh"
                else "Audio processing is in progress. Please wait for transcription/summary to complete."
            )
            logger.warning("[ReportGenerator] audio_pipeline_lock is held, refusing to start.")
            yield {"type": "token", "content": busy_msg}
            return

        start = time.perf_counter()

        # Data collection is synchronous and populates collected_data in-place.
        self._collect_all_data()

        collect_time = time.perf_counter() - start
        logger.info(f"[ReportGenerator] Data collection completed in {collect_time:.2f}s, "
                    f"collected {len(self.collected_data)} sources")

        if not self.collected_data:
            no_data_msg = (
                "当前无课堂记录数据，请先完成一节课的录制。"
                if self.language == "zh"
                else "No classroom recording data available. Please complete a class session first."
            )
            logger.warning(f"[ReportGenerator] No data found for session {self.session_id}")
            yield {"type": "token", "content": no_data_msg}
            return

        session_dir = self._get_session_dir()
        report_path = os.path.join(session_dir, "class_report.md")

        template_path = get_template_path(self.language, self.session_id, self.template_name)
        if template_path is None:
            msg = (
                "当前未找到可用报告模板，请先配置模板后再生成。"
                if self.language == "zh"
                else "No report template is available. Configure a template before generating the report."
            )
            logger.error("[ReportGenerator] No template available for session %s", self.session_id)
            yield {"type": "token", "content": f"[ERROR]: {msg}"}
            return

        first_token_time = None

        structure = extract_template_structure(template_path)
        template_fields = structure["all_fields"]
        kinds = get_field_kinds()

        selected, drop_codes = self._compute_selection()

        raw_codes = [c for c, k in kinds.items() if k == "raw" and c not in self.IMAGE_FIELD_CODES]
        gen_codes = [c for c, k in kinds.items() if k == "generated"]
        gen_codes += [f for f in template_fields if f not in kinds]

        raw_values = resolve_raw_fields(self.data_collector, raw_codes, self.language)
        raw_values.update(self._manual_values())
        image_fields = self._build_image_fields(selected)
        logger.info(f"[ReportGenerator] Full-catalog fill for {os.path.basename(template_path)}: "
                    f"{len(raw_codes)} raw (direct), {len(gen_codes)} generated (LLM), "
                    f"{len(image_fields)} image, {len(drop_codes)} deselected (dropped from this render).")

        from components.report_generator.template_manager import read_docx_as_markdown

        if gen_codes:
            pending = "⏳ 生成中…" if self.language == "zh" else "⏳ Generating…"
            interim_fields = {**{c: pending for c in gen_codes}, **raw_values}
            fill_template(template_path, interim_fields,
                          os.path.join(session_dir, "class_report.docx"),
                          drop_codes=drop_codes, image_fields=image_fields,
                          field_codes=frozenset(get_known_field_codes()))
            interim_md = read_docx_as_markdown(
                os.path.join(session_dir, "class_report.docx"),
                self.session_id,
            )
            yield {"type": "partial_report", "content": interim_md}

        llm_values = {}
        if gen_codes:
            gen_prompt = self._build_generated_fill_prompt(structure, gen_codes, raw_values)
            try:
                json_response = self.model.generate(gen_prompt, stream=False)
                if isinstance(json_response, str) and json_response.startswith("[ERROR]:"):
                    raise RuntimeError(json_response)
            except RuntimeError as e:
                logger.error(f"[ReportGenerator] LLM failed during template fill: {e}")
                err_msg = (
                    "报告生成失败：LLM服务超时或出错，请稍后重试。"
                    if self.language == "zh"
                    else "Report generation failed. Please try again."
                )
                yield {"type": "token", "content": f"[ERROR]: {err_msg}"}
                return

            first_token_time = time.perf_counter()
            llm_values = parse_llm_json_response(json_response)
            logger.info(f"[ReportGenerator] Parsed {len(llm_values)} generated fields from LLM.")
        else:
            first_token_time = time.perf_counter()
            logger.info("[ReportGenerator] No generated fields; skipping LLM.")

        report_fields = {**llm_values, **raw_values}
        save_store(session_dir, report_fields)

        docx_path = os.path.join(session_dir, "class_report.docx")
        fill_template(template_path, report_fields, docx_path,
                      drop_codes=drop_codes, image_fields=image_fields,
                      field_codes=frozenset(get_known_field_codes()))

        markdown_content = read_docx_as_markdown(docx_path, self.session_id)
        StorageManager.save(report_path, markdown_content, append=False)

        yield {"type": "report", "content": markdown_content}
        yield {"type": "report_ready", "session_id": self.session_id}

        end = time.perf_counter()
        total_time = end - start
        generation_time = end - start - collect_time
        ttft = (first_token_time - start - collect_time) if first_token_time else -1

        logger.info(
            f"[ReportGenerator] Complete. Total: {total_time:.2f}s "
            f"(Collect: {collect_time:.2f}s, Generate: {generation_time:.2f}s, TTFT: {ttft:.2f}s)"
        )

        StorageManager.update_csv(
            path=os.path.join(session_dir, "performance_metrics.csv"),
            new_data={
                "performance.report_collect_time": round(collect_time, 4),
                "performance.report_generation_time": round(generation_time, 4),
                "performance.report_total_time": round(total_time, 4),
                "performance.report_ttft": f"{round(ttft, 4)}s",
            },
        )

    def reapply_selection(self, selected_fields) -> dict:
        """Re-render the report for a new field selection — NO LLM, NO data read.

        Re-projects the cached full-catalog field values (saved by a prior
        generate_report) onto the template, dropping the now-deselected fields.
        Fast (~instant) and deterministic: the measured numbers and AI prose are
        identical to the last generation, only which fields appear changes.

        Returns ``{session_id, report}`` (markdown). Raises RuntimeError if no
        cache/template exists.
        """
        from components.report_generator.template_manager import read_docx_as_markdown

        session_dir = self._get_session_dir()
        template_path = get_template_path(self.language, self.session_id, self.template_name)
        if template_path is None:
            raise RuntimeError("No report template available to render.")

        fields = dict(load_store(session_dir).get("fields", {}))
        if not fields:
            raise RuntimeError("No cached fields for this session. Generate a report first.")

        self.selected_fields = selected_fields
        selected, drop_codes = self._compute_selection()

        manual = self._manual_values()
        if manual:
            fields.update(manual)
            save_store(session_dir, fields)

        image_fields = self._build_image_fields(selected)

        docx_path = os.path.join(session_dir, "class_report.docx")
        fill_template(template_path, fields, docx_path,
                      drop_codes=drop_codes, image_fields=image_fields,
                      field_codes=frozenset(get_known_field_codes()))
        markdown_content = read_docx_as_markdown(docx_path, self.session_id)
        StorageManager.save(os.path.join(session_dir, "class_report.md"),
                            markdown_content, append=False)

        logger.info(f"[ReportGenerator] Re-projected selection for session "
                    f"{self.session_id} ({len(drop_codes)} dropped) — no LLM.")
        return {"session_id": self.session_id, "report": markdown_content}

    def _manual_values(self) -> dict:
        """Teacher-typed manual field values (trimmed) for the manual field codes.

        Blank values are ignored so manual-field defaults from raw mapping remain
        visible in the report. Only non-empty teacher input overrides defaults.
        """
        manual_codes = get_manual_field_codes()
        values = {}
        for c, v in self.manual_fields.items():
            if c not in manual_codes or not isinstance(v, str):
                continue
            trimmed = v.strip()
            if trimmed:
                values[c] = trimmed
        return values

    def _compute_selection(self):
        """Return ``(selected, drop_codes)`` for the current request.

        Manual fields behave like any other checkbox: kept when selected (value or
        blank), dropped when not. Always-on fields (auto metadata, e.g.
        report_time) are always selected. ``selected_fields`` None => all
        selectable catalog fields checked.
        """
        catalog_codes = get_known_field_codes()
        always_on = get_always_on_codes()

        if self.selected_fields is None:
            selected = set(catalog_codes)
        else:
            selected = set(self.selected_fields)

        selected |= always_on

        # Apply coupling rules after always-on expansion.
        selected = self._apply_selection_hide_rules(selected)

        drop_codes = frozenset(catalog_codes - selected)
        return selected, drop_codes

    def _apply_selection_hide_rules(self, selected: set[str]) -> set[str]:
        """Apply selection-coupling hide rules.

        Rules are declared in ``_SELECTION_HIDE_RULES`` so future couplings can
        be added without touching core selection flow.
        """
        result = set(selected)
        for rule in self._SELECTION_HIDE_RULES:
            primary = rule.get("primary")
            hide = tuple(rule.get("hide", ()))
            if not primary or not hide:
                continue
            if primary not in result:
                for code in hide:
                    result.discard(code)
        return result

    def _build_image_fields(self, selected) -> dict:
        """Collect the image-backed catalog fields (currently just the mind map)
        for the given selection. Returns ``{code: image_path}``; empty if the
        field is deselected or the image is missing.

        The mind-map image is captured in the browser (html2canvas over the live
        jsMind view) and uploaded to the session dir as ``mindmap_report.png``
        via POST /report/{session_id}/mindmap-image — the backend does not render
        it. If the upload never happened (e.g. the teacher left the mind-map tab
        before it painted), the image is simply omitted from the report.
        """
        image_fields = {}
        if "mindmap" in selected:
            session_dir = self._get_session_dir()
            png = os.path.join(session_dir, "mindmap_report.png")
            if os.path.exists(png):
                image_fields["mindmap"] = png
        return image_fields
