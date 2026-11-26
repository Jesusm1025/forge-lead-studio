"""
Forge Lead Studio — Agent 00: Autonomous Niche Evaluator & Pivot Engine
Zero-token strategic scoring engine that evaluates each vertical (roofing, hvac, etc.)
from tracking/crm_pipeline.json (enriched with live Cloudflare Worker KV telemetry),
classifies every vertical into SCALE, TESTING, or PIVOT, generates bilingual (EN & ES)
expansion/pivot playbooks, and persists tracking/niche_intelligence.json.
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRM_PATH = os.path.join(ROOT, "tracking", "crm_pipeline.json")
INTEL_PATH = os.path.join(ROOT, "tracking", "niche_intelligence.json")
PUBLIC_INTEL_PATH = os.path.join(ROOT, "public", "tracking", "niche_intelligence.json")

# Thresholds defined by Forge Lead Studio Unit-Economics Charter
SCALE_MIN_STEP2 = 10
SCALE_MIN_ENG_RATE = 0.08
SCALE_MIN_REPLY_RATE = 0.04
TESTING_HOLD_STEP2 = 15
PIVOT_MIN_STEP2 = 18
PIVOT_MAX_ENG_RATE = 0.03

VERTICAL_CATALOG = {
    "roofing": {
        "display_en": "Residential Roofing",
        "display_es": "Techos Residenciales (Roofing)",
        "avg_ticket_usd": "$12,500 – $26,000",
        "expansion_metros": [
            "San Antonio, TX",
            "Kansas City, MO",
            "Oklahoma City, OK",
            "Columbus, OH",
            "Indianapolis, IN",
            "St. Louis, MO",
            "Richmond, VA",
            "Cincinnati, OH",
        ],
        "scale_subjects_en": [
            "Built a 30-second hail & roof replacement ballpark for {business}",
            "Quick mobile quote widget for {city} homeowners",
            "Turning {city} roof clicks into pre-qualified inspections",
        ],
        "scale_subjects_es": [
            "Creamos una calculadora instantánea de techos y granizo para {business}",
            "Widget móvil de cotización rápida para propietarios en {city}",
            "Convierte visitas de {city} en inspecciones pre-calificadas",
        ],
        "upsell_addons_en": [
            "Storm & Hail Insurance Claim Pre-Qualifier ($299/mo add-on)",
            "Instant 120-Month Roof Financing Payment Slider ($199/mo add-on)",
            "After-Hours Emergency Tarping SMS Dispatch Widget ($199/mo add-on)",
        ],
        "upsell_addons_es": [
            "Pre-Calificador de Reclamos por Granizo y Seguro ($299/mes adicional)",
            "Simulador de Financiamiento a 120 Meses ($199/mes adicional)",
            "Widget SMS de Emergencia / Lona 24/7 ($199/mes adicional)",
        ],
    },
    "hvac": {
        "display_en": "Residential HVAC Replacement",
        "display_es": "Reemplazo Residencial de HVAC",
        "avg_ticket_usd": "$9,400 – $19,500",
        "expansion_metros": [
            "Houston, TX",
            "Austin, TX",
            "San Antonio, TX",
            "Charlotte, NC",
            "Jacksonville, FL",
            "Las Vegas, NV",
            "Raleigh, NC",
            "Nashville, TN",
        ],
        "scale_subjects_en": [
            "Built a 30-second SEER2 & tonnage replacement quote tool for {business}",
            "Instant HVAC replacement ballpark + financing for {city} homeowners",
            "Stop losing {city} AC replacement shoppers who want pricing first",
        ],
        "scale_subjects_es": [
            "Creamos un cotizador instantáneo SEER2 y tonelaje para {business}",
            "Estimado inmediato de reemplazo HVAC + financiamiento en {city}",
            "Captura compradores de aire acondicionado en {city} antes de que llamen a la competencia",
        ],
        "upsell_addons_en": [
            "24/7 'No AC' Emergency Dispatch & Triage Widget ($249/mo add-on)",
            "Federal 25C Heat Pump Tax Credit & Utility Rebate Finder ($199/mo add-on)",
            "Seasonal Maintenance Club Auto-Enrollment Flow ($199/mo add-on)",
        ],
        "upsell_addons_es": [
            "Widget de Despacho de Emergencia 'Sin A/C' 24/7 ($249/mes adicional)",
            "Buscador de Crédito Fiscal Federal 25C y Reembolsos ($199/mes adicional)",
            "Flujo de Membresía de Mantenimiento Estacional ($199/mes adicional)",
        ],
    },
}

NEXT_VERTICAL_BACKLOG = [
    {
        "vertical": "solar",
        "priority_score": 95,
        "avg_ticket_usd": "$24,000 – $38,000",
        "target_metros": ["Phoenix, AZ", "San Diego, CA", "Austin, TX", "Tampa, FL", "Las Vegas, NV"],
        "en": {
            "name": "Residential Solar + Battery Storage",
            "calculator_hook": "30-second monthly electric bill to solar + battery savings & federal ITC payback estimator",
            "why_now": "Highest homeowner ticket size ($24k–$38k) and urgent demand for transparent utility offset numbers without pushy door-knocker calls.",
        },
        "es": {
            "name": "Energía Solar Residencial + Baterías",
            "calculator_hook": "Calculadora de 30 segundos: factura eléctrica mensual -> ahorro solar + batería y crédito fiscal federal",
            "why_now": "Ticket promedio más alto ($24k–$38k) con alta demanda de estimados transparentes sin llamadas invasivas de vendedores.",
        },
    },
    {
        "vertical": "window_door_replacement",
        "priority_score": 92,
        "avg_ticket_usd": "$14,000 – $28,000",
        "target_metros": ["Miami, FL", "Tampa, FL", "Houston, TX", "Dallas, TX", "Charlotte, NC"],
        "en": {
            "name": "Impact Window & Patio Door Replacement",
            "calculator_hook": "Instant window-count + hurricane impact/Low-E glass pricing & monthly financing ballpark",
            "why_now": "90%+ of local window contractors hide pricing behind mandatory in-home sales pitches; transparent ballpark calculators convert mobile traffic fast.",
        },
        "es": {
            "name": "Reemplazo de Ventanas de Impacto y Puertas",
            "calculator_hook": "Estimador instantáneo por número de ventanas + vidrio de impacto/Low-E y financiamiento mensual",
            "why_now": "Más del 90% de instaladores ocultan precios tras citas presenciales; un cotizador transparente convierte tráfico móvil de inmediato.",
        },
    },
    {
        "vertical": "kitchen_bath_remodel",
        "priority_score": 89,
        "avg_ticket_usd": "$18,000 – $45,000",
        "target_metros": ["Atlanta, GA", "Denver, CO", "Nashville, TN", "Raleigh, NC", "Austin, TX"],
        "en": {
            "name": "Kitchen & Walk-In Bath Remodeling",
            "calculator_hook": "Scope-tier (refresh vs. full gut) + finish grade instant remodel budget & timeline estimator",
            "why_now": "Remodelers waste hours quoting tire-kickers with $5k budgets; pre-qualifying scope and budget range solves their #1 bottleneck.",
        },
        "es": {
            "name": "Remodelación de Cocinas y Baños",
            "calculator_hook": "Estimador instantáneo por alcance (renovación vs. reforma total) + gama de acabados y tiempo de obra",
            "why_now": "Los contratistas pierden horas cotizando curiosos sin presupuesto; pre-calificar el rango de inversión resuelve su mayor dolor.",
        },
    },
    {
        "vertical": "concrete_driveways",
        "priority_score": 85,
        "avg_ticket_usd": "$8,500 – $16,500",
        "target_metros": ["Dallas, TX", "Charlotte, NC", "Columbus, OH", "Indianapolis, IN", "Nashville, TN"],
        "en": {
            "name": "Concrete Driveways & Stamped Patios",
            "calculator_hook": "Square-footage + finish style (broom, stamped, exposed aggregate) + tear-out instant quote",
            "why_now": "Fragmented independent operators with outdated websites and virtually zero competing SaaS quote widgets.",
        },
        "es": {
            "name": "Entradas de Concreto y Patios Estampados",
            "calculator_hook": "Cotizador por pies cuadrados + acabado (escobillado, estampado, agregado) y demolición previa",
            "why_now": "Mercado muy fragmentado de contratistas independientes con sitios antiguos y casi cero competencia de widgets SaaS.",
        },
    },
    {
        "vertical": "tree_service",
        "priority_score": 81,
        "avg_ticket_usd": "$2,800 – $7,500",
        "target_metros": ["Atlanta, GA", "Charlotte, NC", "Raleigh, NC", "Orlando, FL", "Houston, TX"],
        "en": {
            "name": "Hazardous Tree Removal & Stump Grinding",
            "calculator_hook": "Tree height + proximity to structures/powerlines + crane/stump instant removal estimate",
            "why_now": "Fast sales cycle with high storm-season urgency and immediate need to filter low-margin pruning calls from high-ticket removals.",
        },
        "es": {
            "name": "Remoción de Árboles Peligrosos y Destoconado",
            "calculator_hook": "Estimado inmediato por altura del árbol + cercanía a estructuras/cables + grúa y destoconado",
            "why_now": "Ciclo de venta rápido con alta urgencia en temporada de tormentas y necesidad de filtrar trabajos pequeños.",
        },
    },
]


def utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def infer_vertical(p: dict) -> str:
    v = str(p.get("vertical") or p.get("niche") or "").strip().lower()
    if v in ("hvac", "roofing"):
        return v
    if v:
        return v
    pid = str(p.get("prospect_id") or "").lower()
    if pid.startswith("hvac_"):
        return "hvac"
    if "_" in pid:
        return pid.split("_", 1)[0]
    return "roofing"


def max_step_delivered(p: dict) -> int:
    best = max(int(p.get("current_step") or 0), int(p.get("last_sent_step") or 0))
    for h in (p.get("outreach_history") or []):
        try:
            best = max(best, int(h.get("step") or 0))
        except (TypeError, ValueError):
            pass
    for s in (4, 3, 2, 1):
        if p.get(f"step_{s}_sent_at"):
            best = max(best, s)
            break
    return best


def classify_vertical(step2_plus_delivered: int, demo_engagement_rate: float, reply_rate: float, human_replies: int) -> str:
    if step2_plus_delivered >= SCALE_MIN_STEP2 and (
        demo_engagement_rate >= SCALE_MIN_ENG_RATE or reply_rate >= SCALE_MIN_REPLY_RATE
    ):
        return "SCALE"
    if (
        step2_plus_delivered >= PIVOT_MIN_STEP2
        and demo_engagement_rate < PIVOT_MAX_ENG_RATE
        and human_replies == 0
    ):
        return "PIVOT"
    return "TESTING"


def pick_pivot_candidate(active_verticals: set[str]) -> dict:
    for item in NEXT_VERTICAL_BACKLOG:
        if item["vertical"] not in active_verticals:
            return item
    return NEXT_VERTICAL_BACKLOG[0]


def build_recommendations(
    vertical: str,
    verdict: str,
    metrics: dict,
    scouted_metros: list[str],
    active_verticals: set[str],
) -> dict:
    meta = VERTICAL_CATALOG.get(vertical, {
        "display_en": vertical.replace("_", " ").title(),
        "display_es": vertical.replace("_", " ").title(),
        "avg_ticket_usd": "$10,000 – $20,000",
        "expansion_metros": ["Austin, TX", "Dallas, TX", "Phoenix, AZ", "Atlanta, GA", "Tampa, FL"],
        "scale_subjects_en": ["Instant quote prototype built for {business}"],
        "scale_subjects_es": ["Prototipo de cotizador instantáneo creado para {business}"],
        "upsell_addons_en": ["Emergency Dispatch SMS Add-On ($199/mo)", "Financing Pre-Qualification Widget ($199/mo)"],
        "upsell_addons_es": ["Widget SMS de Despacho Urgente ($199/mes)", "Widget de Pre-Calificación Financiera ($199/mes)"],
    })

    scouted_set = {m.lower() for m in scouted_metros}
    next_metros = [m for m in meta["expansion_metros"] if m.lower() not in scouted_set][:4]
    if not next_metros:
        next_metros = meta["expansion_metros"][:4]

    eng_pct = round(metrics["demo_engagement_rate"] * 100, 1)
    rep_pct = round(metrics["reply_rate"] * 100, 1)
    s2 = metrics["step2_plus_delivered"]
    sent = metrics["active_sent"]
    queued = metrics["queued_step_1"]
    engaged = metrics["engaged_demos"]
    replies = metrics["human_replies"]
    remaining_to_hold = max(0, TESTING_HOLD_STEP2 - s2)
    remaining_to_scale_gate = max(0, SCALE_MIN_STEP2 - s2)

    if verdict == "SCALE":
        return {
            "en": {
                "verdict_label": "SCALE — Winner",
                "headline": f"Green Light: Expand {meta['display_en']} into 4 New High-Ticket Metros",
                "summary": (
                    f"Validated traction across {s2} delivered live demos ({eng_pct}% interactive demo engagement, "
                    f"{rep_pct}% human reply rate across {sent} active sends). Double down on outreach volume and monetize upsells."
                ),
                "next_moves": [
                    f"Launch next 12-prospect scouting wave across {', '.join(next_metros[:3])}.",
                    "Lead Step 2 follow-ups with localized ballpark pricing + 60-second mobile calculator clip.",
                    f"Pitch recurring upsells during onboarding calls: {meta['upsell_addons_en'][0]}.",
                    "Publish 1 anonymized conversion lift case study from engaged demos to raise setup fee from $750 to $950.",
                ],
                "target_metros": next_metros,
                "subject_angles": meta["scale_subjects_en"],
                "upsell_addons": meta["upsell_addons_en"],
            },
            "es": {
                "verdict_label": "ESCALAR — Ganador",
                "headline": f"Luz Verde: Expandir {meta['display_es']} a 4 Nuevos Mercados",
                "summary": (
                    f"Tracción validada con {s2} demos en vivo entregados ({eng_pct}% interacción real en calculadora, "
                    f"{rep_pct}% tasa de respuesta humana en {sent} envíos activos). Escala volumen y activa upsells."
                ),
                "next_moves": [
                    f"Lanzar la siguiente ola de 12 prospectos en {', '.join(next_metros[:3])}.",
                    "Enfocar los seguimientos Paso 2 en el estimado local instantáneo + clip móvil de 60 segundos.",
                    f"Ofrecer complementos recurrentes en llamadas de cierre: {meta['upsell_addons_es'][0]}.",
                    "Documentar 1 caso de éxito con los demos activos para subir el fee inicial de $750 a $950.",
                ],
                "target_metros": next_metros,
                "subject_angles": meta["scale_subjects_es"],
                "upsell_addons": meta["upsell_addons_es"],
            },
        }

    if verdict == "PIVOT":
        cand = pick_pivot_candidate(active_verticals)
        return {
            "en": {
                "verdict_label": "PIVOT — Low Traction",
                "headline": f"Pause New {meta['display_en']} Waves -> Pivot Next Capacity to {cand['en']['name']}",
                "summary": (
                    f"Low traction after {s2} live demo deliveries ({eng_pct}% interactive engagement, 0 human replies). "
                    f"Let already-queued follow-ups finish automatically, pause new {vertical} scouting, and clone our <30 KB factory into {cand['en']['name']}."
                ),
                "next_moves": [
                    f"Freeze new {meta['display_en']} scouting waves immediately (let active sequences finish cleanly).",
                    f"Clone Shadow DOM calculator into {cand['en']['name']} (ticket {cand['avg_ticket_usd']}).",
                    f"Hook: {cand['en']['calculator_hook']}.",
                    f"Launch Pilot Wave 1 across {', '.join(cand['target_metros'][:3])}.",
                ],
                "target_metros": cand["target_metros"][:4],
                "subject_angles": [
                    f"Built a 30-second {cand['vertical'].replace('_', ' ')} ballpark widget for {{business}}",
                ],
                "upsell_addons": [cand["en"]["why_now"]],
                "pivot_candidate": {
                    "vertical": cand["vertical"],
                    "name": cand["en"]["name"],
                    "priority_score": cand["priority_score"],
                    "avg_ticket_usd": cand["avg_ticket_usd"],
                    "target_metros": cand["target_metros"],
                    "calculator_hook": cand["en"]["calculator_hook"],
                },
            },
            "es": {
                "verdict_label": "PIVOTAR — Baja Tracción",
                "headline": f"Pausar Nuevas Olas en {meta['display_es']} -> Pivotar hacia {cand['es']['name']}",
                "summary": (
                    f"Baja tracción tras {s2} entregas de demo en vivo ({eng_pct}% interacción real, 0 respuestas humanas). "
                    f"Deja terminar los seguimientos en cola, pausa el scouting en {vertical} y clona la fábrica <30 KB hacia {cand['es']['name']}."
                ),
                "next_moves": [
                    f"Congelar nuevas olas de scouting en {meta['display_es']} (mantener solo los seguimientos activos).",
                    f"Clonar la calculadora Shadow DOM para {cand['es']['name']} (ticket {cand['avg_ticket_usd']}).",
                    f"Gancho: {cand['es']['calculator_hook']}.",
                    f"Lanzar Ola Piloto 1 en {', '.join(cand['target_metros'][:3])}.",
                ],
                "target_metros": cand["target_metros"][:4],
                "subject_angles": [
                    f"Creamos un cotizador instantáneo de {cand['es']['name'].lower()} para {{business}}",
                ],
                "upsell_addons": [cand["es"]["why_now"]],
                "pivot_candidate": {
                    "vertical": cand["vertical"],
                    "name": cand["es"]["name"],
                    "priority_score": cand["priority_score"],
                    "avg_ticket_usd": cand["avg_ticket_usd"],
                    "target_metros": cand["target_metros"],
                    "calculator_hook": cand["es"]["calculator_hook"],
                },
            },
        }

    # TESTING state (Gathering Signal)
    if s2 == 0 and queued > 0:
        summary_en = (
            f"{queued} prospects queued for Step 1 launch (0 Step 2 live demos delivered yet). "
            f"Hold additional {vertical} scouting waves until {TESTING_HOLD_STEP2}+ prospects receive their live demo URL."
        )
        summary_es = (
            f"{queued} prospectos en cola para el lanzamiento Paso 1 (0 demos Paso 2 entregados aún). "
            f"Mantén en pausa nuevas olas de {vertical} hasta que {TESTING_HOLD_STEP2}+ prospectos reciban su demo en vivo."
        )
    else:
        summary_en = (
            f"Gathering statistically meaningful signal: {s2}/{TESTING_HOLD_STEP2} Step 2+ live demos delivered "
            f"({engaged} interactive demos = {eng_pct}%, {replies} replies = {rep_pct}%). "
            f"Hold new wave expansion until {remaining_to_hold} more Step 2 deliveries land."
        )
        summary_es = (
            f"Recopilando señal estadística: {s2}/{TESTING_HOLD_STEP2} demos Paso 2+ entregados "
            f"({engaged} demos interactivos = {eng_pct}%, {replies} respuestas = {rep_pct}%). "
            f"Espera {remaining_to_hold} entregas Paso 2 adicionales antes de abrir una nueva ola."
        )

    return {
        "en": {
            "verdict_label": "TESTING — Gathering Signal",
            "headline": f"Hold Expansion ({s2}/{TESTING_HOLD_STEP2} Step 2 Demos) & Optimize Copy/Calculator",
            "summary": summary_en,
            "next_moves": [
                f"Hold new scouting waves until Step 2+ deliveries reach {TESTING_HOLD_STEP2} ({remaining_to_scale_gate} away from SCALE gate at 10+).",
                "A/B test Step 2 subject lines referencing concrete metro ballpark pricing to lift demo click-through.",
                "Watch Cloudflare KV for Step 2–4 interactions; call any prospect hitting max_step >= 2 within 15 minutes.",
                f"Pre-stage next target metros once validated: {', '.join(next_metros[:3])}.",
            ],
            "target_metros": next_metros,
            "subject_angles": meta["scale_subjects_en"],
            "upsell_addons": meta["upsell_addons_en"],
        },
        "es": {
            "verdict_label": "EN PRUEBA — Recopilando Señal",
            "headline": f"Pausar Expansión ({s2}/{TESTING_HOLD_STEP2} Demos Paso 2) y Afinar Copy/Calculadora",
            "summary": summary_es,
            "next_moves": [
                f"Esperar a alcanzar {TESTING_HOLD_STEP2} entregas Paso 2+ antes de abrir otra ola (faltan {remaining_to_scale_gate} para evaluar ESCALAR en 10+).",
                "Probar variantes de asunto en Paso 2 mencionando el rango local estimado para elevar clics al demo.",
                "Monitorear Cloudflare KV para interacciones en Pasos 2–4 y llamar en menos de 15 min a prospectos activos.",
                f"Mercados pre-seleccionados al validar señal: {', '.join(next_metros[:3])}.",
            ],
            "target_metros": next_metros,
            "subject_angles": meta["scale_subjects_es"],
            "upsell_addons": meta["upsell_addons_es"],
        },
    }


def evaluate_niches(
    crm_data: dict | None = None,
    crm_path: str = CRM_PATH,
    output_path: str = INTEL_PATH,
    public_output_path: str | None = PUBLIC_INTEL_PATH,
    write_files: bool = True,
    mark_alerted_verdicts: dict[str, list[str]] | None = None,
) -> dict:
    if crm_data is None:
        with open(crm_path, encoding="utf-8") as f:
            crm_data = json.load(f)

    prev_intel = {}
    if output_path and os.path.exists(output_path):
        try:
            with open(output_path, encoding="utf-8") as f:
                prev_intel = json.load(f)
        except Exception:
            prev_intel = {}

    prev_verticals = prev_intel.get("verticals") or {}
    prospects = crm_data.get("prospects") or []

    grouped: dict[str, list[dict]] = {}
    for p in prospects:
        v = infer_vertical(p)
        grouped.setdefault(v, []).append(p)

    # Preserve stable display order: roofing, hvac, then alphabetical
    ordered_keys = []
    for k in ("roofing", "hvac"):
        if k in grouped:
            ordered_keys.append(k)
    for k in sorted(grouped.keys()):
        if k not in ordered_keys:
            ordered_keys.append(k)

    active_vertical_set = set(ordered_keys)
    vertical_results = {}
    new_transitions = []

    for v in ordered_keys:
        items = grouped[v]
        total_prospects = len(items)
        active_sent = 0
        queued_step_1 = 0
        step2_plus_delivered = 0
        engaged_demos = 0
        total_demo_views = 0
        total_leads_captured = 0
        human_replies = 0
        bounces = 0
        unsubscribes = 0
        setup_usd = 0
        mrr_usd = 0
        metros_set = set()

        for p in items:
            st = str(p.get("status") or "SCOUTED").upper()
            step_max = max_step_delivered(p)
            views = int(p.get("demo_views") or 0)
            mstep = int(p.get("max_step_reached") or 0)
            leads = int(p.get("test_leads") or 0) + int(p.get("prod_leads") or 0)

            total_demo_views += views
            total_leads_captured += leads

            if st == "BOUNCED_MX":
                bounces += 1
            else:
                city = (p.get("city") or "").strip()
                state_code = (p.get("state") or "").strip()
                if city and state_code:
                    metros_set.add(f"{city}, {state_code}")
                setup_usd += int(p.get("proposed_setup_fee_usd") or p.get("setup_fee") or 0)
                mrr_usd += int(p.get("proposed_retainer_usd") or p.get("monthly_retainer") or 0)

            if st == "UNSUBSCRIBED":
                unsubscribes += 1
            if st == "QUEUED_STEP_1":
                queued_step_1 += 1
            if st in ("REPLIED", "CLOSED_WON", "CLOSED"):
                human_replies += 1
            if st in ("SENT", "REPLIED", "CLOSED_WON", "CLOSED", "UNSUBSCRIBED") or (
                st != "BOUNCED_MX" and step_max >= 1
            ):
                active_sent += 1
            if st != "BOUNCED_MX" and step_max >= 2:
                step2_plus_delivered += 1
            if mstep >= 2 or leads >= 1:
                engaged_demos += 1

        demo_engagement_rate = round(engaged_demos / max(1, step2_plus_delivered), 4)
        reply_rate = round(human_replies / max(1, active_sent), 4)
        bounce_rate = round(bounces / max(1, active_sent + bounces), 4)

        verdict = classify_vertical(step2_plus_delivered, demo_engagement_rate, reply_rate, human_replies)

        prev_v = prev_verticals.get(v) or {}
        prev_verdict = prev_v.get("verdict")
        alerted = list(prev_v.get("alerted_verdicts") or [])
        if mark_alerted_verdicts and v in mark_alerted_verdicts:
            for tag in mark_alerted_verdicts[v]:
                if tag not in alerted:
                    alerted.append(tag)

        is_first_decision = verdict in ("SCALE", "PIVOT") and verdict not in alerted
        if is_first_decision:
            new_transitions.append({
                "vertical": v,
                "previous_verdict": prev_verdict or "NONE",
                "new_verdict": verdict,
            })

        metrics = {
            "total_prospects": total_prospects,
            "active_sent": active_sent,
            "queued_step_1": queued_step_1,
            "step2_plus_delivered": step2_plus_delivered,
            "engaged_demos": engaged_demos,
            "total_demo_views": total_demo_views,
            "total_leads_captured": total_leads_captured,
            "human_replies": human_replies,
            "bounces": bounces,
            "unsubscribes": unsubscribes,
            "demo_engagement_rate": demo_engagement_rate,
            "reply_rate": reply_rate,
            "bounce_rate": bounce_rate,
            "active_pipeline_setup_usd": setup_usd,
            "active_pipeline_mrr_usd": mrr_usd,
            "active_pipeline_y1_usd": setup_usd + (mrr_usd * 12),
        }

        meta = VERTICAL_CATALOG.get(v, {
            "display_en": v.replace("_", " ").title(),
            "display_es": v.replace("_", " ").title(),
            "avg_ticket_usd": "$10,000 – $20,000",
        })
        metros_sorted = sorted(metros_set)
        rec = build_recommendations(v, verdict, metrics, metros_sorted, active_vertical_set)

        vertical_results[v] = {
            "vertical": v,
            "display_name": {
                "en": meta["display_en"],
                "es": meta["display_es"],
            },
            "avg_ticket_usd": meta["avg_ticket_usd"],
            "verdict": verdict,
            "previous_verdict": prev_verdict,
            "alerted_verdicts": alerted,
            "metros": metros_sorted,
            "metrics": metrics,
            "recommendation": rec,
        }

    # Global executive summary across all verticals
    verdicts_list = [x["verdict"] for x in vertical_results.values()]
    if "SCALE" in verdicts_list:
        agency_mode = "SCALE_ACTIVE"
        headline_en = "Winner vertical detected — prioritize high-ticket metro expansion."
        headline_es = "Vertical ganadora detectada — priorizar expansión a nuevos mercados."
    elif "PIVOT" in verdicts_list:
        agency_mode = "PIVOT_RECOMMENDED"
        top_cand = pick_pivot_candidate(active_vertical_set)
        headline_en = f"Low-traction vertical flagged — shift next wave to {top_cand['en']['name']}."
        headline_es = f"Vertical de baja tracción detectada — mover siguiente ola a {top_cand['es']['name']}."
    else:
        agency_mode = "TESTING_DISCIPLINE"
        headline_en = "All active verticals in signal-gathering mode — let Cloud AutoPilot deliver 15+ Step 2 demos."
        headline_es = "Todas las verticales activas en recopilación de señal — dejar que Cloud AutoPilot entregue 15+ demos Paso 2."

    backlog_filtered = [
        item for item in NEXT_VERTICAL_BACKLOG if item["vertical"] not in active_vertical_set
    ]

    payload = {
        "schema_version": "1.0.0",
        "agent": "00-niche-evaluator",
        "evaluated_at": utc_iso(),
        "thresholds": {
            "scale_min_step2_delivered": SCALE_MIN_STEP2,
            "scale_min_demo_engagement_rate": SCALE_MIN_ENG_RATE,
            "scale_min_reply_rate": SCALE_MIN_REPLY_RATE,
            "testing_hold_step2_delivered": TESTING_HOLD_STEP2,
            "pivot_min_step2_delivered": PIVOT_MIN_STEP2,
            "pivot_max_demo_engagement_rate": PIVOT_MAX_ENG_RATE,
        },
        "agency_summary": {
            "mode": agency_mode,
            "active_vertical_count": len(vertical_results),
            "scale_count": verdicts_list.count("SCALE"),
            "testing_count": verdicts_list.count("TESTING"),
            "pivot_count": verdicts_list.count("PIVOT"),
            "headline": {
                "en": headline_en,
                "es": headline_es,
            },
        },
        "verticals": vertical_results,
        "next_vertical_backlog": backlog_filtered,
        "new_transitions": new_transitions,
    }

    if write_files:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
        if public_output_path:
            os.makedirs(os.path.dirname(public_output_path), exist_ok=True)
            shutil.copy2(output_path, public_output_path)

    return payload


def persist_alerted_verdict(vertical: str, verdict: str, output_path: str = INTEL_PATH, public_output_path: str | None = PUBLIC_INTEL_PATH):
    """Record that a [NICHE DECISION] email was sent for (vertical, verdict) to prevent duplicate alerts."""
    if not os.path.exists(output_path):
        return
    with open(output_path, encoding="utf-8") as f:
        data = json.load(f)
    v_obj = (data.get("verticals") or {}).get(vertical)
    if not v_obj:
        return
    alerted = list(v_obj.get("alerted_verdicts") or [])
    if verdict not in alerted:
        alerted.append(verdict)
    v_obj["alerted_verdicts"] = alerted
    data["new_transitions"] = [
        t for t in (data.get("new_transitions") or [])
        if not (t.get("vertical") == vertical and t.get("new_verdict") == verdict)
    ]
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    if public_output_path:
        os.makedirs(os.path.dirname(public_output_path), exist_ok=True)
        shutil.copy2(output_path, public_output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Forge Lead Studio — Agent 00 Autonomous Niche Evaluator & Pivot Engine")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate without writing tracking/niche_intelligence.json")
    parser.add_argument("--crm", default=CRM_PATH, help="Path to crm_pipeline.json")
    parser.add_argument("--json", action="store_true", help="Print full JSON payload to stdout")
    args = parser.parse_args()

    result = evaluate_niches(
        crm_path=args.crm,
        output_path=INTEL_PATH,
        public_output_path=PUBLIC_INTEL_PATH,
        write_files=not args.dry_run,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print(f"[AGENT 00] Evaluated {result['agency_summary']['active_vertical_count']} verticals at {result['evaluated_at']}")
    for v, info in result["verticals"].items():
        m = info["metrics"]
        print(
            f"  - {v.upper():<10} | Verdict={info['verdict']:<7} | "
            f"Total={m['total_prospects']:>2} | ActiveSent={m['active_sent']:>2} | Step2+={m['step2_plus_delivered']:>2} | "
            f"Engaged={m['engaged_demos']:>2} ({m['demo_engagement_rate']*100:>4.1f}%) | "
            f"Replies={m['human_replies']:>2} ({m['reply_rate']*100:>4.1f}%) | "
            f"Bounces={m['bounces']} | Unsub={m['unsubscribes']}"
        )
        print(f"    EN: {info['recommendation']['en']['headline']}")
        print(f"    ES: {info['recommendation']['es']['headline']}")
    if result["new_transitions"]:
        print(f"  [TRANSITIONS] New first-time decisions: {result['new_transitions']}")
    if not args.dry_run:
        print(f"  [SAVED] {INTEL_PATH} & {PUBLIC_INTEL_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
