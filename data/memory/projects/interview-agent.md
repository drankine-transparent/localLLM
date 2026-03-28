# Interview Agent

**Status:** Active
**Stack:** n8n + FastAPI

## What it is
Structured interview tool that conducts and processes interviews via a workflow
automation pipeline. Produces cleaned, tagged transcripts.

## Components
- **Interview Agent** — n8n workflow that conducts the interview
- **Interview Cleanup Skill** — Claude skill that adds metadata to raw transcripts
  (tags, topics, people, action items)

## Key people
- Darren — architecture
- Oliver Amidei — AMS team lead, metadata/MCP alignment

## Active work
- Interview Cleanup Skill: metadata tags need to align with MCP server extraction schema
  before rolling out broadly
