"""New exploratory pre-inference routing; historical policies remain immutable.

Router confidence refers to route choice, never to generator correctness.
The deterministic input gate is applied after the router and before generation.
All hosted router calls remain external even when the generator is local.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import time
import uuid
from pathlib import Path

from .routing import hard_gate, identify_tool
from .tools import REQUIRED

ROUTES = {'TOOL', 'LOCAL', 'CLOUD', 'CLARIFY', 'ABSTAIN'}

class BeforeRequestBlocked(RuntimeError):
    """No provider request was dispatched; keep this distinct from a failed call."""
    def __init__(self, provider, reason):
        self.provider, self.reason = provider, reason
        super().__init__(provider + ' blocked before request')

QUESTIONS = {
    'route': {'type': 'choice', 'instructions':
        'Choose the next step BEFORE any answer generation. Use only the query, context, numeric inputs, tool contract and runtime constraints. '
        'Do not calculate numerical answers. Prefer the local reader for a short unambiguous fact supported by context. '
        'Compound conditions, negation, competing entities or conflicting evidence require the cloud generator when available. '
        'Missing numerical measurements require clarification. Route confidence is not answer correctness.',
        'criteria': {
            'TOOL': 'Explicit request to compute an available numerical agricultural tool with complete valid inputs.',
            'LOCAL': 'Short context-supported factual or tool-selection answer, no compound/conflicting conditions.',
            'CLOUD': 'Nontrivial reasoning, conjunction, negation, competing entities or uncertain local capability; cloud available.',
            'CLARIFY': 'Essential numerical inputs or units are missing or invalid; ask the user rather than guess.',
            'ABSTAIN': 'No usable evidence and no valid calculation; or required cloud is unavailable.'}},
    'missing_data': {'type': 'noul', 'instructions':
        'Does an explicitly requested numerical calculation lack necessary valid measurements or units? Conceptual QA does not require weather measurements.'}}


def public_state(request, cloud_available=True):
    """Strict input allowlist also excludes labels hidden in extra numeric fields."""
    allowed = set().union(*map(set, REQUIRED.values())) | {
        'daily_min','daily_max','daily_rain','base_c','heat_threshold',
        'rain_target_mm','minimum_temperature','scenario_threshold'}
    inputs = request.get('inputs', {})
    if not isinstance(inputs, dict):
        raise ValueError('Numeric inputs must be an object')
    selected = {k: v for k, v in inputs.items() if k in allowed}
    def contains_mapping(value):
        return isinstance(value,dict) or isinstance(value,(list,tuple)) and any(contains_mapping(v) for v in value)
    if any(contains_mapping(v) for v in selected.values()):
        raise ValueError('Nested numerical inputs are not supported')
    return {'query': str(request.get('input', '')), 'context': str(request.get('context', '')),
            'numeric_inputs': selected, 'tools': {k: {'required': list(v)} for k, v in REQUIRED.items()},
            'constraints': {'cloud_generator_available': bool(cloud_available),
                            'local_capability': 'DEV reader only; probabilities not calibrated for agricultural correctness'}}


def ambiguity_flags(request):
    q, context = str(request.get('input', '')), str(request.get('context', ''))
    text = (q + '\n' + context).lower()
    flags = []
    if re.search(r'\b(and|both|unless|not|never|if|otherwise|conflict|contradict)\b|одновременно|только если|иначе|противореч|\bне\b', text):
        flags.append('condition_negation_or_conflict')
    if context.count(':') >= 2:
        flags.append('multiple_labeled_entities')
    if len(context) > 900:
        flags.append('long_context')
    return flags


def rule_route(request, cloud_available=True):
    tool = identify_tool(str(request.get('input', '')))
    q = str(request.get('input', '')).lower()
    explicit = re.search(r'calculate|compute|рассчита|посчита|вычисли', q)
    selection = re.search(r'select only|choose only|do not calculate|только (выбери|назови)|не (рассчитывай|считай)', q)
    if tool and explicit and not selection:
        missing = [k for k in REQUIRED[tool] if k not in request.get('inputs', {})]
        route = 'CLARIFY' if missing else 'TOOL'
    elif ambiguity_flags(request):
        route = 'CLOUD' if cloud_available else 'ABSTAIN'
    elif str(request.get('context', '')).strip():
        route = 'LOCAL'
    else:
        route = 'CLOUD' if cloud_available else 'ABSTAIN'
    return {'route': route, 'router': 'rule-first-v1', 'router_external_calls': 0,
            'cost_usd': 0., 'error': None, 'confidence': None}


def normalize_router(raw, model, external):
    route = raw.get('answers', {}).get('route', {}).get('choice')
    if route not in ROUTES:
        raise ValueError('Invalid route choice')
    confidence = raw['answers']['route'].get('confidence')
    if confidence is not None and (isinstance(confidence, bool) or not isinstance(confidence, (int,float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1):
        raise ValueError('Invalid route confidence')
    return {'route': route, 'router': model, 'router_external_calls': int(external),
            'confidence': confidence, 'raw': raw, 'error': None,
            'confidence_interpretation': 'uncalibrated route preference; not probability of a correct answer'}


def decide_pre(request, selector, local, cloud, *, cloud_available=True, hosted_router=False):
    """Live full pipeline with conservative fallback and distinct external counts."""
    started = time.perf_counter()
    public = public_state(request, cloud_available)
    clean = {'input': public['query'], 'context': public['context'], 'inputs': public['numeric_inputs']}
    router_start = time.perf_counter()
    if hosted_router and not cloud_available:
        routing = rule_route(clean, False)
        routing['offline_hosted_router_bypass'] = True
    else:
        try:
            routing = selector(clean, cloud_available)
        except Exception as exc:
            routing = {'route': None, 'error': {'type': type(exc).__name__}, 'router_external_calls': 0,
                       'cost_usd': None if hosted_router else 0.}
        if routing.get('error') or routing.get('route') not in ROUTES:
            routing = {**routing, 'fallback': rule_route(clean, cloud_available)}
    router_ms = (time.perf_counter()-router_start)*1000
    selected = (routing.get('fallback') or routing).get('route')
    proposed = selected
    gate = hard_gate(clean)
    traces = []
    flags = ambiguity_flags(clean)
    guard_override = None
    if gate:
        route, output = gate['route'], gate['output']
        selected = 'TOOL' if route == 'DETERMINISTIC_TOOL' else 'CLARIFY'
        tool_calls = gate['tool_calls']
        guard_override = 'shared_deterministic_input_gate'
    else:
        tool_calls = 0
        if selected == 'TOOL':
            selected = rule_route(clean, cloud_available)['route']
            if selected == 'TOOL': selected = 'CLARIFY'
            guard_override = 'unsupported_tool_execution_rejected'
        if selected == 'LOCAL' and flags:
            selected = 'CLOUD' if cloud_available else 'ABSTAIN'
            guard_override = 'shared_prerouting_ambiguity_guard'
        if selected == 'CLOUD' and not cloud_available:
            selected = 'ABSTAIN'
            guard_override = 'cloud_disabled'
        if selected in ('LOCAL','CLOUD'):
            provider = 'local' if selected == 'LOCAL' else 'cloud'
            try:
                result = (local if provider == 'local' else cloud)(clean)
            except Exception as exc:
                blocked = isinstance(exc, BeforeRequestBlocked) or type(exc).__name__ == 'ProviderBlocked'
                result = {'output': None, 'error': {'type': type(exc).__name__}, 'attempted': not blocked,
                          'blocked_reason': getattr(exc,'reason',None),
                          'cost_usd': 0. if blocked or provider=='local' else None}
            traces.append({**result, 'provider': provider})
            route = 'LOCAL_MODEL' if provider == 'local' else 'CLOUD_MODEL'
            output = result.get('output')
            if result.get('error') or not isinstance(output,dict):
                output = {'action':'ABSTAIN','answer':'Generator unavailable or malformed output','numeric':None}
                route = 'ABSTAIN'
        else:
            route = 'ASK_FOR_DATA' if selected == 'CLARIFY' else 'ABSTAIN'
            output = {'action': 'ASK_FOR_DATA' if selected == 'CLARIFY' else 'ABSTAIN',
                      'answer':'Please provide the missing measurements or usable evidence.','numeric':None}
    local_calls = sum(t['provider']=='local' and t.get('attempted',True) for t in traces)
    cloud_calls = sum(t['provider']=='cloud' and t.get('attempted',True) for t in traces)
    router_calls = routing.get('router_external_calls', 0)
    costs = [routing.get('cost_usd',0.)]+[t.get('cost_usd') for t in traces]
    known = [c for c in costs if isinstance(c,(int,float)) and not isinstance(c,bool) and math.isfinite(c) and c>=0]
    return {'status':'MEASURED','route':route,'output':output,'router_trace':routing,
            'proposed_route':proposed,'executed_route_decision':selected,'guard_override':guard_override,
            'ambiguity_flags':flags,'trace':traces,'local_calls':local_calls,'cloud_calls':cloud_calls,
            'router_external_calls':router_calls,'verification_external_calls':0,'retry_calls':0,
            'total_external_requests':router_calls+cloud_calls,'tool_calls':tool_calls,
            'cost_usd':sum(known) if len(known)==len(costs) else None,
            'known_remote_cost_usd':sum(known),'unknown_cost_events':len(costs)-len(known),
            'router_latency_ms':router_ms,'latency_ms':(time.perf_counter()-started)*1000,
            'latency_kind':'live_end_to_end_including_router_and_shared_guards',
            'error':next((t['error'] for t in traces if t.get('error')),None),
            'external_data_scope':'public query/context/approved numeric inputs + tool descriptions; no gold or labels'}


class SharedBudget:
    """One transactional ledger across providers/workers; unknown charges retain reserve."""
    def __init__(self,path,cap=.01):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS limits (id INTEGER PRIMARY KEY CHECK(id=1), cap REAL)')
            db.execute('INSERT OR IGNORE INTO limits VALUES (1,?)',(cap,))
            actual=db.execute('SELECT cap FROM limits WHERE id=1').fetchone()[0]
            if actual != cap: raise ValueError('Shared budget cap mismatch')
            db.execute('CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, provider TEXT, reserve REAL, known REAL, status TEXT)')
    def reserve(self,provider,upper):
        if not math.isfinite(upper) or upper<0: raise ValueError('Invalid cost reserve')
        with sqlite3.connect(self.path,timeout=10) as db:
            db.execute('BEGIN IMMEDIATE')
            cap=db.execute('SELECT cap FROM limits WHERE id=1').fetchone()[0]
            charged=db.execute('SELECT COALESCE(SUM(COALESCE(known,reserve)),0) FROM calls').fetchone()[0]
            if charged+upper>cap: raise RuntimeError('Shared paid budget exhausted')
            identifier=uuid.uuid4().hex
            db.execute('INSERT INTO calls VALUES (?,?,?,NULL,?)',(identifier,provider,upper,'pending'))
            return identifier
    def finish(self,identifier,cost):
        if cost is not None and (not math.isfinite(cost) or cost<0): raise ValueError('Invalid observed cost')
        with sqlite3.connect(self.path) as db:
            row=db.execute('SELECT reserve,status FROM calls WHERE id=?',(identifier,)).fetchone()
            if row is None or row[1]!='pending': raise ValueError('Unknown or finished attempt')
            db.execute('UPDATE calls SET known=?,status=? WHERE id=?',(cost,'known' if cost is not None else 'unknown',identifier))
    def snapshot(self):
        with sqlite3.connect(self.path) as db:
            cap=db.execute('SELECT cap FROM limits WHERE id=1').fetchone()[0]
            rows=[dict(zip(('id','provider','reserve_usd','known_cost_usd','status'),r)) for r in db.execute('SELECT * FROM calls ORDER BY rowid')]
        return {'cap_usd':cap,'attempts':rows,'known_cost_usd':sum(r['known_cost_usd'] or 0 for r in rows),
                'reserved_unknown_usd':sum(r['reserve_usd'] for r in rows if r['known_cost_usd'] is None)}
