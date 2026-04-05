# MCP server for ARIA.
# This makes ARIA accessible to AI assistants (Claude Desktop, etc.)
# through the Model Context Protocol standard.
# Reference: https://modelcontextprotocol.io

import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from src.ingestion.loader import load_qc_data, get_summary
from src.qc.rules import evaluate_qc_dataframe
from src.causal.engine import run_causal_analysis

# Load data once
_df = None
_qc_result = None
_causal = None


def _get_df():
    global _df
    if _df is None:
        _df = load_qc_data()
    return _df


def _get_qc():
    global _qc_result
    if _qc_result is None:
        _qc_result = evaluate_qc_dataframe(_get_df())
    return _qc_result


def _get_causal():
    global _causal
    if _causal is None:
        _causal = run_causal_analysis(_get_df().head(500))
    return _causal


# Create MCP server
server = Server("aria-lab-server")


@server.list_resources()
async def list_resources() -> list[types.Resource]:
    """List data resources available through ARIA."""
    return [
        types.Resource(
            uri="lab://qc-status",
            name="QC Status",
            description="Current Westgard QC status for all instruments and tests",
            mimeType="application/json",
        ),
        types.Resource(
            uri="lab://causal-model",
            name="Causal Model",
            description="Root cause analysis: which variables cause QC failures",
            mimeType="application/json",
        ),
        types.Resource(
            uri="lab://summary",
            name="Dataset Summary",
            description="Overview of the lab dataset (instruments, tests, date range)",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read a specific data resource."""
    if uri == "lab://qc-status":
        qc = _get_qc()
        return json.dumps(qc.to_dict(orient="records"), indent=2)
    elif uri == "lab://causal-model":
        causal = _get_causal()
        return json.dumps(causal, indent=2)
    elif uri == "lab://summary":
        summary = get_summary(_get_df())
        return json.dumps(summary, indent=2)
    else:
        raise ValueError(f"Unknown resource: {uri}")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List tools that AI assistants can use through ARIA."""
    return [
        types.Tool(
            name="get_qc_failures",
            description="Get all current QC failures. Returns instrument, test, and Westgard rule violated.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="get_root_cause",
            description="Get the root cause of QC failures. Returns which variable (temperature, lot, calibration) has the biggest causal effect.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="get_instrument_status",
            description="Get QC status for a specific instrument.",
            inputSchema={
                "type": "object",
                "properties": {
                    "instrument_id": {
                        "type": "string",
                        "description": "Instrument ID, e.g. COBAS-C311-01"
                    }
                },
                "required": ["instrument_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Execute a tool when called by an AI assistant."""
    if name == "get_qc_failures":
        qc = _get_qc()
        failures = qc[qc["status"] == "FAIL"]
        result = failures[["instrument_id", "test_name", "qc_level", "rejection_rules", "latest_z"]].to_dict(orient="records")
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_root_cause":
        causal = _get_causal()
        return [types.TextContent(
            type="text",
            text=f"Top root cause of QC failures: {causal['top_cause']}\n"
                 f"Failure rate: {causal['failure_rate'] * 100:.1f}%\n"
                 f"Causal effect sizes: {json.dumps(causal['ates'], indent=2)}"
        )]

    elif name == "get_instrument_status":
        instrument_id = arguments.get("instrument_id", "")
        df = _get_df()
        filtered = df[df["instrument_id"] == instrument_id]
        if filtered.empty:
            return [types.TextContent(type="text", text=f"Instrument {instrument_id} not found.")]
        qc = evaluate_qc_dataframe(filtered)
        result = qc[["test_name", "qc_level", "status", "latest_z"]].to_dict(orient="records")
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
