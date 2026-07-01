"""Instrumented versions of graph queries with real-time visualization.

Wraps the query functions to emit visualization events showing:
  - Graph traversal (nodes visited, edges followed)
  - Filtering logic
  - Data chunks sent to LLM
  - Performance metrics
"""
from __future__ import annotations

import json
from typing import Optional

import networkx as nx

from senpai.data import store
from senpai.graph.build import deal_nodes, graph
from senpai.graph import query as base_query
from senpai.graph.visualization import create_query_tracer, QueryTracer


def _format_node_label(node_id: str, kind: str, attrs: dict) -> str:
    """Format a readable label for a node."""
    if kind == "rep":
        return f"Rep: {attrs.get('name', node_id)}"
    elif kind == "customer":
        return f"Customer: {attrs.get('name', node_id)}"
    elif kind == "deal":
        return f"Deal: {attrs.get('name', node_id)} ({attrs.get('outcome', '?')})"
    elif kind == "product":
        return f"Product: {attrs.get('name', node_id)}"
    elif kind == "category":
        return f"Category: {node_id.replace('category:', '')}"
    elif kind == "industry":
        return f"Industry: {node_id.replace('industry:', '')}"
    else:
        return node_id


def reps_who_win_viz(category: str = "", industry: str = "",
                     after_activity_type: str = "", min_deals: int = 1,
                     tracer: Optional[QueryTracer] = None) -> list[dict]:
    """Instrumented reps_who_win query."""
    if not tracer:
        tracer = create_query_tracer("reps_who_win", {
            "category": category,
            "industry": industry,
            "after_activity_type": after_activity_type,
            "min_deals": min_deals,
        })

    G = graph()
    tracer.start_step(1, f"Building graph with {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # Report the graph structure
    for n, attrs in G.nodes(data=True):
        if attrs.get("kind") == "deal":
            tracer.visit_node(n, attrs.get("kind", "?"), _format_node_label(n, attrs.get("kind"), attrs))

    tracer.end_step()

    # Step 2: Filtering
    tracer.start_step(2, f"Filtering deals by category={category}, industry={industry}, activity_type={after_activity_type}")

    agg: dict[str, dict] = {}
    context_chunks = []

    for did, a in deal_nodes(G):
        if a.get("outcome") == "open":
            continue
        if category and category not in (a.get("category") or ""):
            continue
        if industry and industry not in (a.get("industry") or ""):
            continue
        if after_activity_type and not any(
                after_activity_type in t for t in a.get("acttypes", ())):
            continue

        # Node was visited AND matched filter
        tracer.visit_node(
            did, "deal",
            _format_node_label(did, "deal", a),
            depth=1,
            attributes={"category": a.get("category"), "industry": a.get("industry"), "outcome": a.get("outcome")},
            matched=True,
        )

        # Record the deal in aggregation
        rep = a.get("rep") or "?"
        v = agg.setdefault(rep, {"won": 0, "closed": 0, "deals": []})
        v["closed"] += 1
        v["deals"].append(did)
        if a.get("outcome") == "won":
            v["won"] += 1

        # Add to context for LLM
        context_chunks.append(
            f"Deal {did}: {a.get('name')} | "
            f"Category: {a.get('category')} | "
            f"Industry: {a.get('industry')} | "
            f"Outcome: {a.get('outcome')} | "
            f"Amount: {a.get('amount')}"
        )

    tracer.end_step()

    # Step 3: Aggregation and ranking
    tracer.start_step(3, "Aggregating wins by rep and ranking")

    rows = []
    for rep, v in agg.items():
        if v["closed"] < max(1, int(min_deals)):
            continue
        # Visit rep node
        tracer.visit_node(
            rep, "rep",
            _format_node_label(rep, "rep", {"name": store.rep_name(rep)}),
            depth=2,
            attributes={"won": v["won"], "closed": v["closed"]},
            matched=True,
        )
        rows.append({
            "rep_id": rep, "rep_name": store.rep_name(rep),
            "won": v["won"], "closed": v["closed"],
            "win_rate": round(v["won"] / v["closed"], 3) if v["closed"] else 0.0,
            "example_deal_ids": sorted(v["deals"])[:6],
        })

    rows.sort(key=lambda r: (r["win_rate"], r["won"], r["closed"]), reverse=True)
    tracer.end_step()

    # Prepare context for LLM
    context_sources = [f"filtered_deal_{i}" for i in range(len(context_chunks))]
    tracer.add_context_window(context_chunks, context_sources)

    # Set result summary
    tracer.set_result(
        f"Found {len(rows)} reps matching criteria, top performer: {rows[0]['rep_name'] if rows else 'N/A'} with {rows[0]['win_rate'] if rows else 0}% win rate",
        len(rows),
    )

    tracer.finalize()
    return rows


def account_graph_viz(customer: str, tracer: Optional[QueryTracer] = None) -> dict:
    """Instrumented account_graph query."""
    if not tracer:
        tracer = create_query_tracer("account_graph", {"customer": customer})

    tracer.start_step(1, f"Resolving customer: {customer}")
    c = store.resolve_customer(customer)
    if not c:
        tracer.set_result(f"Customer not found: {customer}", 0)
        tracer.finalize()
        return {"status": "not_found", "query": customer}

    cid = c["customer_id"]
    tracer.visit_node(
        cid, "customer",
        _format_node_label(cid, "customer", c),
        depth=0,
        attributes=c,
        matched=True,
    )
    tracer.end_step()

    # Step 2: Find deals
    tracer.start_step(2, f"Finding deals for customer {cid}")
    G = graph()
    deal_ids = [u for u, _v, d in G.in_edges(cid, data=True) if d.get("rel") == "FOR"]

    deals, reps, products = [], set(), set()
    context_chunks = []

    for did in deal_ids:
        a = G.nodes[did]
        tracer.visit_node(
            did, "deal",
            _format_node_label(did, "deal", a),
            depth=1,
            attributes={"outcome": a.get("outcome"), "amount": a.get("amount")},
            matched=True,
        )
        tracer.traverse_edge(cid, did, "FOR")

        deals.append({
            "deal_id": did, "name": a.get("name", ""), "rank": a.get("rank", ""),
            "outcome": a.get("outcome", ""), "amount": a.get("amount", 0),
        })

        if a.get("rep"):
            reps.add(a["rep"])
            tracer.traverse_edge(did, a["rep"], "OWNS")

        products.update(a.get("products", ()))
        context_chunks.append(
            f"Deal {did}: {a.get('name')} | Amount: {a.get('amount')} | Outcome: {a.get('outcome')}"
        )

    tracer.end_step()

    # Step 3: Enrich with rep and product details
    tracer.start_step(3, f"Enriching with {len(reps)} reps and {len(products)} products")

    for rep in reps:
        tracer.visit_node(
            rep, "rep",
            _format_node_label(rep, "rep", {"name": store.rep_name(rep)}),
            depth=2,
        )

    for prod in products:
        prod_data = store.get_product(prod) or {}
        tracer.visit_node(
            prod, "product",
            _format_node_label(prod, "product", {"name": prod_data.get("product_name", prod)}),
            depth=2,
        )

    deals.sort(key=lambda d: d["deal_id"])
    tracer.end_step()

    # Prepare context
    context_sources = [f"deal_{i}" for i in range(len(context_chunks))]
    tracer.add_context_window(context_chunks, context_sources)

    result = {
        "status": "found", "customer_id": cid, "name": c.get("name", ""),
        "industry": c.get("industry", ""), "size": c.get("size", ""),
        "deals": deals,
        "reps": [{"rep_id": r, "name": store.rep_name(r)} for r in sorted(reps)],
        "products": [{"code": p, "name": (store.get_product(p) or {}).get("product_name", p)}
                     for p in sorted(products)],
    }

    tracer.set_result(f"Found {len(deals)} deals, {len(reps)} reps, {len(products)} products", len(deals))
    tracer.finalize()
    return result


def connections_viz(entity_a: str, entity_b: str, tracer: Optional[QueryTracer] = None) -> dict:
    """Instrumented connections query showing shortest path."""
    if not tracer:
        tracer = create_query_tracer("connections", {"entity_a": entity_a, "entity_b": entity_b})

    tracer.start_step(1, f"Resolving entities: {entity_a} and {entity_b}")
    G = graph()

    ua = base_query._resolve_node(entity_a)
    ub = base_query._resolve_node(entity_b)

    if not ua or not ub:
        tracer.set_result(f"Could not resolve entities", 0)
        tracer.finalize()
        return {"status": "not_found", "a": entity_a, "b": entity_b}

    tracer.visit_node(ua, G.nodes[ua].get("kind"), _format_node_label(ua, G.nodes[ua].get("kind"), G.nodes[ua]), depth=0, matched=True)
    tracer.visit_node(ub, G.nodes[ub].get("kind"), _format_node_label(ub, G.nodes[ub].get("kind"), G.nodes[ub]), depth=0, matched=True)
    tracer.end_step()

    # Step 2: Find path
    tracer.start_step(2, f"Finding shortest path from {ua} to {ub}")
    UG = G.to_undirected(as_view=True)
    try:
        path = nx.shortest_path(UG, ua, ub)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        tracer.set_result(f"No path found", 0)
        tracer.finalize()
        return {"status": "no_path", "a": entity_a, "b": entity_b}

    # Trace the path
    context_chunks = []
    for i, node in enumerate(path):
        attrs = G.nodes[node]
        tracer.visit_node(
            node, attrs.get("kind"),
            _format_node_label(node, attrs.get("kind"), attrs),
            depth=i,
            matched=True,
        )
        context_chunks.append(f"Step {i}: {_format_node_label(node, attrs.get('kind'), attrs)}")
        if i < len(path) - 1:
            tracer.traverse_edge(path[i], path[i+1], "CONNECTS")

    tracer.end_step()

    # Prepare context
    context_sources = [f"path_node_{i}" for i in range(len(context_chunks))]
    tracer.add_context_window(context_chunks, context_sources)

    result = {
        "status": "found",
        "hops": len(path) - 1,
        "path": [base_query._describe(n) for n in path],
    }

    tracer.set_result(f"Found path with {len(path)-1} hops", len(path)-1)
    tracer.finalize()
    return result


def similar_by_graph_viz(deal_id: str, limit: int = 5, tracer: Optional[QueryTracer] = None) -> list[dict]:
    """Instrumented similar_by_graph query."""
    if not tracer:
        tracer = create_query_tracer("similar_by_graph", {"deal_id": deal_id, "limit": limit})

    tracer.start_step(1, f"Finding deals similar to {deal_id}")
    G = graph()
    base = G.nodes.get(deal_id)
    if not base or base.get("kind") != "deal":
        tracer.set_result(f"Deal not found: {deal_id}", 0)
        tracer.finalize()
        return []

    tracer.visit_node(deal_id, "deal", _format_node_label(deal_id, "deal", base), depth=0, matched=True)
    rep, cat, ind = base.get("rep"), base.get("category"), base.get("industry")
    prods = set(base.get("products", ()))

    tracer.end_step()

    # Step 2: Score similar deals
    tracer.start_step(2, f"Scoring deals by shared rep/products/industry/category")
    scored = []
    context_chunks = []

    for did, a in deal_nodes(G):
        if did == deal_id:
            continue
        s = 0
        matches = []
        if rep and a.get("rep") == rep:
            s += 1
            matches.append("rep")
        product_matches = len(prods & set(a.get("products", ())))
        if product_matches > 0:
            s += product_matches * 2
            matches.append(f"{product_matches} products")
        if cat and a.get("category") == cat:
            s += 1
            matches.append("category")
        if ind and a.get("industry") == ind:
            s += 1
            matches.append("industry")
        if s:
            scored.append((s, did, a))
            tracer.visit_node(
                did, "deal",
                _format_node_label(did, "deal", a),
                depth=1,
                attributes={"score": s, "matches": matches},
                matched=True,
            )
            context_chunks.append(
                f"Deal {did}: {a.get('name')} (score={s}, matched: {', '.join(matches)})"
            )

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    tracer.end_step()

    # Prepare context
    context_sources = [f"similar_deal_{i}" for i in range(len(context_chunks))]
    tracer.add_context_window(context_chunks, context_sources)

    result = [{"deal_id": did, "name": a.get("name", ""), "outcome": a.get("outcome", ""),
               "score": s} for s, did, a in scored[:limit]]

    tracer.set_result(f"Found {len(result)} similar deals", len(result))
    tracer.finalize()
    return result
