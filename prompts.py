"""LLM prompt templates for task extraction, memory decode, and search."""

# Max chars to send to the LLM per chunk — ~2000 tokens of text + ~400 token template overhead
# Fits comfortably in a 4096-token context window; was 12000 which required 8192+ context
MAX_INPUT_CHARS = 8000

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



def build_extraction_prompt(text: str, provider: str = "lmstudio") -> str:
    """Format the extraction prompt, stripping /no_think for non-local providers."""
    prompt = TASK_EXTRACTION.format(text=text)
    if provider != "lmstudio":
        prompt = prompt.replace("\n\n/no_think\n\n", "\n\n")
    return prompt


CHAT_SYSTEM = """Helpful workplace assistant. Context:
{context}

Be concise."""

MEMORY_SUGGEST = """Review this meeting transcript and identify information worth adding to a workplace memory system.

What's already in memory:
{claude_md}

Find ONLY new information not already listed above (max 10 items, empty array if nothing new):
1. People mentioned who aren't already known — type: person, dest: people/first-last.md
2. New acronyms, terms, or shorthand not in the glossary — type: term, dest: glossary.md
3. Active projects, clients, or initiatives worth tracking — type: project, dest: projects/project-name.md
4. Key facts, preferences, or context about Dee/Darren — type: fact, dest: profile.md

Return ONLY a JSON array:
[
  {{"type":"person","label":"Full Name","detail":"role or context","dest":"people/first-last.md"}},
  {{"type":"term","label":"ACRONYM","detail":"what it means and when used","dest":"glossary.md"}},
  {{"type":"project","label":"Project Name","detail":"what it is and current status","dest":"projects/project-name.md"}},
  {{"type":"fact","label":"topic","detail":"key fact worth remembering","dest":"profile.md"}}
]

No markdown. No explanation.

/no_think

Transcript:
{text}"""

MEMORY_LEARN = """You manage a workplace memory system. Decide where to save new information and what to write.

Information to save:
{text}

Current memory files:
[profile.md]
{claude_md}

[glossary.md]
{glossary_md}

Rules:
- New acronym or term → file: glossary.md, append: a markdown table row "| Term | Meaning | Context |"
- New person info → file: people/firstname-lastname.md, append: a short markdown profile (name, role, context)
- New project info → file: projects/project-name.md, append: project name, description, status
- Preference or fact about Dee/Darren → file: profile.md, append: "**Fact:** label — detail"
- Keep the append value concise (1-4 lines). Do NOT include existing file content.
- File paths are relative to the memory root. NEVER prefix with "memory/" — correct: "people/brett.md", wrong: "memory/people/brett.md"

Return ONLY a JSON object — no markdown, no explanation:
{{"file": "relative/path.md", "append": "...only the new content to add..."}}

/no_think"""
