---
name: host-initialization-by-default
description: Automates host environment setup for software projects, from requirement analysis to code generation and testing. Use this skill whenever starting a new project, setting up a development environment, or when the user mentions host initialization, environment setup, generating code from requirements, or testing generated code. The skill leverages Python agents for efficient, structured outputs and integrates with MCP for tooling.
---

# Host Initialization by Default

This skill helps you quickly establish a productive development environment for any software project. It focuses on understanding requirements, generating structured code through specialized Python agents, verifying correctness with automated tests, and leveraging MCP integrations for efficiency.

## When to Use This Skill

Invoke this skill whenever a user needs to:
- Set up a new project or repository from scratch
- Analyze and document software requirements
- Generate boilerplate or structured code based on specifications
- Run tests on newly generated code
- Integrate with MCP servers or tools

The skill emphasizes using **Python agents**—short-lived, deterministic subprocesses that produce reliable outputs—over long-running, unbounded tasks. This ensures predictable results and easy debugging.

## Core Principles

1. **Understand Before Coding**  
   Always start by clarifying the environment and requirements. What dependencies, frameworks, or tools are needed? What is the expected output format?

2. **Use Python Agents for Deterministic Work**  
   For tasks like parsing requirements, generating code from templates, or running tests, spawn small Python scripts. These agents should be self-contained, accept clear inputs, and produce structured outputs (JSON, YAML, or plain text).

3. **Test Early and Often**  
   Generated code must be tested immediately. Include a test runner that validates the output against expected behavior.

4. **Integrate with MCP Efficiently**  
   When using MCP tools, avoid heavy API calls by writing local scripts that parse and extract information directly from the environment or from cached data.

## Workflow

### Phase 1: Environment Discovery

- Ask the user about the project context: language, framework, existing codebase (if any), and desired setup.
- Identify required dependencies (e.g., Python packages, system libraries).
- Determine the directory structure and configuration files needed.

### Phase 2: Requirement Extraction

Instead of manually reading lengthy messages or making expensive API calls, use a Python script to extract requirements from user input or project files.

**Example script: `scripts/extract_requirements.py`**

```python
#!/usr/bin/env python3
import sys
import re
import json

def extract_requirements(text):
    # Simple keyword-based extraction; adapt as needed
    patterns = {
        "language": r"\b(Python|JavaScript|TypeScript|Go|Rust)\b",
        "framework": r"\b(Django|Flask|React|Vue|FastAPI)\b",
        "database": r"\b(PostgreSQL|MySQL|SQLite|MongoDB)\b",
    }
    results = {}
    for key, pattern in patterns.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        results[key] = list(set(matches)) if matches else []
    return results

if __name__ == "__main__":
    input_text = sys.stdin.read()
    reqs = extract_requirements(input_text)
    print(json.dumps(reqs, indent=2))
```

Use this script to quickly parse user descriptions and output a structured JSON of detected requirements.

### Phase 3: Code Generation with Python Agents

For each component identified in the requirements, spawn a Python agent that generates the necessary code files. Agents should:

- Accept a clear specification (e.g., JSON describing endpoints, models, or configuration).
- Output files to a designated directory.
- Log their actions for traceability.

**Template for a code-generating agent:**

```python
# agent_generate_api.py
import argparse
import json
import os
from pathlib import Path

TEMPLATE = '''
from fastapi import FastAPI

app = FastAPI()

{endpoints}
'''

def generate_endpoint_code(endpoint_spec):
    # Convert spec to Python code
    method = endpoint_spec.get("method", "get")
    path = endpoint_spec.get("path", "/")
    return f'''
@app.{method}("{path}")
async def {endpoint_spec["name"]}():
    return {{"message": "Hello"}}
'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, help="Path to JSON spec file")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    with open(args.spec) as f:
        spec = json.load(f)

    endpoints_code = "\n".join(generate_endpoint_code(ep) for ep in spec["endpoints"])
    content = TEMPLATE.format(endpoints=endpoints_code)

    out_path = Path(args.output_dir) / "main.py"
    out_path.write_text(content)
    print(f"Generated {out_path}")

if __name__ == "__main__":
    main()
```

Run agents sequentially or in parallel depending on dependencies.

### Phase 4: Automated Testing

Once code is generated, immediately run tests to verify correctness.

- Use `pytest` for Python projects, or the appropriate test framework for the language.
- Write a small test suite based on the original requirements.

**Example test runner script:**

```python
# run_tests.py
import subprocess
import sys

def run_tests(test_dir):
    result = subprocess.run(
        ["pytest", test_dir, "-v", "--tb=short"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(result.returncode)

if __name__ == "__main__":
    run_tests("tests/")
```

### Phase 5: MCP Integration

When the user wants to leverage MCP (Model Context Protocol) tools, prefer local scripts over heavy API calls. For example:

- Instead of calling an MCP server repeatedly to read messages, write a script that fetches data once and caches it locally.
- Use Python's `subprocess` to invoke MCP CLI tools if available.

**Caching MCP data example:**

```python
# cache_mcp_data.py
import json
import subprocess
from pathlib import Path

CACHE_FILE = Path(".mcp_cache.json")

def fetch_data_from_mcp():
    # Call MCP tool once
    result = subprocess.run(
        ["mcp", "tool", "list-messages", "--format", "json"],
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout)

def get_cached_or_fetch():
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    data = fetch_data_from_mcp()
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)
    return data
```

## Bundled Scripts

The skill includes reusable scripts in the `scripts/` directory:

- `extract_requirements.py` – Parses natural language to detect tech stack.
- `agent_generate_api.py` – Example agent for generating FastAPI endpoints.
- `run_tests.py` – Simple test runner.
- `cache_mcp_data.py` – Efficient MCP data handling.

Use them directly or adapt to the specific project.

## Output Structure

After running the workflow, the skill produces:

- A well-organized project directory with generated source files.
- A `tests/` directory containing initial test cases.
- A `requirements.txt` or equivalent dependency manifest.
- A brief summary of what was created and how to proceed.

## Customization

This skill is designed to be extended. If the user needs support for a different language or framework, modify the extraction patterns and code templates accordingly. The agent-based approach remains the same.

## Important Notes

- **Python agents are for deterministic tasks only.** Avoid using them for open-ended exploration; that's better suited for interactive  sessions.
- **Test every generated component.** Even a simple smoke test prevents later debugging headaches.
- **Respect the user's existing environment.** If a virtual environment or specific tool versions are required, detect and use them automatically.

By following this skill, you ensure a smooth, repeatable host initialization process that produces reliable, tested code with minimal manual intervention.

