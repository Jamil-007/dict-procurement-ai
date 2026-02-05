"""
LangGraph state graph definition for the procurement analysis workflow.
Manages the multi-agent pipeline with human-in-the-loop capabilities.
"""

from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agents import (
    AgentState,
    pdf_parser_node,
    specification_validator_agent,
    lcca_agent,
    market_scoping_agent,
    green_sustainable_agent,
    tatak_pinoy_agent,
    compliance_modality_agent,
    compiler_agent,
    gamma_generator_node,
)


# Create the state graph
workflow = StateGraph(AgentState)

# Add all nodes
workflow.add_node("pdf_parser", pdf_parser_node)
workflow.add_node("spec_validator", specification_validator_agent)
workflow.add_node("lcca_analyzer", lcca_agent)
workflow.add_node("market_researcher", market_scoping_agent)
workflow.add_node("sustainability_analyst", green_sustainable_agent)
workflow.add_node("domestic_preference_checker", tatak_pinoy_agent)
workflow.add_node("modality_advisor", compliance_modality_agent)
workflow.add_node("report_compiler", compiler_agent)
workflow.add_node("gamma_generator", gamma_generator_node)

# Set entry point
workflow.set_entry_point("pdf_parser")

# Define edges
# pdf_parser fans out to 6 parallel analysis agents
workflow.add_edge("pdf_parser", "spec_validator")
workflow.add_edge("pdf_parser", "lcca_analyzer")
workflow.add_edge("pdf_parser", "market_researcher")
workflow.add_edge("pdf_parser", "sustainability_analyst")
workflow.add_edge("pdf_parser", "domestic_preference_checker")
workflow.add_edge("pdf_parser", "modality_advisor")

# All 6 parallel agents converge to report_compiler
workflow.add_edge("spec_validator", "report_compiler")
workflow.add_edge("lcca_analyzer", "report_compiler")
workflow.add_edge("market_researcher", "report_compiler")
workflow.add_edge("sustainability_analyst", "report_compiler")
workflow.add_edge("domestic_preference_checker", "report_compiler")
workflow.add_edge("modality_advisor", "report_compiler")


# Conditional edge for gamma generation
def should_generate_gamma(state: AgentState) -> str:
    """Determine if Gamma presentation should be generated."""
    if state.get("generate_gamma", False):
        return "gamma_generator"
    return END


# After compiler, interrupt for human review
workflow.add_conditional_edges(
    "report_compiler",
    should_generate_gamma,
    {
        "gamma_generator": "gamma_generator",
        END: END
    }
)

# Gamma generator goes to END
workflow.add_edge("gamma_generator", END)

# Compile the graph with memory checkpointer
checkpointer = MemorySaver()
graph = workflow.compile(checkpointer=checkpointer, interrupt_after=["report_compiler"])


def create_initial_state(thread_id: str, pdf_path: str) -> AgentState:
    """
    Create initial state for a new analysis session.

    Args:
        thread_id: Unique identifier for this session
        pdf_path: Path to the uploaded PDF file

    Returns:
        Initial AgentState with empty/default values
    """
    return {
        "original_pdf_path": pdf_path,
        "parsed_text": "",
        "analysis_results": {
            "spec_check": {},
            "lcca": {},
            "market_scope": {},
            "green": {},
            "tatak_pinoy": {},
            "compliance": {}
        },
        "compiled_report": "",
        "human_feedback": "",
        "generate_gamma": False,
        "gamma_link": "",
        "thread_id": thread_id,
        "thinking_logs": []
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


def resume_graph(thread_id: str, generate_gamma: bool = False) -> None:
    """
    Resume graph execution after human-in-the-loop decision.

    Args:
        thread_id: Thread identifier
        generate_gamma: Whether to generate Gamma presentation
    """
    config = {"configurable": {"thread_id": thread_id}}

    # Update state with human decision
    current_state = graph.get_state(config)
    if current_state:
        updated_state = current_state.values.copy()
        updated_state["generate_gamma"] = generate_gamma

        # Resume execution
        graph.update_state(config, updated_state)
