# src/main.py
import argparse
import yaml
import json
import sys # For stderr
from .workflow import app, AppState # AppState might be useful for typing initial_state

def main():
    parser = argparse.ArgumentParser(description="Convert Swagger 2.0 to OpenAPI 3.1, apply best practices, and analyze impacts.")
    parser.add_argument("input_file", help="Path to the input Swagger 2.0 file (JSON or YAML).")
    parser.add_argument(
        "-o", "--output-spec",
        help="Path to save the final OpenAPI 3.1 YAML file. If not provided, prints to stdout."
    )
    parser.add_argument(
        "-l", "--impact-log",
        help="Path to save the impact analysis JSON log file. If not provided, prints to stdout."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging throughout the workflow."
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5, # Default from workflow.py's reader_validator_node, making it configurable here
        help="Maximum number of iterations for the linting/correction loop."
    )
    args = parser.parse_args()

    if args.verbose:
        print(f"Starting OpenAPI processing for input file: {args.input_file}")
        print(f"Verbose mode: {args.verbose}")
        print(f"Max correction iterations: {args.max_iterations}")
        if args.output_spec:
            print(f"Final OpenAPI spec will be saved to: {args.output_spec}")
        if args.impact_log:
            print(f"Impact log will be saved to: {args.impact_log}")

    # Prepare the initial state for the LangGraph AppState TypedDict
    initial_state: AppState = {
        "original_swagger_file_path": args.input_file,
        "swagger_content": None,
        "openapi_content": None,
        "current_openapi_spec": None,
        "linter_issues": [],
        "impact_log": [],
        "final_openapi_spec": None,
        "current_iteration": 0, # Will be initialized by reader_validator_node if not set
        "max_iterations": args.max_iterations,
        "error_message": None,
        "verbose": args.verbose
    }

    if args.verbose:
        print("Invoking the agentic workflow...")

    final_state = app.invoke(initial_state)

    if args.verbose:
        print("\n--- Workflow Execution Finished ---")
        # print("Final state snapshot:", {k: type(v) for k,v in final_state.items()}) # Avoid printing large specs

    # Handle error messages from the workflow
    if final_state.get("error_message"):
        print(f"Workflow completed with errors: {final_state['error_message']}", file=sys.stderr)
        # Depending on severity, might exit with non-zero code
        # For now, just print and proceed to output what we have

    # Output the final OpenAPI specification
    final_spec = final_state.get("final_openapi_spec")
    if final_spec:
        if args.output_spec:
            try:
                with open(args.output_spec, 'w', encoding='utf-8') as f:
                    yaml.dump(final_spec, f, sort_keys=False, default_flow_style=False, allow_unicode=True)
                if args.verbose: print(f"Final OpenAPI 3.1 spec saved to: {args.output_spec}")
            except Exception as e:
                print(f"Error saving OpenAPI spec to {args.output_spec}: {e}", file=sys.stderr)
        else:
            print("\n--- Final OpenAPI 3.1 Specification ---")
            yaml.dump(final_spec, sys.stdout, sort_keys=False, default_flow_style=False, allow_unicode=True)
    elif not final_state.get("error_message"): # No spec and no error message might mean something unexpected
        print("Warning: Final OpenAPI specification is not available, and no explicit error was reported.", file=sys.stderr)


    # Output the impact analysis log
    impact_log_data = final_state.get("impact_log")
    if impact_log_data: # Even an empty list is valid, means no impacts found or analysis done
        if args.impact_log:
            try:
                with open(args.impact_log, 'w', encoding='utf-8') as f:
                    json.dump(impact_log_data, f, indent=2, ensure_ascii=False)
                if args.verbose: print(f"Impact analysis log saved to: {args.impact_log}")
            except Exception as e:
                print(f"Error saving impact log to {args.impact_log}: {e}", file=sys.stderr)
        else:
            print("\n--- Impact Analysis Log ---")
            json.dump(impact_log_data, sys.stdout, indent=2, ensure_ascii=False)
            print() # for newline after json output
    elif not final_state.get("error_message"): # No log and no error
        # This could be normal if analysis node decided there's nothing to log
        if args.verbose: print("Impact analysis log is empty or not available (and no explicit error reported).")


    if final_state.get("error_message"):
        print("Please check error messages above for details on issues during processing.", file=sys.stderr)
        # sys.exit(1) # Consider exiting with error code if there were errors

if __name__ == "__main__":
    main()
