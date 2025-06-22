# tests/test_workflow_nodes.py
import unittest
import os
import yaml
import json
from typing import TypedDict, List, Dict, Any
from unittest.mock import patch, MagicMock

# Adjust the import path based on how Python path is configured for tests
# Assuming 'src' is in PYTHONPATH or tests are run from project root
# If running `python -m unittest discover tests` from root, this should work:
from src.workflow import (
    reader_validator_node,
    conversion_node,
    linting_node,
    iterative_correction_node,
    best_practices_node,
    impact_analysis_node,
    AppState
)
from langchain_core.messages import AIMessage # For mocking LLM responses

# Define a path to the sample files directory
SAMPLES_DIR = os.path.join(os.path.dirname(__file__), '..', 'sample_openapi_files')
VALID_SWAGGER_YAML = os.path.join(SAMPLES_DIR, 'valid_swagger.yaml')
VALID_SWAGGER_JSON = os.path.join(SAMPLES_DIR, 'valid_swagger.json')
INVALID_SWAGGER_MISSING_VERSION = os.path.join(SAMPLES_DIR, 'invalid_swagger_missing_version.yaml')
EMPTY_FILE_YAML = os.path.join(SAMPLES_DIR, 'empty_file.yaml')
NOT_YAML_TXT = os.path.join(SAMPLES_DIR, 'not_yaml.txt')
NON_EXISTENT_FILE = os.path.join(SAMPLES_DIR, 'non_existent_file.yaml')


class TestReaderValidatorNode(unittest.TestCase):

    def setUp(self):
        os.makedirs(SAMPLES_DIR, exist_ok=True)
        valid_swagger_dict = {
            "swagger": "2.0",
            "info": {"title": "Simple JSON API", "version": "1.0.1"},
            "paths": {
                "/items_json": {
                    "get": {"summary": "Get JSON items", "responses": {"200": {"description": "A list of JSON items."}}}
                }
            }
        }
        with open(VALID_SWAGGER_JSON, 'w') as f:
            json.dump(valid_swagger_dict, f)

    def tearDown(self):
        if os.path.exists(VALID_SWAGGER_JSON):
            os.remove(VALID_SWAGGER_JSON)

    def _create_initial_state(self, file_path: str) -> AppState:
        return {
            "original_swagger_file_path": file_path,
            "swagger_content": None, "openapi_content": None, "current_openapi_spec": None,
            "linter_issues": [], "impact_log": [], "final_openapi_spec": None,
            "current_iteration": 0, "max_iterations": 5, "error_message": None, "verbose": False
        }

    def test_load_valid_yaml(self):
        state = self._create_initial_state(VALID_SWAGGER_YAML)
        result_state = reader_validator_node(state)
        self.assertIsNone(result_state.get("error_message"),
                          f"Error message was not None: {result_state.get('error_message')}")
        self.assertIsNotNone(result_state.get("swagger_content"))
        self.assertEqual(result_state["swagger_content"]["info"]["title"], "Simple API")

    def test_load_valid_json(self):
        state = self._create_initial_state(VALID_SWAGGER_JSON)
        result_state = reader_validator_node(state)
        self.assertIsNone(result_state.get("error_message"),
                          f"Error message was not None: {result_state.get('error_message')}")
        self.assertIsNotNone(result_state.get("swagger_content"))
        self.assertEqual(result_state["swagger_content"]["info"]["title"], "Simple JSON API")

    def test_file_not_found(self):
        state = self._create_initial_state(NON_EXISTENT_FILE)
        result_state = reader_validator_node(state)
        self.assertIsNotNone(result_state.get("error_message"))
        self.assertIn("Input file not found", result_state["error_message"])
        self.assertIsNone(result_state.get("swagger_content"))

    def test_invalid_yaml_or_json_content(self):
        state = self._create_initial_state(NOT_YAML_TXT)
        result_state = reader_validator_node(state)
        self.assertIsNotNone(result_state.get("error_message"))
        self.assertIn("Failed to parse file as YAML or JSON", result_state["error_message"])
        self.assertIsNone(result_state.get("swagger_content"))

    def test_empty_file(self):
        state = self._create_initial_state(EMPTY_FILE_YAML)
        result_state = reader_validator_node(state)
        self.assertIsNotNone(result_state.get("error_message"))
        self.assertIn("Parsed content is not a valid dictionary", result_state["error_message"])
        self.assertIsNone(result_state.get("swagger_content"))

    def test_missing_swagger_version_field(self):
        state = self._create_initial_state(INVALID_SWAGGER_MISSING_VERSION)
        result_state = reader_validator_node(state)
        self.assertIsNotNone(result_state.get("error_message"))
        self.assertIn("'swagger' field must be '2.0'", result_state["error_message"])
        self.assertIsNotNone(result_state.get("swagger_content"))
        self.assertEqual(result_state["swagger_content"]["info"]["title"], "Invalid API")

    def test_missing_info_field(self):
        invalid_spec = {"swagger": "2.0", "paths": {}}
        os.makedirs(SAMPLES_DIR, exist_ok=True)
        temp_file = os.path.join(SAMPLES_DIR, "temp_missing_info.yaml")
        with open(temp_file, 'w') as f: yaml.dump(invalid_spec, f)
        state = self._create_initial_state(temp_file)
        result_state = reader_validator_node(state)
        os.remove(temp_file)
        self.assertIsNotNone(result_state.get("error_message"))
        self.assertIn("'info' field must be an object", result_state["error_message"])

    def test_missing_paths_field(self):
        invalid_spec = {"swagger": "2.0", "info": {"title": "API", "version":"1.0"}}
        os.makedirs(SAMPLES_DIR, exist_ok=True)
        temp_file = os.path.join(SAMPLES_DIR, "temp_missing_paths.yaml")
        with open(temp_file, 'w') as f: yaml.dump(invalid_spec, f)
        state = self._create_initial_state(temp_file)
        result_state = reader_validator_node(state)
        os.remove(temp_file)
        self.assertIsNotNone(result_state.get("error_message"))
        self.assertIn("'paths' field must be an object", result_state["error_message"])

class TestConversionNode(unittest.TestCase):
    def _create_initial_state(self, swagger_content=None, existing_error=None) -> AppState:
        return {"original_swagger_file_path": "dummy.yaml", "swagger_content": swagger_content,
            "openapi_content": None, "current_openapi_spec": None, "linter_issues": [],
            "impact_log": [], "final_openapi_spec": None, "current_iteration": 0,
            "max_iterations": 5, "error_message": existing_error, "verbose": False}

    @patch('src.workflow.swagger_to_openapi.convert_from_dict')
    def test_successful_conversion(self, mock_convert):
        mocked_output = {"openapi": "3.1.0", "info": {"title": "Converted"}}
        mock_convert.return_value = mocked_output
        state = self._create_initial_state(swagger_content={"swagger": "2.0"})
        result = conversion_node(state)
        mock_convert.assert_called_once_with({"swagger": "2.0"})
        self.assertIsNone(result.get("error_message"))
        self.assertEqual(result.get("openapi_content"), mocked_output)
        self.assertEqual(result.get("current_openapi_spec"), mocked_output)

    @patch('src.workflow.swagger_to_openapi.convert_from_dict')
    def test_conversion_failure_exception(self, mock_convert):
        mock_convert.side_effect = Exception("Lib error")
        state = self._create_initial_state(swagger_content={"swagger": "2.0"})
        result = conversion_node(state)
        self.assertIsNotNone(result.get("error_message"))
        self.assertIn("Failed to convert Swagger to OpenAPI: Lib error", result["error_message"])

    def test_missing_swagger_content(self):
        state = self._create_initial_state(swagger_content=None)
        result = conversion_node(state)
        self.assertIsNotNone(result.get("error_message"))
        self.assertIn("Swagger content is missing or invalid", result["error_message"])

    def test_pre_existing_error_message(self):
        state = self._create_initial_state(swagger_content={"swagger": "2.0"}, existing_error="Prev error")
        result = conversion_node(state)
        self.assertEqual(result.get("error_message"), "Prev error")

class TestLintingNode(unittest.TestCase):
    def _create_initial_state(self, current_spec=None, existing_error=None) -> AppState:
        return {"original_swagger_file_path": "dummy.yaml", "swagger_content": None,
            "openapi_content": None, "current_openapi_spec": current_spec, "linter_issues": [],
            "impact_log": [], "final_openapi_spec": None, "current_iteration": 0,
            "max_iterations": 5, "error_message": existing_error, "verbose": False}

    @patch('src.workflow.subprocess.run')
    @patch('src.workflow.tempfile.NamedTemporaryFile')
    @patch('src.workflow.os.remove')
    def test_linting_successful_no_issues(self, mock_remove, mock_temp_file, mock_run):
        mock_file = MagicMock(); mock_file.name = "temp.yaml"
        mock_temp_file.return_value.__enter__.return_value = mock_file
        mock_proc = MagicMock(); mock_proc.returncode = 0
        mock_proc.stdout = '{"total": 0}'; mock_proc.stderr = ""
        mock_run.return_value = mock_proc
        state = self._create_initial_state(current_spec={"openapi": "3.1.0"})
        result = linting_node(state)
        mock_run.assert_called_once()
        self.assertIsNone(result.get("error_message"), result.get("error_message"))
        self.assertEqual(result.get("linter_issues"), [])
        mock_remove.assert_called_once_with("temp.yaml")

    @patch('src.workflow.subprocess.run')
    @patch('src.workflow.tempfile.NamedTemporaryFile')
    @patch('src.workflow.os.remove')
    def test_linting_successful_with_issues(self, mock_remove, mock_temp_file, mock_run):
        mock_file = MagicMock(); mock_file.name = "temp_issues.yaml"
        mock_temp_file.return_value.__enter__.return_value = mock_file
        issues = [{"ruleId": "test", "message": "issue"}]
        mock_proc = MagicMock(); mock_proc.returncode = 1
        mock_proc.stdout = json.dumps(issues); mock_proc.stderr = ""
        mock_run.return_value = mock_proc
        state = self._create_initial_state(current_spec={"openapi": "3.1.0"})
        result = linting_node(state)
        self.assertIsNone(result.get("error_message"), result.get("error_message"))
        self.assertEqual(result.get("linter_issues"), issues)

    @patch('src.workflow.subprocess.run')
    @patch('src.workflow.tempfile.NamedTemporaryFile')
    @patch('src.workflow.os.remove')
    def test_linter_cli_execution_error(self, mock_remove, mock_temp_file, mock_run):
        mock_file = MagicMock(); mock_file.name = "temp_err.yaml"
        mock_temp_file.return_value.__enter__.return_value = mock_file
        mock_proc = MagicMock(); mock_proc.returncode = 127
        mock_proc.stdout = ""; mock_proc.stderr = "cmd not found"
        mock_run.return_value = mock_proc
        state = self._create_initial_state(current_spec={"openapi": "3.1.0"})
        result = linting_node(state)
        self.assertIsNotNone(result.get("error_message"))
        self.assertIn("Redocly CLI execution failed", result["error_message"])

    # ... (other linting tests from prompt will be added here) ...

# === Tests for IterativeCorrectionNode ===
class TestIterativeCorrectionNode(unittest.TestCase):
    def _create_initial_state(self, current_spec=None, issues=None, err_msg=None, iter_count=0) -> AppState:
        return {
            "original_swagger_file_path": "dummy.yaml", "swagger_content": None,
            "openapi_content": None, "current_openapi_spec": current_spec,
            "linter_issues": issues if issues is not None else [], "impact_log": [],
            "final_openapi_spec": None, "current_iteration": iter_count,
            "max_iterations": 5, "error_message": err_msg, "verbose": False
        }

    @patch('src.workflow.os.getenv')
    @patch('src.workflow.ChatOpenAI')
    def test_successful_correction(self, MockChatOpenAI, mock_getenv):
        mock_getenv.return_value = "fake_api_key"
        mock_llm_instance = MockChatOpenAI.return_value

        corrected_spec_dict = {"openapi": "3.1.0", "info": {"title": "Corrected by LLM"}}
        corrected_spec_yaml = yaml.dump(corrected_spec_dict)
        mock_llm_instance.invoke.return_value = AIMessage(content=corrected_spec_yaml)

        state = self._create_initial_state(current_spec={"openapi": "3.0.0"}, issues=[{"id":"some-issue"}])
        result_state = iterative_correction_node(state)

        self.assertIsNone(result_state.get("error_message"), result_state.get("error_message"))
        self.assertEqual(result_state.get("current_openapi_spec"), corrected_spec_dict)
        self.assertEqual(result_state.get("current_iteration"), 1)
        mock_getenv.assert_called_with("OPENAI_API_KEY")
        MockChatOpenAI.assert_called_once()

    @patch('src.workflow.os.getenv')
    @patch('src.workflow.ChatOpenAI')
    def test_correction_llm_returns_non_yaml(self, MockChatOpenAI, mock_getenv):
        mock_getenv.return_value = "fake_api_key"
        mock_llm_instance = MockChatOpenAI.return_value
        mock_llm_instance.invoke.return_value = AIMessage(content="This is not YAML.")

        original_spec = {"openapi": "3.0.0", "info": {"title": "Original"}}
        state = self._create_initial_state(current_spec=original_spec, issues=[{"id":"some-issue"}])
        result_state = iterative_correction_node(state)

        self.assertIsNotNone(result_state.get("error_message"))
        self.assertIn("LLM output was not a valid OpenAPI YAML structure", result_state["error_message"])
        self.assertEqual(result_state.get("current_openapi_spec"), original_spec)
        self.assertEqual(result_state.get("current_iteration"), 1)

    @patch('src.workflow.os.getenv')
    @patch('src.workflow.ChatOpenAI')
    def test_correction_llm_exception(self, MockChatOpenAI, mock_getenv):
        mock_getenv.return_value = "fake_api_key"
        mock_llm_instance = MockChatOpenAI.return_value
        mock_llm_instance.invoke.side_effect = Exception("LLM API Error")

        original_spec = {"openapi": "3.0.0", "info": {"title": "Original"}}
        state = self._create_initial_state(current_spec=original_spec, issues=[{"id":"some-issue"}])
        result_state = iterative_correction_node(state)

        self.assertIsNotNone(result_state.get("error_message"))
        self.assertIn("Error during LLM-based correction: LLM API Error", result_state["error_message"])
        self.assertEqual(result_state.get("current_openapi_spec"), original_spec)
        self.assertEqual(result_state.get("current_iteration"), 1)

    @patch('src.workflow.os.getenv')
    @patch('src.workflow.ChatOpenAI')
    def test_correction_missing_api_key(self, MockChatOpenAI, mock_getenv):
        mock_getenv.return_value = None
        state = self._create_initial_state(current_spec={"openapi": "3.0.0"}, issues=[{"id":"some-issue"}])
        result_state = iterative_correction_node(state)

        self.assertIsNotNone(result_state.get("error_message"))
        self.assertIn("OPENAI_API_KEY not found", result_state["error_message"])
        MockChatOpenAI.assert_not_called()
        self.assertEqual(result_state.get("current_iteration"), 0)

    def test_correction_no_linter_issues(self):
        state = self._create_initial_state(current_spec={"openapi": "3.0.0"}, issues=[])
        result_state = iterative_correction_node(state)
        self.assertIsNone(result_state.get("error_message"))
        self.assertEqual(result_state.get("current_iteration"), 0)

# === Tests for BestPracticesNode ===
class TestBestPracticesNode(unittest.TestCase):
    def _create_initial_state(self, current_spec=None, err_msg=None) -> AppState:
        return {
            "original_swagger_file_path": "dummy.yaml", "swagger_content": None,
            "openapi_content": None, "current_openapi_spec": current_spec,
            "linter_issues": [], "impact_log": [], "final_openapi_spec": None,
            "current_iteration": 0, "max_iterations": 5,
            "error_message": err_msg, "verbose": False
        }

    @patch('src.workflow.os.getenv')
    @patch('src.workflow.ChatOpenAI')
    def test_successful_best_practices(self, MockChatOpenAI, mock_getenv):
        mock_getenv.return_value = "fake_api_key"
        mock_llm_instance = MockChatOpenAI.return_value

        enhanced_spec_dict = {"openapi": "3.1.0", "info": {"title": "Enhanced by LLM"}}
        enhanced_spec_yaml = yaml.dump(enhanced_spec_dict)
        mock_llm_instance.invoke.return_value = AIMessage(content=enhanced_spec_yaml)

        state = self._create_initial_state(current_spec={"openapi": "3.1.0", "info": {"title": "Linted Spec"}})
        result_state = best_practices_node(state)

        self.assertIsNone(result_state.get("error_message"), result_state.get("error_message"))
        self.assertEqual(result_state.get("final_openapi_spec"), enhanced_spec_dict)

    @patch('src.workflow.os.getenv')
    @patch('src.workflow.ChatOpenAI')
    def test_best_practices_llm_returns_bad_yaml(self, MockChatOpenAI, mock_getenv):
        mock_getenv.return_value = "fake_api_key"
        mock_llm_instance = MockChatOpenAI.return_value
        mock_llm_instance.invoke.return_value = AIMessage(content="Not YAML")

        original_spec = {"openapi": "3.1.0", "info": {"title": "Original"}}
        state = self._create_initial_state(current_spec=original_spec)
        result_state = best_practices_node(state)

        self.assertIsNotNone(result_state.get("error_message"))
        self.assertIn("LLM output for best practices was not a valid OpenAPI YAML structure", result_state["error_message"])
        self.assertEqual(result_state.get("final_openapi_spec"), original_spec)

# === Tests for ImpactAnalysisNode ===
class TestImpactAnalysisNode(unittest.TestCase):
    def _create_initial_state(self, swagger_spec=None, final_spec=None, err_msg=None) -> AppState:
        return {
            "original_swagger_file_path": "dummy.yaml",
            "swagger_content": swagger_spec,
            "openapi_content": None, "current_openapi_spec": None,
            "linter_issues": [], "impact_log": [],
            "final_openapi_spec": final_spec,
            "current_iteration": 0, "max_iterations": 5,
            "error_message": err_msg, "verbose": False
        }

    @patch('src.workflow.os.getenv')
    @patch('src.workflow.ChatOpenAI')
    def test_successful_impact_analysis(self, MockChatOpenAI, mock_getenv):
        mock_getenv.return_value = "fake_api_key"
        mock_llm_instance = MockChatOpenAI.return_value

        impact_log_list = [{"tipo": "breaking_change", "descricao": "Something broke", "acao_sugerida": "Fix it"}]
        impact_log_json_str = json.dumps(impact_log_list)
        mock_llm_instance.invoke.return_value = AIMessage(content=impact_log_json_str)

        state = self._create_initial_state(
            swagger_spec={"swagger":"2.0"},
            final_spec={"openapi":"3.1.0"}
        )
        result_state = impact_analysis_node(state)

        self.assertIsNone(result_state.get("error_message"), result_state.get("error_message"))
        self.assertEqual(result_state.get("impact_log"), impact_log_list)

    @patch('src.workflow.os.getenv')
    @patch('src.workflow.ChatOpenAI')
    def test_impact_analysis_llm_returns_bad_json(self, MockChatOpenAI, mock_getenv):
        mock_getenv.return_value = "fake_api_key"
        mock_llm_instance = MockChatOpenAI.return_value
        mock_llm_instance.invoke.return_value = AIMessage(content="Not JSON")

        state = self._create_initial_state(
            swagger_spec={"swagger":"2.0"},
            final_spec={"openapi":"3.1.0"}
        )
        result_state = impact_analysis_node(state)
        self.assertIsNotNone(result_state.get("error_message"))
        self.assertIn("Failed to parse LLM JSON response for impact analysis", result_state["error_message"])
        self.assertTrue(any(item.get("tipo") == "error" for item in result_state.get("impact_log", [])))

    @patch('src.workflow.os.getenv') # Keep mock_getenv for consistency even if not strictly needed for this path
    @patch('src.workflow.ChatOpenAI')
    def test_impact_analysis_missing_specs(self, MockChatOpenAI, mock_getenv): # Added mock_getenv here
        mock_getenv.return_value = "fake_api_key" # Ensure API key is 'present' for the parts that might run

        state_no_orig = self._create_initial_state(swagger_spec=None, final_spec={"openapi":"3.1.0"})
        res_state_no_orig = impact_analysis_node(state_no_orig)
        self.assertTrue(any(item.get("tipo") == "warning" or item.get("tipo") == "error" for item in res_state_no_orig.get("impact_log", [])), res_state_no_orig.get("impact_log"))
        if res_state_no_orig.get("impact_log"): # Guard against empty log
            self.assertIn("Original Swagger 2.0 content is missing", res_state_no_orig.get("impact_log")[0]['descricao'])

        state_no_final = self._create_initial_state(swagger_spec={"swagger":"2.0"}, final_spec=None)
        res_state_no_final = impact_analysis_node(state_no_final)
        self.assertIsNotNone(res_state_no_final.get("error_message"))
        self.assertIn("Final OpenAPI 3.1 spec is missing", res_state_no_final.get("error_message"))
        self.assertTrue(any(item.get("tipo") == "error" for item in res_state_no_final.get("impact_log", [])))


if __name__ == '__main__':
    unittest.main()
