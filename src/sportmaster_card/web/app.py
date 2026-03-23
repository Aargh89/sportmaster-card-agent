"""FastAPI backend for the Sportmaster Card Agent pipeline UI.

Provides:
    - POST /api/generate — start pipeline with SSE progress stream
    - GET / — serve the frontend HTML
    - GET /api/platforms — list available platform configs

The pipeline runs in a background thread, sending SSE events
as each agent completes its work.
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from threading import Thread
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sportmaster Card Agent", version="0.1.0")

# Global queue for SSE events per session
_event_queues: dict[str, asyncio.Queue] = {}


def _send_event(session_id: str, event_type: str, data: dict):
    """Push an SSE event to the session's queue."""
    if session_id in _event_queues:
        queue = _event_queues[session_id]
        try:
            queue.put_nowait({"event": event_type, "data": json.dumps(data, ensure_ascii=False)})
        except asyncio.QueueFull:
            pass


def _run_pipeline(session_id: str, product_data: dict, platforms: list[str]):
    """Execute the full pipeline in a background thread, emitting SSE events."""
    from sportmaster_card.models.product_input import ProductInput

    try:
        product = ProductInput(**product_data)
    except Exception as e:
        _send_event(session_id, "error", {"message": f"Invalid product data: {e}"})
        _send_event(session_id, "done", {"status": "error"})
        return

    _send_event(session_id, "agent_start", {
        "agent": "Router", "step": 1, "total": 15,
        "description": "Классификация товара и выбор пайплайна"
    })

    # --- UC1: Enrichment (run once) ---
    from sportmaster_card.agents.router import RouterAgent
    router = RouterAgent()
    t0 = time.time()
    routing = router.route(product, "1P")
    _send_event(session_id, "agent_done", {
        "agent": "Router", "step": 1,
        "duration": round(time.time() - t0, 1),
        "result": {
            "flow": routing.flow_type.value,
            "profile": routing.processing_profile.value,
            "platforms": routing.target_platforms,
        }
    })

    # DataValidator
    _send_event(session_id, "agent_start", {
        "agent": "DataValidator", "step": 2, "total": 15,
        "description": "Проверка полноты данных из Excel"
    })
    from sportmaster_card.agents.data_validator import DataValidatorAgent
    validator = DataValidatorAgent()
    t0 = time.time()
    val_report, val_prov = validator.validate(product)
    _send_event(session_id, "agent_done", {
        "agent": "DataValidator", "step": 2,
        "duration": round(time.time() - t0, 1),
        "result": {
            "is_valid": val_report.is_valid,
            "completeness": f"{val_report.overall_completeness:.0%}",
            "missing": val_report.missing_required,
        }
    })

    # VisualInterpreter
    _send_event(session_id, "agent_start", {
        "agent": "VisualInterpreter", "step": 3, "total": 15,
        "description": "Анализ фото/визуалов товара"
    })
    from sportmaster_card.agents.visual_interpreter import VisualInterpreterAgent
    visual = VisualInterpreterAgent()
    t0 = time.time()
    extracted, vis_prov = visual.interpret(product)
    _send_event(session_id, "agent_done", {
        "agent": "VisualInterpreter", "step": 3,
        "duration": round(time.time() - t0, 1),
        "result": {"attributes": len(extracted), "mode": "stub (no photo)"}
    })

    # --- External Research: WB and Ozon as SEPARATE steps ---
    from sportmaster_card.models.enrichment import CompetitorCard, CompetitorBenchmark
    from sportmaster_card.tools.wb_search import wb_search, build_search_queries
    from sportmaster_card.tools.ozon_search import ozon_search
    from collections import Counter

    all_competitors = []
    ext_prov = []
    benchmark = None

    # Step 4a: Wildberries
    _send_event(session_id, "agent_start", {
        "agent": "WB Search", "step": 4, "total": 17,
        "description": "Поиск конкурентов на Wildberries"
    })
    t0 = time.time()
    wb_results = []
    try:
        queries = build_search_queries(
            brand=product.brand, product_name=product.product_name,
            category=product.category, product_subgroup=product.product_subgroup,
            technologies=product.technologies,
        )
        for q in queries[:2]:  # Max 2 queries to reduce rate limit risk
            wb_results = wb_search(query=q, max_results=5, min_rating=4.0, retry_delay=2, max_versions=2)
            if wb_results:
                break
            time.sleep(1)
    except Exception as e:
        logger.warning("WB search failed: %s", e)

    wb_cards = []
    for wp in wb_results:
        card = CompetitorCard(
            platform="wb", product_name=f"{wp.brand} {wp.name}",
            description=wp.description or f"★{wp.rating} · {wp.feedbacks} отзывов",
            price=float(wp.price), rating=wp.rating,
            key_features=[f"Цена: {wp.price}₽", f"★{wp.rating}", f"{wp.feedbacks} отзывов"],
            url=wp.url,
        )
        wb_cards.append(card)
        all_competitors.append(card)

    _send_event(session_id, "agent_done", {
        "agent": "WB Search", "step": 4,
        "duration": round(time.time() - t0, 1),
        "result": {
            "found": len(wb_cards),
            "status": f"{len(wb_cards)} товаров" if wb_cards else "rate limit / нет результатов",
            "top": f"{wb_cards[0].product_name[:50]} — {wb_cards[0].price:.0f}₽" if wb_cards else "—",
        }
    })

    # Step 4b: Ozon
    _send_event(session_id, "agent_start", {
        "agent": "Ozon Search", "step": "4b", "total": 17,
        "description": "Поиск конкурентов на Ozon"
    })
    t0 = time.time()
    ozon_results = []
    try:
        ozon_query = f"{product.brand} {product.product_subgroup}"
        ozon_results = ozon_search(query=ozon_query, max_results=5, min_rating=4.0)
    except Exception as e:
        logger.warning("Ozon search failed: %s", e)

    ozon_cards = []
    for op in ozon_results:
        card = CompetitorCard(
            platform="ozon",
            product_name=f"{op.brand} {op.name}" if op.brand else op.name,
            description=f"★{op.rating}" if op.rating else "",
            price=float(op.price) if op.price else None,
            rating=op.rating,
            key_features=[f"Цена: {op.price}₽"] if op.price else [],
            url=op.url,
        )
        ozon_cards.append(card)
        all_competitors.append(card)

    _send_event(session_id, "agent_done", {
        "agent": "Ozon Search", "step": "4b",
        "duration": round(time.time() - t0, 1),
        "result": {
            "found": len(ozon_cards),
            "status": f"{len(ozon_cards)} товаров" if ozon_cards else "anti-bot / нет результатов",
            "top": f"{ozon_cards[0].product_name[:50]}" if ozon_cards else "—",
        }
    })

    # Step 4c: LLM fallback if no API results
    from sportmaster_card.models.provenance import DataProvenance, SourceType
    from datetime import datetime

    if not all_competitors:
        _send_event(session_id, "agent_start", {
            "agent": "LLM Research", "step": "4c", "total": 17,
            "description": "API недоступен → LLM ищет конкурентов из своих знаний"
        })
        t0 = time.time()
        from sportmaster_card.agents.external_researcher import ExternalResearcherAgent
        researcher = ExternalResearcherAgent()
        benchmark, ext_prov = researcher._research_with_llm(product)
        all_competitors = benchmark.competitors
        _send_event(session_id, "agent_done", {
            "agent": "LLM Research", "step": "4c",
            "duration": round(time.time() - t0, 1),
            "result": {
                "found": len(all_competitors),
                "source": "LLM knowledge",
                "summary": benchmark.benchmark_summary[:80],
            }
        })

    prices = [c.price for c in all_competitors if c.price]
    avg_price = sum(prices) / len(prices) if prices else None

    if not benchmark:
        benchmark = CompetitorBenchmark(
            mcm_id=product.mcm_id, competitors=all_competitors,
            benchmark_summary=f"WB: {len(wb_cards)}, Ozon: {len(ozon_cards)}. Средняя цена: {avg_price:.0f}₽" if avg_price else f"WB: {len(wb_cards)}, Ozon: {len(ozon_cards)}",
            average_price=avg_price,
        )
    for c in all_competitors:
        ext_prov.append(DataProvenance(
            attribute_name="competitor_card", value=c.product_name,
            source_type=SourceType.EXTERNAL, source_name=c.platform,
            confidence=0.7, agent_id="agent-1.3-external-researcher",
            timestamp=datetime.now(),
        ))

    # InternalResearcher
    _send_event(session_id, "agent_start", {
        "agent": "InternalResearcher", "step": 5, "total": 15,
        "description": "Извлечение инсайтов из внутренних документов"
    })
    from sportmaster_card.agents.internal_researcher import InternalResearcherAgent
    int_researcher = InternalResearcherAgent()
    t0 = time.time()
    insights, int_prov = int_researcher.research(product)
    _send_event(session_id, "agent_done", {
        "agent": "InternalResearcher", "step": 5,
        "duration": round(time.time() - t0, 1),
        "result": {"insights": len(insights.insights), "mode": "stub"}
    })

    # Synectics
    _send_event(session_id, "agent_start", {
        "agent": "SynecticsAgent", "step": 6, "total": 15,
        "description": "Генерация креативных метафор и ассоциаций (LLM)"
    })
    from sportmaster_card.agents.synectics_agent import SynecticsAgent
    synectics = SynecticsAgent()
    t0 = time.time()
    creative = synectics.generate(product)
    _send_event(session_id, "agent_done", {
        "agent": "SynecticsAgent", "step": 6,
        "duration": round(time.time() - t0, 1),
        "result": {
            "metaphors": creative.metaphors[:3],
            "hooks": creative.emotional_hooks[:2],
            "mode": "LLM" if creative.metaphors and not creative.metaphors[0].startswith("Технология") else "stub",
        }
    })

    # DataEnricher
    _send_event(session_id, "agent_start", {
        "agent": "DataEnricher", "step": 7, "total": 15,
        "description": "Объединение данных из всех источников"
    })
    from sportmaster_card.agents.data_enricher import DataEnricherAgent
    enricher = DataEnricherAgent()
    t0 = time.time()
    all_prov = val_prov + vis_prov + ext_prov + int_prov
    enriched = enricher.enrich(product, val_report, benchmark, insights, creative, all_prov)
    _send_event(session_id, "agent_done", {
        "agent": "DataEnricher", "step": 7,
        "duration": round(time.time() - t0, 1),
        "result": {"provenance_entries": len(all_prov)}
    })

    # DataCurator
    _send_event(session_id, "agent_start", {
        "agent": "DataCurator", "step": 8, "total": 15,
        "description": "LLM-обогащение: описание, фичи, бенефиты, SEO (Claude Sonnet)"
    })
    from sportmaster_card.agents.data_curator import DataCuratorAgent
    curator = DataCuratorAgent()
    t0 = time.time()
    curated = curator.curate(enriched)
    _send_event(session_id, "agent_done", {
        "agent": "DataCurator", "step": 8,
        "duration": round(time.time() - t0, 1),
        "result": {
            "description": curated.description[:150] + "...",
            "features": len(curated.key_features),
            "benefits": len(curated.benefits_data),
            "seo_queries": len(curated.seo_material),
            "mode": "LLM",
        }
    })

    # --- UC2: Content per platform (parallel info) ---
    _send_event(session_id, "phase", {
        "phase": "UC2",
        "description": f"Генерация контента для {len(platforms)} площадок",
        "platforms": platforms,
    })

    from sportmaster_card.agents.seo_analyst import SEOAnalystAgent
    from sportmaster_card.agents.structure_planner import StructurePlannerAgent
    from sportmaster_card.agents.content_generator import ContentGeneratorAgent
    from sportmaster_card.agents.brand_compliance import BrandComplianceAgent
    from sportmaster_card.agents.fact_checker import FactCheckerAgent
    from sportmaster_card.agents.copy_editor import CopyEditorAgent
    from sportmaster_card.agents.quality_controller import QualityControllerAgent
    from sportmaster_card.models.content import ContentBrief, PlatformContentSet
    from sportmaster_card.models.platform_profile import PlatformProfile

    seo_agent = SEOAnalystAgent()
    planner = StructurePlannerAgent()
    gen = ContentGeneratorAgent()
    compliance = BrandComplianceAgent()
    fact_checker = FactCheckerAgent()
    editor = CopyEditorAgent()
    qc = QualityControllerAgent()

    all_contents = {}
    all_scores = {}
    step_num = 9

    for pid in platforms:
        # Load platform profile
        config_dir = Path(__file__).parent.parent / "config" / "platforms"
        yaml_path = config_dir / f"{pid}.yaml"
        profile = PlatformProfile.from_yaml(str(yaml_path)) if yaml_path.exists() else None
        max_desc = profile.text_requirements.max_description_length if profile else 3000
        max_title = profile.text_requirements.max_title_length if profile else 150
        tone = profile.text_requirements.tone_of_voice if profile else "professional"
        forbidden = profile.text_requirements.forbidden_words if profile else []

        _send_event(session_id, "platform_start", {
            "platform": pid, "step": step_num,
            "description": f"Генерация для {pid.upper()}"
        })

        # SEO
        _send_event(session_id, "agent_start", {
            "agent": f"SEO ({pid})", "step": step_num, "total": 15,
            "description": f"SEO-анализ для {pid.upper()} (LLM)"
        })
        t0 = time.time()
        seo = seo_agent.analyze(product, pid)
        _send_event(session_id, "agent_done", {
            "agent": f"SEO ({pid})", "step": step_num,
            "duration": round(time.time() - t0, 1),
            "result": {"keywords": seo.primary_keywords[:3], "mode": "LLM"}
        })

        # Generate
        _send_event(session_id, "agent_start", {
            "agent": f"ContentGen ({pid})", "step": step_num, "total": 15,
            "description": f"Генерация контента для {pid.upper()} (Claude Sonnet)"
        })
        t0 = time.time()
        content = gen.generate(product, pid, max_desc, max_title)
        _send_event(session_id, "agent_done", {
            "agent": f"ContentGen ({pid})", "step": step_num,
            "duration": round(time.time() - t0, 1),
            "result": {
                "title": content.product_name[:80],
                "description_length": len(content.description),
                "benefits": len(content.benefits),
                "mode": "LLM",
            }
        })

        # Quality checks
        _send_event(session_id, "agent_start", {
            "agent": f"QualityCheck ({pid})", "step": step_num, "total": 15,
            "description": f"Проверка качества {pid.upper()}"
        })
        t0 = time.time()
        comp_report = compliance.check(content, brand_name=product.brand, forbidden_words=forbidden)
        fact_report = fact_checker.check(content, curated)
        edited = editor.edit(content, max_desc, max_title)
        score = qc.evaluate(edited, comp_report, fact_report)
        _send_event(session_id, "agent_done", {
            "agent": f"QualityCheck ({pid})", "step": step_num,
            "duration": round(time.time() - t0, 1),
            "result": {
                "quality": score.overall_score,
                "passed": score.passes_threshold,
                "compliant": comp_report.is_compliant,
                "accurate": fact_report.is_accurate,
            }
        })

        all_contents[pid] = edited
        all_scores[pid] = score

        # Send full platform result
        _send_event(session_id, "platform_done", {
            "platform": pid,
            "content": {
                "title": edited.product_name,
                "description": edited.description,
                "benefits": [{"title": b.title, "description": b.description} for b in edited.benefits],
                "seo_title": edited.seo_title,
                "seo_meta": edited.seo_meta_description,
                "seo_keywords": edited.seo_keywords,
            },
            "quality": {
                "overall": score.overall_score,
                "passed": score.passes_threshold,
            }
        })

        step_num += 1

    # Final summary
    all_passed = all(s.passes_threshold for s in all_scores.values())
    _send_event(session_id, "done", {
        "status": "success",
        "platforms_generated": len(all_contents),
        "all_passed_quality": all_passed,
        "curated_profile": {
            "description": curated.description,
            "key_features": curated.key_features,
            "benefits_data": curated.benefits_data,
            "seo_material": curated.seo_material,
            "technologies": curated.technologies,
        }
    })


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the frontend HTML."""
    html_path = Path(__file__).parent / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/platforms")
async def list_platforms():
    """List available platform configurations."""
    config_dir = Path(__file__).parent.parent / "config" / "platforms"
    platforms = []
    for f in sorted(config_dir.glob("*.yaml")):
        platforms.append({"id": f.stem, "name": f.stem.replace("_", " ").title()})
    return JSONResponse(platforms)


@app.post("/api/generate")
async def generate(request: Request):
    """Start pipeline and return SSE stream of progress events."""
    body = await request.json()
    product_data = body.get("product", {})
    platforms = body.get("platforms", ["sm_site"])

    import uuid
    session_id = str(uuid.uuid4())
    queue = asyncio.Queue(maxsize=200)
    _event_queues[session_id] = queue

    # Run pipeline in background thread
    thread = Thread(
        target=_run_pipeline,
        args=(session_id, product_data, platforms),
        daemon=True,
    )
    thread.start()

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=300)
                    yield event
                    if event.get("event") == "done":
                        break
                except asyncio.TimeoutError:
                    yield {"event": "error", "data": json.dumps({"message": "Timeout"})}
                    break
        finally:
            _event_queues.pop(session_id, None)

    return EventSourceResponse(event_generator())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
