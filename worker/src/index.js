/**
 * Forge Lead Studio — Production Lead Router & Demo Telemetry Worker
 * Endpoints:
 *   GET  /health                       — Liveness probe
 *   POST /event                        — Ingests demo views, step progress, and trojan:lead_captured payloads
 *   GET  /stats?secret=<ADMIN_KEY>     — Returns aggregated KV telemetry for all prospects
 *   PUT  /route?secret=<ADMIN_KEY>     — Configures a signed client's production webhook/email route
 *   DELETE /stats?secret=<ADMIN_KEY>&prospect_id=<id> — Admin cleanup for synthetic test records
 */

function buildCorsHeaders(request) {
  const origin = request?.headers?.get('origin');
  if (origin) {
    return {
      'access-control-allow-origin': origin,
      'access-control-allow-credentials': 'true',
      'access-control-allow-methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'access-control-allow-headers': 'Content-Type, X-Admin-Key',
      'access-control-max-age': '86400',
      'vary': 'Origin',
    };
  }
  return {
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'access-control-allow-headers': 'Content-Type, X-Admin-Key',
    'access-control-max-age': '86400',
  };
}

const MAX_BODY_BYTES = 32768;
const BOT_UA_RE = /HeadlessChrome|Playwright|Puppeteer|Lighthouse|Chrome-Lighthouse|bot\b|crawler|spider|slurp|curl\/|wget\/|python-urllib|python-requests/i;
const VALID_PID_RE = /^[a-z0-9][a-z0-9_-]{2,84}$/i;

function jsonResp(data, status = 200, request = null) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      ...buildCorsHeaders(request),
    },
  });
}

async function verifyAdminSecret(provided, expected) {
  if (!provided || !expected) return false;
  const enc = new TextEncoder();
  const [h1, h2] = await Promise.all([
    crypto.subtle.digest('SHA-256', enc.encode(String(provided))),
    crypto.subtle.digest('SHA-256', enc.encode(String(expected))),
  ]);
  return crypto.subtle.timingSafeEqual(h1, h2);
}

async function readBoundedJson(request) {
  const lenHdr = Number(request.headers.get('content-length') || 0);
  if (lenHdr > MAX_BODY_BYTES) return { error: 'Payload too large', status: 413 };
  const buf = await request.arrayBuffer();
  if (buf.byteLength > MAX_BODY_BYTES) return { error: 'Payload too large', status: 413 };
  if (buf.byteLength === 0) return { error: 'Empty body', status: 400 };
  try {
    return { data: JSON.parse(new TextDecoder().decode(buf)) };
  } catch {
    return { error: 'Invalid JSON payload', status: 400 };
  }
}

async function forwardProductionLead(webhookUrl, leadRecord) {
  try {
    const res = await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'user-agent': 'ForgeLeadRouter/1.0' },
      body: JSON.stringify(leadRecord),
    });
    console.log(JSON.stringify({ event: 'webhook_forwarded', prospect_id: leadRecord.prospect_id, lead_id: leadRecord.lead_id, status: res.status }));
  } catch (err) {
    console.error(JSON.stringify({ event: 'webhook_error', prospect_id: leadRecord.prospect_id, lead_id: leadRecord.lead_id, error: String(err) }));
  }
}

export default {
  async fetch(request, env, ctx) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: buildCorsHeaders(request) });
    }
    const reply = (data, status = 200) => jsonResp(data, status, request);

    const url = new URL(request.url);
    const path = url.pathname;
    const nowIso = new Date().toISOString();

    if (request.method === 'GET' && (path === '/' || path === '/health')) {
      return reply({ ok: true, service: 'forge-lead-router', ts: nowIso });
    }

    // ==================== POST /event ====================
    if (request.method === 'POST' && path === '/event') {
      const ua = request.headers.get('user-agent') || '';
      if (BOT_UA_RE.test(ua)) {
        return reply({ ok: true, ignored: 'bot_ua' }, 202);
      }

      const parsed = await readBoundedJson(request);
      if (parsed.error) return reply({ ok: false, error: parsed.error }, parsed.status);

      const body = parsed.data || {};
      const pid = String(body.prospect_id || '').trim();
      const eventType = String(body.event_type || 'view').trim().toLowerCase();
      const mode = String(body.mode || 'demo').trim().toLowerCase() === 'production' ? 'production' : 'demo';
      const stepNum = Math.max(0, Math.min(4, Number(body.step) || (eventType === 'lead_captured' ? 4 : eventType === 'view' ? 1 : 0)));
      const eventTs = typeof body.ts === 'string' && body.ts.length >= 10 ? body.ts : nowIso;

      if (!VALID_PID_RE.test(pid)) {
        return reply({ ok: false, error: 'Invalid prospect_id' }, 400);
      }

      const statsKey = `stats:${pid}`;
      const existing = (await env.FORGE_TELEMETRY.get(statsKey, { type: 'json' })) || {
        prospect_id: pid,
        views: 0,
        max_step_reached: 0,
        test_leads: 0,
        prod_leads: 0,
        last_viewed_at: null,
        last_event_at: null,
        recent_leads: [],
      };

      if (eventType === 'view' || eventType === 'page_view') {
        existing.views = (Number(existing.views) || 0) + 1;
        existing.last_viewed_at = eventTs;
        existing.max_step_reached = Math.max(Number(existing.max_step_reached) || 0, stepNum || 1);
      } else if (eventType === 'step' || eventType === 'step_reached') {
        if (!existing.views) {
          existing.views = 1;
          existing.last_viewed_at = eventTs;
        }
        existing.max_step_reached = Math.max(Number(existing.max_step_reached) || 0, stepNum);
      } else if (eventType === 'lead_captured') {
        const pl = body.payload || {};
        const leadObj = pl.lead || {};
        const prof = pl.roof_profile || {};
        const est = pl.estimate || {};
        const leadId = crypto.randomUUID();

        const leadRecord = {
          lead_id: leadId,
          prospect_id: pid,
          mode,
          captured_at: pl.captured_at || eventTs,
          reference_id: pl.reference_id || leadId.slice(0, 8).toUpperCase(),
          name: leadObj.full_name || pl.name || '',
          contact: leadObj.contact || pl.contact || '',
          contact_type: leadObj.contact_type || '',
          preferred_window: leadObj.preferred_window || '',
          address: leadObj.address || pl.address || '',
          roof_size: prof.sqft || pl.roof_size || null,
          stories: prof.stories || '',
          pitch: prof.pitch || '',
          condition: prof.condition || '',
          material: est.material_label || prof.material || pl.material || '',
          estimated_range: est.min_usd && est.max_usd ? `$${Number(est.min_usd).toLocaleString('en-US')}–$${Number(est.max_usd).toLocaleString('en-US')}` : (pl.estimated_range || ''),
          monthly_payment: est.monthly_min_usd ? `$${Number(est.monthly_min_usd).toLocaleString('en-US')}/mo` : (pl.monthly_payment || ''),
          raw_payload: pl,
        };

        await env.FORGE_TELEMETRY.put(`lead:${pid}:${leadId}`, JSON.stringify(leadRecord));

        if (!existing.views) {
          existing.views = 1;
          existing.last_viewed_at = eventTs;
        }
        existing.max_step_reached = 4;
        if (mode === 'production') {
          existing.prod_leads = (Number(existing.prod_leads) || 0) + 1;
          const routeCfg = await env.FORGE_TELEMETRY.get(`route:${pid}`, { type: 'json' });
          const targetWebhook = routeCfg?.active !== false && routeCfg?.webhook_url ? routeCfg.webhook_url : null;
          if (targetWebhook && targetWebhook.startsWith('https://')) {
            ctx.waitUntil(forwardProductionLead(targetWebhook, leadRecord));
          }
        } else {
          existing.test_leads = (Number(existing.test_leads) || 0) + 1;
        }

        const recent = Array.isArray(existing.recent_leads) ? existing.recent_leads : [];
        recent.unshift({
          lead_id: leadId,
          reference_id: leadRecord.reference_id,
          mode,
          captured_at: leadRecord.captured_at,
          name: leadRecord.name,
          contact: leadRecord.contact,
          roof_size: leadRecord.roof_size,
          material: leadRecord.material,
          estimated_range: leadRecord.estimated_range,
          monthly_payment: leadRecord.monthly_payment,
        });
        existing.recent_leads = recent.slice(0, 10);
      } else {
        return reply({ ok: false, error: `Unsupported event_type '${eventType}'` }, 400);
      }

      existing.last_event_at = eventTs;
      await env.FORGE_TELEMETRY.put(statsKey, JSON.stringify(existing));

      console.log(JSON.stringify({ event: 'telemetry_ingested', prospect_id: pid, event_type: eventType, mode, views: existing.views, max_step: existing.max_step_reached }));
      return reply({ ok: true, prospect_id: pid, views: existing.views, max_step_reached: existing.max_step_reached });
    }

    // ==================== ADMIN AUTH CHECK ====================
    const secret = url.searchParams.get('secret') || request.headers.get('x-admin-key') || '';
    const isAdmin = await verifyAdminSecret(secret, env.ADMIN_KEY);

    // ==================== GET /stats ====================
    if (request.method === 'GET' && path === '/stats') {
      if (!isAdmin) return reply({ ok: false, error: 'Unauthorized' }, 401);

      const keys = [];
      let cursor;
      do {
        const listed = await env.FORGE_TELEMETRY.list({ prefix: 'stats:', cursor });
        for (const k of listed.keys) keys.push(k.name);
        cursor = listed.list_complete ? undefined : listed.cursor;
      } while (cursor);

      const entries = await Promise.all(
        keys.map(async k => {
          const val = await env.FORGE_TELEMETRY.get(k, { type: 'json' });
          return [k.slice('stats:'.length), val];
        })
      );

      const prospects = {};
      for (const [pid, val] of entries) {
        if (val) prospects[pid] = val;
      }

      return reply({
        ok: true,
        generated_at: nowIso,
        count: Object.keys(prospects).length,
        prospects,
      });
    }

    // ==================== PUT /route (Production client webhook config) ====================
    if (request.method === 'PUT' && path === '/route') {
      if (!isAdmin) return reply({ ok: false, error: 'Unauthorized' }, 401);
      const parsed = await readBoundedJson(request);
      if (parsed.error) return reply({ ok: false, error: parsed.error }, parsed.status);
      const { prospect_id: pid, webhook_url, notify_email, active = true } = parsed.data || {};
      if (!VALID_PID_RE.test(String(pid || ''))) return reply({ ok: false, error: 'Invalid prospect_id' }, 400);
      if (webhook_url && !String(webhook_url).startsWith('https://')) return reply({ ok: false, error: 'webhook_url must use https://' }, 400);
      const routeObj = { prospect_id: pid, webhook_url: webhook_url || null, notify_email: notify_email || null, active: Boolean(active), updated_at: nowIso };
      await env.FORGE_TELEMETRY.put(`route:${pid}`, JSON.stringify(routeObj));
      return reply({ ok: true, route: routeObj });
    }

    // ==================== DELETE /stats (Admin test record cleanup) ====================
    if (request.method === 'DELETE' && path === '/stats') {
      if (!isAdmin) return reply({ ok: false, error: 'Unauthorized' }, 401);
      const pid = String(url.searchParams.get('prospect_id') || '').trim();
      if (!VALID_PID_RE.test(pid)) return reply({ ok: false, error: 'Invalid prospect_id' }, 400);
      await env.FORGE_TELEMETRY.delete(`stats:${pid}`);
      const leads = await env.FORGE_TELEMETRY.list({ prefix: `lead:${pid}:` });
      await Promise.all(leads.keys.map(k => env.FORGE_TELEMETRY.delete(k.name)));
      return reply({ ok: true, deleted: pid, deleted_leads: leads.keys.length });
    }

    return reply({ ok: false, error: 'Not Found' }, 404);
  },
};
