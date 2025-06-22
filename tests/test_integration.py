# tests/test_integration.py
import unittest
from unittest.mock import patch, MagicMock, call # Add call for checking call order/args
import yaml
import json
import os

from src.workflow import app, AppState
from langchain_core.messages import AIMessage # For mocking LLM responses

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), '..', 'sample_openapi_files')
VALID_SWAGGER_YAML = os.path.join(SAMPLES_DIR, 'valid_swagger.yaml')

class TestWorkflowIntegration(unittest.TestCase):

    @patch('src.workflow.os.getenv') # Mock API key globally for all LLM nodes
    @patch('src.workflow.swagger_to_openapi.convert_from_dict') # Mock converter
    @patch('src.workflow.subprocess.run') # Mock linter
    @patch('src.workflow.ChatOpenAI') # Mock LLM
    def test_successful_end_to_end_run(self, MockChatOpenAI, mock_subprocess_run, mock_convert_from_dict, mock_os_getenv):
        # --- Setup Mocks ---
        mock_os_getenv.return_value = "fake_integration_api_key" # Provide dummy API key

        # Mock for swagger_to_openapi.convert_from_dict
        converted_spec_dict = {"openapi": "3.1.0", "info": {"title": "Mock Converted Spec"}}
        mock_convert_from_dict.return_value = converted_spec_dict

        # Mock for subprocess.run (Redocly Linter) - simulate no issues
        mock_linter_process_no_issues = MagicMock()
        mock_linter_process_no_issues.returncode = 0
        mock_linter_process_no_issues.stdout = '{"total": 0}'
        mock_linter_process_no_issues.stderr = ""
        mock_subprocess_run.return_value = mock_linter_process_no_issues

        # Mock for ChatOpenAI (used by correction, best_practices, impact_analysis)
        mock_llm_instance = MockChatOpenAI.return_value

        # Define responses for each LLM call based on node or prompt content
        # For simplicity here, we'll have it respond based on call order or a more sophisticated side_effect.
        # IterativeCorrection (if called, assume no issues, so it might not be called if linter passes first time)
        mock_corrected_spec_yaml = yaml.dump({"openapi": "3.1.0", "info": {"title": "Mock Corrected Spec (No real change)"}})

        # BestPractices
        mock_best_practices_spec_dict = {"openapi": "3.1.0", "info": {"title": "Mock Best Practices Spec"}, "components": {"schemas": {"TestSchema": {"type": "string"}}}}
        mock_best_practices_spec_yaml = yaml.dump(mock_best_practices_spec_dict)

        # ImpactAnalysis
        mock_impact_log_list = [{"tipo": "mock_change", "descricao": "Mocked change detected", "acao_sugerida": "Review mock setup."}]
        mock_impact_log_json = json.dumps(mock_impact_log_list)

        # Use a side_effect to return different values for different LLM calls
        # This is naive; a better way would be to inspect the prompt in the mock if prompts are distinct enough.
        # For now, assuming order: corrector (if lint fails), best_practices, impact_analysis
        # If linter has no issues, corrector is skipped.
        # So, first LLM call will be best_practices, second impact_analysis.

        llm_responses = [
            AIMessage(content=mock_best_practices_spec_yaml), # For BestPracticesNode
            AIMessage(content=mock_impact_log_json)           # For ImpactAnalysisNode
        ]
        # If iterative_correction_node were to be called, its response would need to be added here too.
        # Since linter is mocked to return no issues, corrector won't run.

        mock_llm_instance.invoke.side_effect = llm_responses


        # --- Prepare Initial State ---
        initial_state: AppState = {
            "original_swagger_file_path": VALID_SWAGGER_YAML,
            "swagger_content": None, "openapi_content": None, "current_openapi_spec": None,
            "linter_issues": [], "impact_log": [], "final_openapi_spec": None,
            "current_iteration": 0, "max_iterations": 3,
            "error_message": None, "verbose": False # Keep verbose False for cleaner test output
        }

        # --- Invoke Workflow ---
        final_state = app.invoke(initial_state)

        # --- Assertions ---
        self.assertIsNone(final_state.get("error_message"),
                          f"Workflow returned an error: {final_state.get('error_message')}")

        # Check converter mock
        mock_convert_from_dict.assert_called() # Should have been called

        # Check linter mock
        mock_subprocess_run.assert_called() # Linter should have been called

        # Check LLM mocks (ChatOpenAI should be instantiated, invoke called twice)
        MockChatOpenAI.assert_called() # Ensure an LLM instance was created
        self.assertEqual(mock_llm_instance.invoke.call_count, 2) # BestPractices + ImpactAnalysis

        # Check final outputs
        self.assertEqual(final_state.get("final_openapi_spec"), mock_best_practices_spec_dict)
        self.assertEqual(final_state.get("impact_log"), mock_impact_log_list)

        # Verify that the original swagger was loaded (indirectly, by checking no error from reader)
        self.assertIsNotNone(final_state.get("swagger_content"))


    @patch('src.workflow.os.getenv')
    @patch('src.workflow.swagger_to_openapi.convert_from_dict')
    @patch('src.workflow.subprocess.run')
    @patch('src.workflow.ChatOpenAI')
    def test_workflow_with_one_correction_loop(self, MockChatOpenAI, mock_subprocess_run, mock_convert_from_dict, mock_os_getenv):
        mock_os_getenv.return_value = "fake_integration_api_key"

        converted_spec_dict = {"openapi": "3.1.0", "info": {"title": "Mock Converted Spec for Loop Test"}}
        mock_convert_from_dict.return_value = converted_spec_dict

        # Linter: First call returns issues, second call no issues
        mock_linter_issues = [{"ruleId": "loop-test-rule", "message": "Needs correction."}]
        mock_linter_process_with_issues = MagicMock(returncode=1, stdout=json.dumps(mock_linter_issues), stderr="")
        mock_linter_process_no_issues = MagicMock(returncode=0, stdout='{"total": 0}', stderr="")
        mock_subprocess_run.side_effect = [mock_linter_process_with_issues, mock_linter_process_no_issues]

        # LLM Responses: Corrector, BestPractices, ImpactAnalysis
        mock_llm_instance = MockChatOpenAI.return_value

        corrected_by_llm_dict = {"openapi": "3.1.0", "info": {"title": "Corrected by LLM in Loop Test"}}
        corrected_by_llm_yaml = yaml.dump(corrected_by_llm_dict)

        best_practices_dict = {"openapi": "3.1.0", "info": {"title": "Best Practices after Loop"}}
        best_practices_yaml = yaml.dump(best_practices_dict)

        impact_log_list_loop = [{"tipo": "loop_test_change", "descricao": "Change after loop", "acao_sugerida": "Verify."}]
        impact_log_json_loop = json.dumps(impact_log_list_loop)

        llm_responses_loop = [
            AIMessage(content=corrected_by_llm_yaml),    # For IterativeCorrectionNode
            AIMessage(content=best_practices_yaml),      # For BestPracticesNode
            AIMessage(content=impact_log_json_loop)      # For ImpactAnalysisNode
        ]
        mock_llm_instance.invoke.side_effect = llm_responses_loop

        initial_state: AppState = {
            "original_swagger_file_path": VALID_SWAGGER_YAML,
            "swagger_content": None, "openapi_content": None, "current_openapi_spec": None,
            "linter_issues": [], "impact_log": [], "final_openapi_spec": None,
            "current_iteration": 0, "max_iterations": 3,
            "error_message": None, "verbose": False
        }

        final_state = app.invoke(initial_state)

        self.assertIsNone(final_state.get("error_message"),
                          f"Workflow (loop test) returned an error: {final_state.get('error_message')}")

        self.assertEqual(mock_subprocess_run.call_count, 2) # Linter called twice
        self.assertEqual(mock_llm_instance.invoke.call_count, 3) # Corrector, BestPractices, ImpactAnalysis

        self.assertEqual(final_state.get("final_openapi_spec"), best_practices_dict)
        self.assertEqual(final_state.get("impact_log"), impact_log_list_loop)
        self.assertEqual(final_state.get("current_iteration"), 1) # Iteration counter for corrector

if __name__ == '__main__':
    unittest.main()
