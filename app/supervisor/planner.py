import json
from typing import Dict, Any, List
from app.agents.llm import LLMService
from app.logging_config import logger
from app.supervisor.agent_registry import AgentRegistry
from app.supervisor.tool_registry import ToolRegistry
from app.supervisor.tool_planner import ToolPlanner
from app.supervisor.planner_cache import PlannerCache

class Planner:
    """Invokes Planning LLM to compile strict execution plans detailing required agents and tools, with Redis caching."""

    @classmethod
    def plan(cls, query: str, classification: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Formulates execution plan. Checks Redis cache for normalized query hits first."""
        # 1. Attempt cache retrieval via PlannerCache
        cached_plan = PlannerCache.get_cached_plan(query)
        if cached_plan:
            return cached_plan

        logger.info(f"Compiling new execution plan for classification '{classification}'...")

        # 2. Query Agent Registry dynamically
        agents_list = AgentRegistry.list_agents()
        agents_desc = "\n".join([
            f"- {a['name']}: {a['description']} (Capabilities: {a['capabilities']})" 
            for a in agents_list
        ])

        # 3. Query Tool Registry dynamically
        tools_list = ToolRegistry.list_tools()
        tools_desc = "\n".join([
            f"- {t['name']}: {t['description']}" 
            for t in tools_list
        ])

        system_prompt = (
            "You are the Lead Multi-Agent Orchestrator and Planner for AquaMind AI.\n"
            "Generate a strict, structured execution plan in JSON format based on the query classification and parsed entities.\n\n"
            f"Available Registered Agents:\n{agents_desc}\n\n"
            f"Available Registered Tools:\n{tools_desc}\n\n"
            "Output MUST be raw JSON matching this schema exactly:\n"
            "{\n"
            "  \"intent\": \"intent_category_name\",\n"
            "  \"reasoning\": [\n"
            "    \"Reason why agent1 was selected.\",\n"
            "    \"Reason why tool1 was selected.\"\n"
            "  ],\n"
            "  \"language\": \"English_or_Tamil_or_Mixed\",\n"
            "  \"entities\": {\"location\": \"Name\", \"year\": \"Range_or_None\"},\n"
            "  \"agents\": [\"AgentName1\", \"AgentName2\"],\n"
            "  \"tools\": [\"ToolName1\", \"ToolName2\"],\n"
            "  \"response_type\": \"chart_or_map_or_table_or_text\",\n"
            "  \"confidence\": 0.95\n"
            "}\n"
            "Requirements for 'reasoning': It must be a list of clear, human-readable strings explaining WHY each agent and tool is selected.\n"
            "Do not include comments or markdown fences outside the JSON blocks. Output MUST be valid JSON only."
        )

        user_content = (
            f"Query: {query}\n"
            f"Classification: {classification}\n"
            f"Extracted Entities: {json.dumps(entities)}"
        )

        try:
            # Invoke LLM in JSON mode
            plan_data = LLMService.call_json(user_content, system_prompt=system_prompt)
            
            # Post-process validation (ensure scheduled agents are valid)
            valid_agents = {a["name"] for a in agents_list}
            plan_data["agents"] = [a for a in plan_data.get("agents", []) if a in valid_agents]
            
            if not plan_data["agents"]:
                # Default safety fallback
                plan_data["agents"] = ["GeneralAgent"]
                
            # Filter and validate tools using ToolPlanner
            plan_data["tools"] = ToolPlanner.plan_tools(
                plan_data.get("tools", []), 
                plan_data.get("intent", classification)
            )
            
            # Ensure reasoning exists
            if "reasoning" not in plan_data or not isinstance(plan_data["reasoning"], list):
                plan_data["reasoning"] = [
                    f"Selected agents: {', '.join(plan_data['agents'])}",
                    f"Selected tools: {', '.join(plan_data['tools']) if plan_data['tools'] else 'None'}"
                ]
                
            # Cache the compiled plan via PlannerCache
            PlannerCache.set_cached_plan(query, plan_data)
            return plan_data
        except Exception as e:
            logger.error(f"Failed to generate execution plan: {e}", exc_info=True)
            # Safe default fallback plan
            return {
                "intent": classification.lower(),
                "reasoning": [f"Fallback activated due to planner error: {str(e)}"],
                "language": "English",
                "entities": entities,
                "agents": ["GeneralAgent"],
                "tools": [],
                "response_type": "text",
                "confidence": 0.50
            }

