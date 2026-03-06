"""API routes for visual workflow management."""

import logging
from copy import deepcopy

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from llm_forge.ui.workflow_policy import (
    format_governance_error,
    validate_workflow_nodes,
)
from llm_forge.ui.workflow_store import WorkflowStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])

_store = WorkflowStore()

_TEMPLATES: dict[str, dict] = {
    "banking_agentoffice": {
        "name": "Banking AgentOffice",
        "description": (
            "Loan workflow with Intake, KYC/AML, Risk Scoring, "
            "Decision and Compliance review"
        ),
        "nodes": [
            {
                "id": "data_intake",
                "type": "dataSource",
                "position": {"x": 80, "y": 280},
                "data": {
                    "label": "Loan Applications",
                    "config": {
                        "path": "data/banking/loan_applications.csv",
                        "format": "csv",
                    },
                    "status": "idle",
                },
            },
            {
                "id": "agent_intake",
                "type": "agent",
                "position": {"x": 320, "y": 140},
                "data": {
                    "label": "Intake Agent",
                    "config": {
                        "framework": "forge-react",
                        "agent_role": "intake",
                        "risk_level": "low",
                        "requires_approval": False,
                    },
                    "status": "idle",
                },
            },
            {
                "id": "agent_kyc",
                "type": "agent",
                "position": {"x": 320, "y": 310},
                "data": {
                    "label": "KYC AML Agent",
                    "config": {
                        "framework": "forge-react",
                        "agent_role": "kyc_aml",
                        "risk_level": "high",
                        "requires_approval": True,
                    },
                    "status": "idle",
                },
            },
            {
                "id": "agent_risk",
                "type": "agent",
                "position": {"x": 560, "y": 225},
                "data": {
                    "label": "Risk Scoring Agent",
                    "config": {
                        "framework": "forge-react",
                        "agent_role": "risk_scoring",
                        "risk_level": "high",
                        "requires_approval": True,
                    },
                    "status": "idle",
                },
            },
            {
                "id": "router_decision",
                "type": "router",
                "position": {"x": 810, "y": 225},
                "data": {
                    "label": "Decision Router",
                    "config": {
                        "strategy": "llm_classifier",
                        "agent_role": "decision",
                        "risk_level": "critical",
                        "requires_approval": True,
                    },
                    "status": "idle",
                },
            },
            {
                "id": "agent_decision",
                "type": "agent",
                "position": {"x": 1050, "y": 140},
                "data": {
                    "label": "Credit Decision Agent",
                    "config": {
                        "framework": "forge-react",
                        "agent_role": "decision",
                        "risk_level": "critical",
                        "requires_approval": True,
                    },
                    "status": "idle",
                },
            },
            {
                "id": "a2a_compliance",
                "type": "a2a",
                "position": {"x": 1050, "y": 320},
                "data": {
                    "label": "Compliance Review",
                    "config": {
                        "protocol": "a2a",
                        "delegation_mode": "request_response",
                        "agent_role": "compliance",
                        "risk_level": "critical",
                        "requires_approval": True,
                    },
                    "status": "idle",
                },
            },
            {
                "id": "gateway_public",
                "type": "gateway",
                "position": {"x": 1290, "y": 225},
                "data": {
                    "label": "Bank API Gateway",
                    "config": {
                        "protocols": "REST,GraphQL",
                        "auth_method": "oauth2",
                        "rate_limit": 60,
                        "agent_role": "support",
                        "risk_level": "medium",
                        "requires_approval": False,
                    },
                    "status": "idle",
                },
            },
        ],
        "edges": [
            {"id": "e_data_intake", "source": "data_intake", "target": "agent_intake"},
            {"id": "e_data_kyc", "source": "data_intake", "target": "agent_kyc"},
            {"id": "e_intake_risk", "source": "agent_intake", "target": "agent_risk"},
            {"id": "e_kyc_risk", "source": "agent_kyc", "target": "agent_risk"},
            {"id": "e_risk_router", "source": "agent_risk", "target": "router_decision"},
            {"id": "e_router_decision", "source": "router_decision", "target": "agent_decision"},
            {"id": "e_router_compliance", "source": "router_decision", "target": "a2a_compliance"},
            {"id": "e_decision_gateway", "source": "agent_decision", "target": "gateway_public"},
            {"id": "e_compliance_gateway", "source": "a2a_compliance", "target": "gateway_public"},
        ],
    }
}


class SaveWorkflowRequest(BaseModel):
    name: str
    nodes: list[dict]
    edges: list[dict]
    workflow_id: str | None = None


class CreateFromTemplateRequest(BaseModel):
    name: str | None = None


@router.get("")
async def list_workflows() -> list[dict]:
    """List all saved workflows."""
    return _store.list_all()


@router.post("")
async def save_workflow(req: SaveWorkflowRequest) -> dict:
    """Save or update a workflow."""
    return _store.save(
        name=req.name,
        nodes=req.nodes,
        edges=req.edges,
        workflow_id=req.workflow_id,
    )


@router.get("/templates")
async def list_workflow_templates() -> list[dict]:
    """List built-in workflow templates."""
    items: list[dict] = []
    for template_id, template in _TEMPLATES.items():
        items.append(
            {
                "id": template_id,
                "name": template["name"],
                "description": template.get("description", ""),
                "node_count": len(template.get("nodes", [])),
                "edge_count": len(template.get("edges", [])),
            }
        )
    return items


@router.post("/templates/{template_id}/create")
async def create_workflow_from_template(
    template_id: str,
    req: CreateFromTemplateRequest,
) -> dict:
    """Create and persist a workflow from a built-in template."""
    template = _TEMPLATES.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return _store.save(
        name=req.name or template["name"],
        nodes=deepcopy(template["nodes"]),
        edges=deepcopy(template["edges"]),
    )


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str) -> dict:
    """Get a single workflow by ID."""
    wf = _store.get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str) -> dict:
    """Delete a workflow."""
    if _store.delete(workflow_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Workflow not found")


@router.post("/{workflow_id}/run")
async def run_workflow(workflow_id: str) -> dict:
    """Convert workflow to pipeline config and mark as run.

    Returns the pipeline config (actual execution is handled by the caller).
    """
    workflow = _store.get(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    violations = validate_workflow_nodes(workflow.get("nodes", []))
    if violations:
        raise HTTPException(
            status_code=400,
            detail=format_governance_error(violations),
        )

    config = _store.to_pipeline_config(workflow_id)
    if not config:
        raise HTTPException(status_code=404, detail="Workflow not found")
    _store.mark_run(workflow_id)
    return {"status": "started", "pipeline_config": config}


@router.get("/{workflow_id}/config")
async def get_workflow_config(workflow_id: str) -> dict:
    """Get the pipeline config for a workflow without running it."""
    config = _store.to_pipeline_config(workflow_id)
    if not config:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return config
