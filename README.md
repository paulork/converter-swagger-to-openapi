# Agentic OpenAPI Migrator & Enhancer

## Description

This project implements a multi-agent system using Python, LangGraph, and LangChain to automate the conversion and enhancement of API specifications. It takes a Swagger 2.0 (OpenAPI v2) file, converts it to OpenAPI 3.1, applies linting rules, uses Large Language Models (LLMs) for iterative correction and best practice application, and finally generates an impact analysis log for the changes made.

## Features

-   **Swagger 2.0 to OpenAPI 3.1 Conversion**: Utilizes standard libraries for initial conversion.
-   **Linting**: Integrates with Redocly CLI for validating the OpenAPI specification against common rules.
-   **Iterative Correction**: Employs an LLM to attempt to fix issues reported by the linter.
-   **Best Practices Application**: Uses an LLM to enhance the specification by adding examples, improving descriptions, and other API design best practices.
-   **Impact Analysis**: Leverages an LLM to compare the original and final specifications and generate a log of potentially breaking changes and other significant modifications.
-   **Agentic Workflow**: Orchestrated by LangGraph, allowing for a clear and extensible flow of operations.
-   **Configurable**: Max correction iterations and verbosity can be controlled via CLI arguments.

## Prerequisites

-   Python 3.9+
-   Pip (Python package installer)

## Setup Instructions

1.  **Clone the repository:**
    ```bash
    git clone <your_repository_url_here>
    cd <project_directory_name>
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    ```
    -   On Windows:
        ```bash
        venv\Scripts\activate
        ```
    -   On macOS/Linux:
        ```bash
        source venv/bin/activate
        ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    -   Create a file named `.env` in the root of the project directory.
    -   Add your OpenAI API key to this file:
        ```env
        OPENAI_API_KEY="your_openai_api_key_here"
        ```
    Replace `"your_openai_api_key_here"` with your actual OpenAI API key.

## How to Run

Execute the main script from the project root directory:

**Basic command:**
```bash
python src/main.py path/to/your/swagger_2_0_file.yaml
```

**Example with all options:**
```bash
python src/main.py input_swagger.json -o final_openapi_spec.yaml -l impact_report.json --verbose --max-iterations 7
```

### Command-Line Arguments:

-   `input_file`: (Required) Path to the input Swagger 2.0 file (can be YAML or JSON).
-   `-o, --output-spec <path>`: (Optional) Path to save the final OpenAPI 3.1 YAML file. If not provided, the spec will be printed to standard output.
-   `-l, --impact-log <path>`: (Optional) Path to save the impact analysis JSON log file. If not provided, the log will be printed to standard output.
-   `-v, --verbose`: (Optional) Enable verbose logging to see detailed information about each step of the workflow.
-   `--max-iterations <number>`: (Optional) Set the maximum number of iterations for the linting/correction loop. Default is 5.

## Workflow Overview / Agents

The system uses a sequence of specialized agents orchestrated by LangGraph:

1.  **Reader & Validator Agent**: Loads the input Swagger 2.0 file, parses it, and performs initial validation.
2.  **Conversion Agent**: Converts the Swagger 2.0 content to the OpenAPI 3.1 format using the `swagger-to-openapi` library.
3.  **Linting Agent**: Uses the Redocly CLI to lint the current OpenAPI 3.1 specification and extracts any issues found.
4.  **Iterative Correction Agent**: If linting issues are present, this LLM-based agent attempts to correct the specification. It iterates with the Linting Agent up to a maximum number of attempts.
5.  **Best Practices Agent**: Once the specification is lint-free (or max iterations are reached), this LLM-based agent reviews the spec and applies common API design best practices (e.g., adding examples, improving descriptions).
6.  **Impact Analysis Agent**: Finally, this LLM-based agent compares the original Swagger 2.0 spec with the final, enhanced OpenAPI 3.1 spec to generate a log of changes that might impact API consumers.

## Example Usage

**Input (`input_swagger.yaml`):**
```yaml
swagger: "2.0"
info:
  title: "Minimal Test API"
  version: "v1"
paths:
  /ping:
    get:
      summary: "Health check"
      responses:
        "200":
          description: "API is healthy."
```

**Example Output (Snippets):**

*Final OpenAPI 3.1 Specification (e.g., `final_openapi_spec.yaml`):*
```yaml
openapi: 3.1.0
info:
  title: Minimal Test API (Enhanced by LLM) # Title might be modified by LLM
  version: v1
  description: An enhanced description of this minimal test API. # Added by BestPractices Agent
paths:
  /ping:
    get:
      summary: Health check for the API. # Description might be expanded
      responses:
        '200':
          description: API is healthy and responding correctly.
          content:
            application/json:
              examples:
                example1:
                  value:
                    status: ok
                    timestamp: '2024-01-01T12:00:00Z'
# ... other enhancements and converted structure ...
```

*Impact Analysis Log (e.g., `impact_report.json`):*
```json
[
  {
    "tipo": "significant_improvement",
    "descricao": "The operation GET /ping had its description and response example enhanced for clarity.",
    "acao_sugerida": "Review the enhanced documentation for GET /ping. No breaking changes."
  },
  {
    "tipo": "minor_change",
    "descricao": "The API specification was converted from Swagger 2.0 to OpenAPI 3.1.0.",
    "acao_sugerida": "Ensure client tooling is compatible with OpenAPI 3.1.0."
  }
  // ... other changes if any ...
]
```
*(Note: Actual LLM outputs will vary.)*

## LLM Configuration

-   This project uses OpenAI's GPT models (e.g., `gpt-3.5-turbo` for corrections, `gpt-4o` for best practices and impact analysis, as configured in the code).
-   A valid `OPENAI_API_KEY` must be provided in the `.env` file in the project root for the LLM-based agents to function.

## Testing

To run the automated tests (unit and integration):
```bash
python -m unittest discover tests
```
Ensure you are in the project root directory and your virtual environment is activated. Mocked LLM calls are used during tests, so no actual API calls are made.

## Contributing

Contributions are welcome! Please feel free to fork the repository, make changes, and submit pull requests.

## License

This project is licensed under the MIT License. (Consider adding a LICENSE file if you choose a license).
# aazzz
