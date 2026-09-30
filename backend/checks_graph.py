"""
LangGraph state graph for the compliance checker workflow (T1-T6).

    ingest -> classify -> extract -> route -> [selected checkers] -> compile

Distinct from `graph.py`, which is the original advisory analysis graph behind
/analyze and the Analyst page. Both are LangGraph; they are separate compiled
graphs with separate checkpointers, and they share the six advisory agent
nodes from `agents.analysis` rather than duplicating them.

`route` is a conditional edge that returns a *list* of node names, so the
selected checkers run in parallel and converge on the compiler. Which ones
get selected depends on the document types actually detected in the upload --
see `pipeline.plan_route`.

The six original advisory agents are still here, unchanged. They are now one
of the routed branches rather than the whole pipeline, and fire only for
planning documents.
"""

from typing import List

from langgraph.graph import StateGraph, END

from agents.analysis import (
    specification_validator_agent,
    lcca_agent,
    market_scoping_agent,
    green_sustainable_agent,
    tatak_pinoy_agent,
    compliance_modality_agent,
    gamma_generator_node,
)
from persistence.checkpoint import get_checkpointer
from pipeline import (
    CHECKER_NODES,
    classify_node,
    compile_node,
    consistency_checks_node,
    extract_node,
    ingest_node,
    route,
    route_node,
    rule_checks_node,
)
from state import AgentState


workflow = StateGraph(AgentState)

# -- ingestion and fact extraction ----------------------------------------
workflow.add_node("ingest", ingest_node)
workflow.add_node("classify", classify_node)
workflow.add_node("extract", extract_node)
workflow.add_node("route", route_node)

# -- checkers --------------------------------------------------------------
workflow.add_node("rule_checks", rule_checks_node)  # T1, T2, T3
workflow.add_node("consistency_checks", consistency_checks_node)  # T4, T5, T6

# The original six, preserved as the planning advisory branch.
workflow.add_node("spec_validator", specification_validator_agent)
workflow.add_node("lcca_analyzer", lcca_agent)
workflow.add_node("market_researcher", market_scoping_agent)
workflow.add_node("sustainability_analyst", green_sustainable_agent)
workflow.add_node("domestic_preference_checker", tatak_pinoy_agent)
workflow.add_node("modality_advisor", compliance_modality_agent)

workflow.add_node("report_compiler", compile_node)
workflow.add_node("gamma_generator", gamma_generator_node)

workflow.set_entry_point("ingest")
workflow.add_edge("ingest", "classify")
workflow.add_edge("classify", "extract")
workflow.add_edge("extract", "route")

# Fan out to whichever checkers the router selected. `report_compiler` is in
# the path map because a packet with nothing readable routes straight to it,
# so the run still produces a report saying why.
workflow.add_conditional_edges(
    "route",
    route,
    {name: name for name in CHECKER_NODES} | {"report_compiler": "report_compiler"},
)

# Every checker converges on the compiler.
for _checker in CHECKER_NODES:
    workflow.add_edge(_checker, "report_compiler")


def should_generate_gamma(state: AgentState) -> str:
    """Determine if Gamma presentation should be generated."""
    if state.get("generate_gamma", False):
        return "gamma_generator"
    return END


# After compiler, interrupt for human review
workflow.add_conditional_edges(
    "report_compiler",
    should_generate_gamma,
    {"gamma_generator": "gamma_generator", END: END},
)

workflow.add_edge("gamma_generator", END)

# A persistent checkpointer, so a session survives a backend restart -- the
# archive depends on it, and so does resuming a paused review.
checkpointer = get_checkpointer()
graph = workflow.compile(checkpointer=checkpointer, interrupt_after=["report_compiler"])


def create_initial_state(thread_id: str, pdf_paths: List[str]) -> AgentState:
    """
    Create initial state for a new analysis session.

    Args:
        thread_id: Unique identifier for this session
        pdf_paths: Paths to uploaded files

    Returns:
        Initial AgentState with empty/default values
    """
    return {
        "original_pdf_paths": pdf_paths,
        "thread_id": thread_id,
        "loaded_documents": [],
        "parsed_text": "",
        "documents": [],
        "routed_checkers": [],
        "findings": [],
        "analysis_results": {
            "spec_check": {},
            "lcca": {},
            "market_scope": {},
            "green": {},
            "tatak_pinoy": {},
            "compliance": {},
        },
        "compiled_report": "",
        "human_feedback": "",
        "generate_gamma": False,
        "gamma_link": "",
        "thinking_logs": [],
    }


def get_state(thread_id: str) -> AgentState:
    """
    Retrieve current state for a thread.

    Args:
        thread_id: Thread identifier

    Returns:
        Current state or None if not found
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        state_snapshot = graph.get_state(config)
        return state_snapshot.values if state_snapshot else None
    except Exception:
        return None


def resume_graph(thread_id: str, generate_gamma: bool = False) -> dict:
    """
    Resume graph execution after human-in-the-loop decision.

    Args:
        thread_id: Thread identifier
        generate_gamma: Whether to generate Gamma presentation

    Returns:
        Final state after graph execution completes
    """
    config = {"configurable": {"thread_id": thread_id}}

    # Update state with human decision
    current_state = graph.get_state(config)
    if current_state:
        updated_state = current_state.values.copy()
        updated_state["generate_gamma"] = generate_gamma

        # Update state and resume execution
        graph.update_state(config, updated_state)
        # Actually invoke the graph to continue from the interrupt point
        result = graph.invoke(None, config)
        return result
    return {}
