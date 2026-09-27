"""
Agent node implementations for the procurement analysis pipeline.
Each agent processes the state and returns updated state with findings.
"""

import json
import time
import uuid
from typing import Dict, Any
from utils.llm_factory import get_llm
from utils.gamma_client import gamma_client
from prompts import (
    RA_12009_DIRECTIVE,
    SPECIFICATION_VALIDATOR_PROMPT,
    LCCA_PROMPT,
    MARKET_SCOPING_PROMPT,
    GREEN_SUSTAINABLE_PROMPT,
    TATAK_PINOY_PROMPT,
    COMPLIANCE_MODALITY_PROMPT,
    COMPILER_PROMPT,
)


# The state and its reducers moved to `state.py` so that the checker nodes in
# `pipeline.py` can share them with these agents without a circular import.
# Re-exported here because callers have been importing them from `agents`.
from state import (  # noqa: E402,F401
    AgentState,
    append_findings,
    append_thinking_logs,
    merge_analysis_results,
)


def create_thinking_log(
    agent: str, message: str, status: str = "active"
) -> Dict[str, Any]:
    """Helper function to create a thinking log entry."""
    return {
        "id": str(uuid.uuid4()),
        "agent": agent,
        "message": message,
        "timestamp": int(time.time() * 1000),  # Convert to milliseconds for JavaScript
        "status": status,
    }


def with_active_log(agent_name: str, active_message: str):
    """
    Decorator that automatically emits an 'active' log when agent starts.
    The wrapped agent function should only return 'complete' logs.
    """

    def decorator(agent_func):
        def wrapper(state: AgentState) -> Dict[str, Any]:
            # Emit active log first
            active_log = create_thinking_log(agent_name, active_message, "active")
            # Run the actual agent function
            agent_result = agent_func(state)

            # Merge results - append agent's logs to active log
            if "thinking_logs" in agent_result:
                combined_logs = [active_log] + agent_result["thinking_logs"]
                agent_result["thinking_logs"] = combined_logs

            return agent_result

        return wrapper

    return decorator


# Ingestion moved to `pipeline.ingest_node`, which handles scanned PDFs via
# vision OCR and keeps each file separate instead of concatenating them into
# one blob. The advisory agents below still read `parsed_text`, which that
# node continues to populate.


@with_active_log("Specification Validator", "Checking specification compliance...")
def specification_validator_agent(state: AgentState) -> Dict[str, Any]:
    """
    Validate procurement specifications for compliance with RA 12009.
    Checks for restrictive specifications and brand names.
    """
    logs = []

    try:
        llm = get_llm()
        prompt = SPECIFICATION_VALIDATOR_PROMPT.format(parsed_text=state["parsed_text"], ra_12009_directive=RA_12009_DIRECTIVE)
        response = llm.invoke(prompt)

        # Extract JSON from response
        content = response.content if hasattr(response, "content") else str(response)

        # Try to parse JSON from the response
        try:
            # Find JSON in response (may be wrapped in markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            result = {
                "compliant": False,
                "issues": ["Failed to parse analysis results"],
                "severity": "medium",
                "recommendations": [],
            }

        logs.append(
            create_thinking_log(
                "Specification Validator", "Specification analysis complete", "complete"
            )
        )

        return {"analysis_results": {"spec_check": result}, "thinking_logs": logs}

    except Exception as e:
        result = {
            "compliant": False,
            "issues": [f"Analysis error: {str(e)}"],
            "severity": "high",
            "recommendations": [],
        }
        logs.append(
            create_thinking_log(
                "Specification Validator", f"Error: {str(e)}", "complete"
            )
        )

        return {"analysis_results": {"spec_check": result}, "thinking_logs": logs}


@with_active_log("LCCA Analyzer", "Analyzing lifecycle costs...")
def lcca_agent(state: AgentState) -> Dict[str, Any]:
    """
    Analyze lifecycle cost considerations and Total Cost of Ownership.
    """
    logs = []

    try:
        llm = get_llm()
        prompt = LCCA_PROMPT.format(parsed_text=state["parsed_text"], ra_12009_directive=RA_12009_DIRECTIVE)
        response = llm.invoke(prompt)

        content = response.content if hasattr(response, "content") else str(response)

        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
        except json.JSONDecodeError:
            result = {
                "tco_considered": False,
                "cost_factors_identified": [],
                "missing_considerations": ["Failed to parse analysis"],
                "severity": "medium",
                "recommendations": [],
            }

        logs.append(
            create_thinking_log(
                "LCCA Analyzer", "Lifecycle cost analysis complete", "complete"
            )
        )

        return {"analysis_results": {"lcca": result}, "thinking_logs": logs}

    except Exception as e:
        result = {
            "tco_considered": False,
            "cost_factors_identified": [],
            "missing_considerations": [f"Analysis error: {str(e)}"],
            "severity": "high",
            "recommendations": [],
        }
        logs.append(
            create_thinking_log("LCCA Analyzer", f"Error: {str(e)}", "complete")
        )

        return {"analysis_results": {"lcca": result}, "thinking_logs": logs}


@with_active_log("Market Researcher", "Researching market prices...")
def market_scoping_agent(state: AgentState) -> Dict[str, Any]:
    """
    Verify ABC alignment with market prices using Tavily search.
    """
    logs = []

    try:
        # Extract key items from parsed text for market research
        # This is a simplified approach - in production, use more sophisticated extraction
        llm = get_llm()

        # First, extract key procurement items to search for
        extraction_prompt = f"""Based on this procurement document, identify the main items/products being procured and their approximate budget.
List them concisely.

Document:
{state["parsed_text"][:3000]}

Respond with just the key items and budget, one per line."""

        extraction_response = llm.invoke(extraction_prompt)
        items_to_search = (
            extraction_response.content
            if hasattr(extraction_response, "content")
            else str(extraction_response)
        )

        # Use Tavily for market research (if configured)
        market_data = f"Market research for items:\n{items_to_search}\n\n"

        try:
            from config import settings

            if settings.TAVILY_API_KEY:
                from tavily import TavilyClient

                tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)

                # Search for market prices
                search_results = tavily.search(
                    query=f"Philippines market price {items_to_search[:200]}",
                    max_results=3,
                )

                market_data += "Search results:\n"
                for result in search_results.get("results", []):
                    market_data += f"- {result.get('title', '')}: {result.get('content', '')[:200]}\n"
            else:
                market_data += (
                    "(Tavily API not configured - using document analysis only)"
                )
        except Exception as search_error:
            market_data += f"(Market search unavailable: {str(search_error)})"

        # Analyze with market data
        prompt = MARKET_SCOPING_PROMPT.format(
            parsed_text=state["parsed_text"], market_data=market_data, ra_12009_directive=RA_12009_DIRECTIVE
        )
        response = llm.invoke(prompt)

        content = response.content if hasattr(response, "content") else str(response)

        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
        except json.JSONDecodeError:
            result = {
                "abc_reasonable": True,
                "market_price_range": "Unable to determine",
                "supplier_availability": "unknown",
                "issues": ["Failed to parse analysis"],
                "severity": "low",
                "recommendations": [],
            }

        logs.append(
            create_thinking_log(
                "Market Researcher", "Market analysis complete", "complete"
            )
        )

        return {"analysis_results": {"market_scope": result}, "thinking_logs": logs}

    except Exception as e:
        result = {
            "abc_reasonable": True,
            "market_price_range": "Analysis unavailable",
            "supplier_availability": "unknown",
            "issues": [f"Analysis error: {str(e)}"],
            "severity": "medium",
            "recommendations": [],
        }
        logs.append(
            create_thinking_log("Market Researcher", f"Error: {str(e)}", "complete")
        )

        return {"analysis_results": {"market_scope": result}, "thinking_logs": logs}


@with_active_log("Sustainability Analyst", "Evaluating sustainability criteria...")
def green_sustainable_agent(state: AgentState) -> Dict[str, Any]:
    """
    Check environmental and sustainability criteria.
    """
    logs = []

    try:
        llm = get_llm()
        prompt = GREEN_SUSTAINABLE_PROMPT.format(parsed_text=state["parsed_text"], ra_12009_directive=RA_12009_DIRECTIVE)
        response = llm.invoke(prompt)

        content = response.content if hasattr(response, "content") else str(response)

        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
        except json.JSONDecodeError:
            result = {
                "green_criteria_included": False,
                "environmental_considerations": [],
                "missing_criteria": ["Failed to parse analysis"],
                "severity": "low",
                "recommendations": [],
            }

        logs.append(
            create_thinking_log(
                "Sustainability Analyst",
                "Sustainability evaluation complete",
                "complete",
            )
        )

        return {"analysis_results": {"green": result}, "thinking_logs": logs}

    except Exception as e:
        result = {
            "green_criteria_included": False,
            "environmental_considerations": [],
            "missing_criteria": [f"Analysis error: {str(e)}"],
            "severity": "medium",
            "recommendations": [],
        }
        logs.append(
            create_thinking_log(
                "Sustainability Analyst", f"Error: {str(e)}", "complete"
            )
        )

        return {"analysis_results": {"green": result}, "thinking_logs": logs}


@with_active_log("Domestic Preference Checker", "Verifying Tatak Pinoy compliance...")
def tatak_pinoy_agent(state: AgentState) -> Dict[str, Any]:
    """
    Verify compliance with Domestic Preference (RA 12009 Section 79).
    """
    logs = []

    try:
        llm = get_llm()
        prompt = TATAK_PINOY_PROMPT.format(parsed_text=state["parsed_text"], ra_12009_directive=RA_12009_DIRECTIVE)
        response = llm.invoke(prompt)

        content = response.content if hasattr(response, "content") else str(response)

        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
        except json.JSONDecodeError:
            result = {
                "domestic_preference_applied": False,
                "local_content_considered": False,
                "compliance_issues": ["Failed to parse analysis"],
                "opportunities": [],
                "severity": "low",
                "recommendations": [],
            }

        logs.append(
            create_thinking_log(
                "Domestic Preference Checker",
                "Tatak Pinoy analysis complete",
                "complete",
            )
        )

        return {"analysis_results": {"tatak_pinoy": result}, "thinking_logs": logs}

    except Exception as e:
        result = {
            "domestic_preference_applied": False,
            "local_content_considered": False,
            "compliance_issues": [f"Analysis error: {str(e)}"],
            "opportunities": [],
            "severity": "medium",
            "recommendations": [],
        }
        logs.append(
            create_thinking_log(
                "Domestic Preference Checker", f"Error: {str(e)}", "complete"
            )
        )

        return {"analysis_results": {"tatak_pinoy": result}, "thinking_logs": logs}


@with_active_log("Modality Advisor", "Determining procurement modality...")
def compliance_modality_agent(state: AgentState) -> Dict[str, Any]:
    """
    Recommend appropriate procurement modality.
    """
    logs = []

    try:
        llm = get_llm()
        prompt = COMPLIANCE_MODALITY_PROMPT.format(parsed_text=state["parsed_text"], ra_12009_directive=RA_12009_DIRECTIVE)
        response = llm.invoke(prompt)

        content = response.content if hasattr(response, "content") else str(response)

        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
        except json.JSONDecodeError:
            result = {
                "recommended_modality": "Competitive Bidding",
                "justification": "Default procurement mode",
                "procurement_characteristics": [],
                "compliance_requirements": ["Failed to parse analysis"],
                "severity": "low",
                "recommendations": [],
            }

        logs.append(
            create_thinking_log(
                "Modality Advisor", "Modality analysis complete", "complete"
            )
        )

        return {"analysis_results": {"compliance": result}, "thinking_logs": logs}

    except Exception as e:
        result = {
            "recommended_modality": "Competitive Bidding",
            "justification": "Analysis error occurred",
            "procurement_characteristics": [],
            "compliance_requirements": [f"Analysis error: {str(e)}"],
            "severity": "medium",
            "recommendations": [],
        }
        logs.append(
            create_thinking_log("Modality Advisor", f"Error: {str(e)}", "complete")
        )

        return {"analysis_results": {"compliance": result}, "thinking_logs": logs}


def advisory_verdict(analysis_results: Dict[str, Any]) -> Dict[str, Any]:
    """Ask the LLM to synthesise the six advisory agents into one verdict.

    This is the original compiler, reduced to a pure function. The graph's
    compiler node now builds the verdict from deterministic findings and
    folds this in as advisory commentary, so a failure here degrades the
    narrative rather than the whole report -- hence the dict return with an
    `error` key instead of an exception.
    """
    if not analysis_results:
        return {"error": "No advisory analysis was produced."}

    try:
        llm = get_llm()
        analysis_summary = json.dumps(analysis_results, indent=2)
        prompt = COMPILER_PROMPT.format(
            analysis_results=analysis_summary,
            ra_12009_directive=RA_12009_DIRECTIVE,
        )
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
    except Exception as e:  # network, credentials, rate limit
        return {"error": f"Advisory analysis unavailable: {e}"}

    # The model is asked for JSON but does not always send only JSON.
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    content = content.strip()
    if not content.startswith("{"):
        start_idx = content.find("{")
        if start_idx != -1:
            content = content[start_idx:]
    if not content.endswith("}"):
        end_idx = content.rfind("}")
        if end_idx != -1:
            content = content[: end_idx + 1]

    try:
        verdict = json.loads(content)
    except json.JSONDecodeError as e:
        return {"error": f"Advisory verdict was not valid JSON: {e}"}

    if not isinstance(verdict, dict) or "findings" not in verdict:
        return {"error": "Advisory verdict had an unexpected shape."}
    return verdict


def gamma_generator_node(state: AgentState) -> Dict[str, Any]:
    """
    Generate Gamma presentation from the compiled report (conditional node).
    """
    if not state.get("generate_gamma", False):
        return {}

    # Emit active log first
    logs = [
        create_thinking_log("Gamma Generator", "Generating presentation...", "active")
    ]

    try:
        # Run async function in sync context for LangGraph compatibility
        import asyncio

        # Use asyncio.run() to execute async function in synchronous context
        gamma_link = asyncio.run(
            gamma_client.generate_presentation(
                content=state["compiled_report"], thread_id=state["thread_id"]
            )
        )

        logs.append(
            create_thinking_log(
                "Gamma Generator", f"Presentation ready: {gamma_link}", "complete"
            )
        )

        return {"gamma_link": gamma_link, "thinking_logs": logs}

    except Exception as e:
        logs.append(
            create_thinking_log("Gamma Generator", f"Error: {str(e)}", "complete")
        )

        return {"gamma_link": "", "thinking_logs": logs}
