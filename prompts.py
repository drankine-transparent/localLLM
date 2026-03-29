"""LLM prompt templates for task extraction, memory decode, and search."""

# Max chars to send to the LLM — ~3000 tokens for prompt + ~9000 tokens for text
MAX_INPUT_CHARS = 12000

def truncate(text: str, max_chars: int = MAX_INPUT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"

TASK_EXTRACTION = """Extract tasks from this meeting transcript as a JSON array.

STEP 1 — Find the meeting name and date from the transcript header or content.
Format the tag as: `Meeting Name · YYYY-MM-DD`

STEP 2 — For each task, decide who owns it:
- Darren / Dee / Darren Rankine owns it → section = "active"
- Anyone else owns it → section = "waiting", AND the title MUST start with "FirstName: "

Examples of section assignment:
  "I'll fix the bug" (Darren speaking) → active, title has no prefix
  "Will said he'd create the ticket" → waiting, title = "Will: Create the ticket"
  "Oliver will investigate Neo4j" → waiting, title = "Oliver: Investigate Neo4j"
  "Rae to send the deck" → waiting, title = "Rae: Send the deck"

STEP 3 — Write the context field:
  1-2 sentences describing what needs to be done and why.
  Always end with the meeting tag: `Meeting Name · YYYY-MM-DD`

Output ONLY a JSON array with keys: title, context, section. No markdown. No wrapper object.

Example output:
[
  {{"title":"Fix output URL handling for interviews","context":"The interview output URL is broken and needs to be resolved before the next demo. `Interview Agent Sync · 2026-03-27`","section":"active"}},
  {{"title":"Will: Create ticket for URL switching","context":"Will volunteered to file the ticket to track the URL switching feature work. `Interview Agent Sync · 2026-03-27`","section":"waiting"}},
  {{"title":"Oliver: Investigate Firestore vs Neo4j for relational data","context":"Darren asked Oliver to assess whether Firestore can handle relational/ontology-based data or if Neo4j is needed. `Interview Agent Sync · 2026-03-27`","section":"waiting"}}
]

/no_think

Transcript:
{text}"""

MEMORY_DECODE = """Expand all shorthand, acronyms, and nicknames using this glossary:
{glossary}

Text to decode:
{text}"""

MEMORY_SEARCH = """Find relevant info for the query using this knowledge base. Cite [file: path].

{knowledge_base}

Query: {query}"""

CHAT_SYSTEM = """Helpful workplace assistant. Context:
{context}

Be concise."""

MEMORY_SUGGEST = """Review this meeting transcript and identify information worth adding to a workplace memory system.

What's already in memory:
{claude_md}

Find ONLY new information not already listed above:
1. People mentioned who aren't in the People table
2. New acronyms, terms, or project names not in the glossary
3. Key facts, decisions, or context worth remembering

Return ONLY a JSON array (max 6 items, empty array if nothing new):
[{{"type":"person","label":"name","detail":"role or context"}},{{"type":"term","label":"ACRONYM","detail":"what it means and when used"}},{{"type":"fact","label":"topic","detail":"key fact worth remembering"}}]

No markdown. No explanation.

/no_think

Transcript:
{text}"""

MEMORY_LEARN = """You manage a workplace memory system. Save new information to the right file.

Information to save:
{text}

Current memory files:
[profile.md]
{claude_md}

[glossary.md]
{glossary_md}

Rules:
- New acronym or term → add a row to glossary.md in the matching table (Acronyms, Internal Terms, Nicknames, or Project Codenames)
- New person info → create people/firstname-lastname.md with a short profile
- New project info → create projects/project-name.md with details
- Preference or fact about Darren → add to profile.md in the right section
- Preserve ALL existing content; only append the new information
- Keep additions concise (1-4 lines)

Return ONLY a JSON object — no markdown, no explanation:
{{"file": "relative/path.md", "content": "...complete updated file content..."}}

/no_think"""
