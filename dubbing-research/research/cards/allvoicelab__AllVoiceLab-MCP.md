# allvoicelab/AllVoiceLab-MCP

**Verdict:** Model Context Protocol (MCP) server exposing AllVoiceLab TTS and video translation APIs to AI coding agents.

## Pipeline Stages & Models
| Stage | Engine / Model Used |
|---|---|
| MCP Server | Exposes dubbing tools over stdio/HTTP JSON-RPC |

## Bengali Readiness
- **Status:** Unverified.

## Timing & Synchronization Approach
Server-side.

## Lip-Sync Approach
None.

## Strengths Worth Stealing
- Demonstrates how to build an MCP server interface for video dubbing workflows.

## Weaknesses & Critical Risks
- Hardcoded to proprietary AllVoiceLab cloud backend.

## License & Project Health
- **License:** MIT.

## Reuse Recommendation
**Copy ideas (pattern for exposing our local studio to Antigravity / Claude via MCP).**

## Confidence & Verification
- **Confidence:** High.
