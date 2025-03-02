import builtins
import io
import logging
import os
import shutil
import tarfile
from io import TextIOWrapper
from pathlib import Path
from typing import Callable, Tuple
from unittest.mock import patch

import demisto_client
import pytest
from demisto_client.demisto_api.rest import ApiException

from demisto_sdk.commands.common.constants import (
    CLASSIFIERS_DIR,
    CONNECTIONS_DIR,
    CONTENT_ENTITIES_DIRS,
    CORRELATION_RULES_DIR,
    DASHBOARDS_DIR,
    DELETED_JSON_FIELDS_BY_DEMISTO,
    DELETED_YML_FIELDS_BY_DEMISTO,
    GENERIC_DEFINITIONS_DIR,
    GENERIC_FIELDS_DIR,
    GENERIC_MODULES_DIR,
    GENERIC_TYPES_DIR,
    INCIDENT_FIELDS_DIR,
    INCIDENT_TYPES_DIR,
    INDICATOR_FIELDS_DIR,
    INDICATOR_TYPES_DIR,
    INTEGRATIONS_DIR,
    JOBS_DIR,
    LAYOUT_RULES_DIR,
    LAYOUTS_DIR,
    LISTS_DIR,
    MODELING_RULES_DIR,
    PARSING_RULES_DIR,
    PLAYBOOKS_DIR,
    PRE_PROCESS_RULES_DIR,
    REPORTS_DIR,
    SCRIPTS_DIR,
    TEST_PLAYBOOKS_DIR,
    TRIGGER_DIR,
    WIDGETS_DIR,
    WIZARDS_DIR,
    XDRC_TEMPLATE_DIR,
    XSIAM_DASHBOARDS_DIR,
    XSIAM_REPORTS_DIR,
)
from demisto_sdk.commands.common.handlers import DEFAULT_JSON_HANDLER as json
from demisto_sdk.commands.common.handlers import DEFAULT_YAML_HANDLER as yaml
from demisto_sdk.commands.common.legacy_git_tools import git_path
from demisto_sdk.commands.common.tests.tools_test import SENTENCE_WITH_UMLAUTS
from demisto_sdk.commands.common.tools import (
    get_child_files,
    get_file,
    get_json,
    get_yaml,
)
from demisto_sdk.commands.download.downloader import Downloader
from TestSuite.test_tools import str_in_call_args_list


def ordered(obj):
    if isinstance(obj, dict):
        return sorted((k, ordered(v)) for k, v in obj.items())
    if isinstance(obj, list):
        return sorted(ordered(x) for x in obj)
    else:
        return obj


class Environment:
    """
    Environment is class designed to spin up a virtual, temporary content repo and build all objects related to
    the Downloader (such as pack content & custom content)
    """

    def __init__(self, tmp_path):
        self.CONTENT_BASE_PATH = None
        self.CUSTOM_CONTENT_BASE_PATH = None
        self.PACK_INSTANCE_PATH = None
        self.INTEGRATION_INSTANCE_PATH = None
        self.SCRIPT_INSTANCE_PATH = None
        self.PLAYBOOK_INSTANCE_PATH = None
        self.LAYOUT_INSTANCE_PATH = None
        self.LAYOUTSCONTAINER_INSTANCE_PATH = None
        self.PRE_PROCESS_RULES_INSTANCE_PATH = None
        self.LISTS_INSTANCE_PATH = None
        self.CUSTOM_CONTENT_SCRIPT_PATH = None
        self.CUSTOM_CONTENT_INTEGRATION_PATH = None
        self.CUSTOM_CONTENT_LAYOUT_PATH = None
        self.CUSTOM_CONTENT_PLAYBOOK_PATH = None
        self.CUSTOM_CONTENT_JS_INTEGRATION_PATH = None
        self.INTEGRATION_PACK_OBJECT = None
        self.SCRIPT_PACK_OBJECT = None
        self.PLAYBOOK_PACK_OBJECT = None
        self.LAYOUT_PACK_OBJECT = None
        self.LAYOUTSCONTAINER_PACK_OBJECT = None
        self.LISTS_PACK_OBJECT = None
        self.JOBS_PACK_OBJECT = None
        self.JOBS_INSTANCE_PATH = None
        self.PACK_CONTENT = None
        self.INTEGRATION_CUSTOM_CONTENT_OBJECT = None
        self.SCRIPT_CUSTOM_CONTENT_OBJECT = None
        self.PLAYBOOK_CUSTOM_CONTENT_OBJECT = None
        self.LAYOUT_CUSTOM_CONTENT_OBJECT = None
        self.FAKE_CUSTOM_CONTENT_OBJECT = None
        self.JS_INTEGRATION_CUSTOM_CONTENT_OBJECT = None
        self.CUSTOM_CONTENT = None
        self.tmp_path = Path(tmp_path)
        self.setup()

    def setup(self):
        tests_path = self.tmp_path / "tests"
        tests_env_path = tests_path / "tests_env"
        tests_data_path = tests_path / "tests_data"
        shutil.copytree(
            src="demisto_sdk/commands/download/tests/tests_env", dst=str(tests_env_path)
        )
        shutil.copytree(
            src="demisto_sdk/commands/download/tests/tests_data",
            dst=str(tests_data_path),
        )

        self.CONTENT_BASE_PATH = f"{tests_path}/tests_env/content"
        self.CUSTOM_CONTENT_BASE_PATH = f"{tests_path}/tests_data/custom_content"
        self.PACK_INSTANCE_PATH = f"{self.CONTENT_BASE_PATH}/Packs/TestPack"

        self.INTEGRATION_INSTANCE_PATH = (
            f"{self.PACK_INSTANCE_PATH}/Integrations/TestIntegration"
        )
        self.SCRIPT_INSTANCE_PATH = f"{self.PACK_INSTANCE_PATH}/Scripts/TestScript"
        self.PLAYBOOK_INSTANCE_PATH = (
            f"{self.PACK_INSTANCE_PATH}/Playbooks/playbook-DummyPlaybook.yml"
        )
        self.LAYOUT_INSTANCE_PATH = (
            f"{self.PACK_INSTANCE_PATH}/Layouts/layout-details-TestLayout.json"
        )
        self.LAYOUTSCONTAINER_INSTANCE_PATH = (
            f"{self.PACK_INSTANCE_PATH}/Layouts/layoutscontainer-mytestlayout.json"
        )
        self.PRE_PROCESS_RULES_INSTANCE_PATH = (
            f"{self.PACK_INSTANCE_PATH}/PreProcessRules/preprocessrule-dummy.json"
        )
        self.LISTS_INSTANCE_PATH = f"{self.PACK_INSTANCE_PATH}/Lists/list-dummy.json"
        self.JOBS_INSTANCE_PATH = f"{self.PACK_INSTANCE_PATH}/Jobs/job-sample.json"

        self.CUSTOM_CONTENT_SCRIPT_PATH = (
            f"{self.CUSTOM_CONTENT_BASE_PATH}/automation-TestScript.yml"
        )
        self.CUSTOM_CONTENT_INTEGRATION_PATH = (
            f"{self.CUSTOM_CONTENT_BASE_PATH}/integration-Test_Integration.yml"
        )
        self.CUSTOM_CONTENT_LAYOUT_PATH = (
            f"{self.CUSTOM_CONTENT_BASE_PATH}/layout-details-TestLayout.json"
        )
        self.CUSTOM_CONTENT_PLAYBOOK_PATH = (
            f"{self.CUSTOM_CONTENT_BASE_PATH}/playbook-DummyPlaybook.yml"
        )
        self.CUSTOM_CONTENT_JS_INTEGRATION_PATH = (
            f"{self.CUSTOM_CONTENT_BASE_PATH}/integration-DummyJSIntegration.yml"
        )
        self.CUSTOM_API_RESPONSE = f"{self.CUSTOM_CONTENT_BASE_PATH}/api-response"

        self.INTEGRATION_PACK_OBJECT = {
            "Test Integration": [
                {
                    "name": "Test Integration",
                    "id": "Test Integration",
                    "path": f"{self.INTEGRATION_INSTANCE_PATH}/TestIntegration.py",
                    "file_ending": "py",
                },
                {
                    "name": "Test Integration",
                    "id": "Test Integration",
                    "path": f"{self.INTEGRATION_INSTANCE_PATH}/TestIntegration_testt.py",
                    "file_ending": "py",
                },
                {
                    "name": "Test Integration",
                    "id": "Test Integration",
                    "path": f"{self.INTEGRATION_INSTANCE_PATH}/TestIntegration.yml",
                    "file_ending": "yml",
                },
                {
                    "name": "Test Integration",
                    "id": "Test Integration",
                    "path": f"{self.INTEGRATION_INSTANCE_PATH}/TestIntegration_image.png",
                    "file_ending": "png",
                },
                {
                    "name": "Test Integration",
                    "id": "Test Integration",
                    "path": f"{self.INTEGRATION_INSTANCE_PATH}/CHANGELOG.md",
                    "file_ending": "md",
                },
                {
                    "name": "Test Integration",
                    "id": "Test Integration",
                    "path": f"{self.INTEGRATION_INSTANCE_PATH}/TestIntegration_description.md",
                    "file_ending": "md",
                },
                {
                    "name": "Test Integration",
                    "id": "Test Integration",
                    "path": f"{self.INTEGRATION_INSTANCE_PATH}/README.md",
                    "file_ending": "md",
                },
            ]
        }
        self.SCRIPT_PACK_OBJECT = {
            "TestScript": [
                {
                    "name": "TestScript",
                    "id": "TestScript",
                    "path": f"{self.SCRIPT_INSTANCE_PATH}/TestScript.py",
                    "file_ending": "py",
                },
                {
                    "name": "TestScript",
                    "id": "TestScript",
                    "path": f"{self.SCRIPT_INSTANCE_PATH}/TestScript.yml",
                    "file_ending": "yml",
                },
                {
                    "name": "TestScript",
                    "id": "TestScript",
                    "path": f"{self.SCRIPT_INSTANCE_PATH}/CHANGELOG.md",
                    "file_ending": "md",
                },
                {
                    "name": "TestScript",
                    "id": "TestScript",
                    "path": f"{self.SCRIPT_INSTANCE_PATH}/README.md",
                    "file_ending": "md",
                },
            ]
        }
        self.PLAYBOOK_PACK_OBJECT = {
            "DummyPlaybook": [
                {
                    "name": "DummyPlaybook",
                    "id": "DummyPlaybook",
                    "path": self.PLAYBOOK_INSTANCE_PATH,
                    "file_ending": "yml",
                }
            ]
        }
        self.LAYOUT_PACK_OBJECT = {
            "Hello World Alert": [
                {
                    "name": "Hello World Alert",
                    "id": "Hello World Alert",
                    "path": self.LAYOUT_INSTANCE_PATH,
                    "file_ending": "json",
                }
            ]
        }
        self.LAYOUTSCONTAINER_PACK_OBJECT = {
            "mylayout": [
                {
                    "name": "mylayout",
                    "id": "mylayout",
                    "path": self.LAYOUTSCONTAINER_INSTANCE_PATH,
                    "file_ending": "json",
                }
            ]
        }
        self.PRE_PROCESS_RULES_PACK_OBJECT = {
            "DummyPreProcessRule": [
                {
                    "name": "DummyPreProcessRule",
                    "id": "DummyPreProcessRule",
                    "path": self.PRE_PROCESS_RULES_INSTANCE_PATH,
                    "file_ending": "json",
                }
            ]
        }
        self.LISTS_PACK_OBJECT = {
            "DummyList": [
                {
                    "name": "DummyList",
                    "id": "DummyList",
                    "path": self.LISTS_INSTANCE_PATH,
                    "file_ending": "json",
                }
            ]
        }
        self.JOBS_PACK_OBJECT = {
            "DummyJob": [
                {
                    "name": "DummyJob",
                    "id": "DummyJob",
                    "path": self.JOBS_INSTANCE_PATH,
                    "file_ending": "json",
                }
            ]
        }

        self.PACK_CONTENT = {
            INTEGRATIONS_DIR: [self.INTEGRATION_PACK_OBJECT],
            SCRIPTS_DIR: [self.SCRIPT_PACK_OBJECT],
            PLAYBOOKS_DIR: [self.PLAYBOOK_PACK_OBJECT],
            LAYOUTS_DIR: [self.LAYOUT_PACK_OBJECT, self.LAYOUTSCONTAINER_PACK_OBJECT],
            PRE_PROCESS_RULES_DIR: [],
            LISTS_DIR: [],
            JOBS_DIR: [],
            WIZARDS_DIR: [],
            TEST_PLAYBOOKS_DIR: [],
            REPORTS_DIR: [],
            DASHBOARDS_DIR: [],
            WIDGETS_DIR: [],
            INCIDENT_FIELDS_DIR: [],
            INDICATOR_FIELDS_DIR: [],
            INCIDENT_TYPES_DIR: [],
            CLASSIFIERS_DIR: [],
            CONNECTIONS_DIR: [],
            INDICATOR_TYPES_DIR: [],
            GENERIC_TYPES_DIR: [],
            GENERIC_FIELDS_DIR: [],
            GENERIC_MODULES_DIR: [],
            GENERIC_DEFINITIONS_DIR: [],
            MODELING_RULES_DIR: [],
            XDRC_TEMPLATE_DIR: [],
            PARSING_RULES_DIR: [],
            CORRELATION_RULES_DIR: [],
            XSIAM_DASHBOARDS_DIR: [],
            XSIAM_REPORTS_DIR: [],
            TRIGGER_DIR: [],
            LAYOUT_RULES_DIR: [],
        }

        self.INTEGRATION_CUSTOM_CONTENT_OBJECT = {
            "id": "Test Integration",
            "name": "Test Integration",
            "path": self.CUSTOM_CONTENT_INTEGRATION_PATH,
            "entity": "Integrations",
            "type": "integration",
            "file_ending": "yml",
            "code_lang": "python",
        }
        self.SCRIPT_CUSTOM_CONTENT_OBJECT = {
            "id": "f1e4c6e5-0d44-48a0-8020-a9711243e918",
            "name": "TestScript",
            "path": self.CUSTOM_CONTENT_SCRIPT_PATH,
            "entity": "Scripts",
            "type": "script",
            "file_ending": "yml",
            "code_lang": "python",
        }
        self.PLAYBOOK_CUSTOM_CONTENT_OBJECT = {
            "id": "DummyPlaybook",
            "name": "DummyPlaybook",
            "path": self.CUSTOM_CONTENT_PLAYBOOK_PATH,
            "entity": "Playbooks",
            "type": "playbook",
            "file_ending": "yml",
        }
        self.LAYOUT_CUSTOM_CONTENT_OBJECT = {
            "id": "Hello World Alert",
            "name": "Hello World Alert",
            "path": self.CUSTOM_CONTENT_LAYOUT_PATH,
            "entity": "Layouts",
            "type": "layout",
            "file_ending": "json",
        }
        self.FAKE_CUSTOM_CONTENT_OBJECT = {
            "id": "DEMISTO",
            "name": "DEMISTO",
            "path": f"{self.CUSTOM_CONTENT_BASE_PATH}/DEMISTO.json",
            "entity": "Layouts",
            "type": "layout",
            "file_ending": "json",
        }
        self.JS_INTEGRATION_CUSTOM_CONTENT_OBJECT = {
            "id": "SumoLogic",
            "name": "SumoLogic",
            "path": self.CUSTOM_CONTENT_JS_INTEGRATION_PATH,
            "entity": "Integrations",
            "type": "integration",
            "file_ending": "yml",
            "code_lang": "javascript",
        }

        self.CUSTOM_CONTENT = [
            self.INTEGRATION_CUSTOM_CONTENT_OBJECT,
            self.SCRIPT_CUSTOM_CONTENT_OBJECT,
            self.PLAYBOOK_CUSTOM_CONTENT_OBJECT,
            self.LAYOUT_CUSTOM_CONTENT_OBJECT,
            self.JS_INTEGRATION_CUSTOM_CONTENT_OBJECT,
        ]


class TestHelperMethods:
    @pytest.mark.parametrize(
        "code_lang, file_type, file_name, err_msg, output",
        [
            (
                "javascript",
                "integration",
                "file name",
                "Downloading an integration written in JavaScript is not supported.",
                False,
            ),
            (
                "javascript",
                "script",
                "file name",
                "Downloading a script written in JavaScript is not supported.",
                False,
            ),
            ("python", "integration", "file name", "", True),
        ],
    )
    def test_verify_code_lang(self, code_lang, file_type, file_name, err_msg, output):
        with patch.object(Downloader, "__init__", lambda a, b, c: None):
            downloader = Downloader("", "")
            downloader.files_not_downloaded = []
            assert (
                downloader.verify_code_lang(code_lang, file_type, file_name) is output
            )
            if not output:
                assert [file_name, err_msg] in downloader.files_not_downloaded

    @pytest.mark.parametrize(
        "data, file_type, entity",
        [
            ({"name": "test-pb"}, "playbook", TEST_PLAYBOOKS_DIR),
            ({"name": "playbook_testing"}, "playbook", PLAYBOOKS_DIR),
            ({"name": "playbook_test"}, "playbook", TEST_PLAYBOOKS_DIR),
            ({"name": "playbookTest"}, "playbook", TEST_PLAYBOOKS_DIR),
            ({"name": "Testplaybook"}, "playbook", TEST_PLAYBOOKS_DIR),
            ({"name": "Test-playbook"}, "playbook", TEST_PLAYBOOKS_DIR),
            ({"name": "playbook_Test"}, "playbook", TEST_PLAYBOOKS_DIR),
            ({"name": "playbook-test"}, "playbook", TEST_PLAYBOOKS_DIR),
            ({"name": "playbook-Test"}, "playbook", TEST_PLAYBOOKS_DIR),
            ({"name": "Test123"}, "playbook", TEST_PLAYBOOKS_DIR),
            ({"name": "test_123"}, "playbook", TEST_PLAYBOOKS_DIR),
            ({"name": "test-123"}, "playbook", TEST_PLAYBOOKS_DIR),
            ({"name": "Test_123"}, "playbook", TEST_PLAYBOOKS_DIR),
            ({}, "integration", INTEGRATIONS_DIR),
        ],
    )
    def test_file_type_to_entity(self, data, file_type, entity):
        with patch.object(Downloader, "__init__", lambda a, b, c: None):
            downloader = Downloader("", "")
            assert downloader.file_type_to_entity(data, file_type) == entity

    def test_get_custom_content_objects(self, tmp_path):
        env = Environment(tmp_path)
        with patch.object(Downloader, "__init__", lambda a, b, c: None):
            downloader = Downloader("", "")
            downloader.custom_content_temp_dir = env.CUSTOM_CONTENT_BASE_PATH
            custom_content_objects = downloader.get_custom_content_objects()
            assert ordered(custom_content_objects) == ordered(env.CUSTOM_CONTENT)

    @pytest.mark.parametrize(
        "name, ending, detail, output",
        [
            ("G S M", "py", "python", "GSM.py"),
            ("G S M", "yml", "yaml", "GSM.yml"),
            ("G S M", "png", "image", "GSM_image.png"),
            ("G S M", "md", "description", "GSM_description.md"),
        ],
    )
    def test_get_searched_basename(self, name, ending, detail, output):
        downloader = Downloader(output="", input="", regex="")
        assert downloader.get_searched_basename(name, ending, detail) == output

    @pytest.mark.parametrize(
        "ending, output",
        [
            ("py", "python"),
            ("md", "description"),
            ("yml", "yaml"),
            ("png", "image"),
            ("", ""),
        ],
    )
    def test_get_extracted_file_detail(self, ending, output):
        downloader = Downloader(output="", input="", regex="")
        assert downloader.get_extracted_file_detail(ending) == output

    @pytest.mark.parametrize(
        "name, output",
        [
            ("automation-demisto", "script-demisto"),
            ("wow", "wow"),
            ("playbook-demisto", "demisto"),
        ],
    )
    def test_update_file_prefix(self, name, output):
        downloader = Downloader(output="", input="", regex="")
        assert downloader.update_file_prefix(name) == output
        assert not downloader.update_file_prefix(name).startswith("playbook-")

    @pytest.mark.parametrize(
        "name", ["GSM", "G S M", "G_S_M", "G-S-M", "G S_M", "G_S-M"]
    )
    def test_create_dir_name(self, name):
        downloader = Downloader(output="", input="", regex="")
        assert downloader.create_dir_name(name) == "GSM"


class TestFlagHandlers:
    @pytest.mark.parametrize(
        "system, it, lf, a, o, i, r, res, err",
        [
            (True, True, False, False, True, True, None, True, ""),
            (
                False,
                True,
                False,
                False,
                True,
                True,
                None,
                False,
                "The item type option is just for downloading system " "items.",
            ),
            (
                True,
                False,
                False,
                False,
                True,
                True,
                None,
                False,
                "Error: Missing option '-it' / '--item-type', "
                "you should specify the system item type to download.",
            ),
            (False, False, True, True, True, True, None, True, ""),
            (
                False,
                False,
                False,
                False,
                False,
                True,
                None,
                False,
                "Error: Missing option '-o' / '--output'.",
            ),
            (
                False,
                False,
                False,
                False,
                True,
                False,
                None,
                False,
                "Error: Missing option '-i' / '--input'.",
            ),
            (False, False, False, True, True, False, None, True, ""),
            (False, False, False, True, True, True, None, True, ""),
            (False, False, False, False, True, False, "Some Regex", True, ""),
        ],
    )
    def test_verify_flags(self, system, it, lf, a, o, i, r, res, err, mocker):
        logger_info = mocker.patch.object(logging.getLogger("demisto-sdk"), "info")
        with patch.object(Downloader, "__init__", lambda x, y, z: None):
            downloader = Downloader("", "")
            downloader.list_files = lf
            downloader.all_custom_content = a
            downloader.output_pack_path = o
            downloader.input_files = i
            downloader.regex = r
            downloader.download_system_item = system
            downloader.system_item_type = it
            answer = downloader.verify_flags()
            if err:
                assert str_in_call_args_list(logger_info.call_args_list, err)
            assert answer is res

    def test_handle_all_custom_content_flag(self, tmp_path):
        env = Environment(tmp_path)
        with patch.object(Downloader, "__init__", lambda a, b, c: None):
            downloader = Downloader("", "")
            downloader.custom_content_temp_dir = env.CUSTOM_CONTENT_BASE_PATH
            downloader.all_custom_content = True
            downloader.handle_all_custom_content_flag()
            custom_content_names = [cco["name"] for cco in env.CUSTOM_CONTENT]
            assert ordered(custom_content_names) == ordered(downloader.input_files)

    def test_handle_init_flag(self, tmp_path, mocker):
        env = Environment(tmp_path)
        mock = mocker.patch.object(
            builtins, "input", side_effect=("test_pack_name", "n", "n")
        )

        downloader = Downloader(env.CONTENT_BASE_PATH, "")
        downloader.init = True
        downloader.handle_init_flag()

        assert mock.call_count == 3
        assert downloader.output_pack_path == str(
            Path(env.CONTENT_BASE_PATH) / "Packs" / "test_pack_name"
        )
        assert Path(downloader.output_pack_path, "pack_metadata.json").exists()
        assert not Path(downloader.output_pack_path, "Integrations").exists()
        for file in Path(downloader.output_pack_path).iterdir():
            assert not file.is_dir()

    def test_handle_list_files_flag(self, tmp_path, mocker):
        logger_info = mocker.patch.object(logging.getLogger("demisto-sdk"), "info")
        env = Environment(tmp_path)
        with patch.object(Downloader, "__init__", lambda a, b, c: None):
            downloader = Downloader("", "")
            downloader.custom_content_temp_dir = env.CUSTOM_CONTENT_BASE_PATH
            downloader.list_files = True
            answer = downloader.handle_list_files_flag()
            list_files = [[cco["name"], cco["type"]] for cco in env.CUSTOM_CONTENT]
            for file in list_files:
                assert all(
                    [
                        str_in_call_args_list(logger_info.call_args_list, file[0]),
                        str_in_call_args_list(logger_info.call_args_list, file[1]),
                    ]
                )
            assert answer

    def test_handle_list_files_flag_error(self, mocker, tmp_path):
        """
        GIVEN a file contained in custom content of not supported type
        WHEN the user runs demisto-sdk download -lf
        THEN the handle_list_files_flag method should ignore the file
        """
        env = Environment(tmp_path)
        mocker.patch(
            "demisto_sdk.commands.download.downloader.get_dict_from_file",
            return_value=({}, "json"),
        )
        mocker.patch(
            "demisto_sdk.commands.download.downloader.get_child_files",
            return_value=["path"],
        )
        with patch.object(Downloader, "__init__", lambda a, b, c: None):
            downloader = Downloader("", "")
            downloader.custom_content_temp_dir = env.INTEGRATION_INSTANCE_PATH
            downloader.list_files = True
            assert downloader.handle_list_files_flag()


class TestBuildPackContent:
    def test_build_pack_content(self, tmp_path):
        env = Environment(tmp_path)
        downloader = Downloader(output=env.PACK_INSTANCE_PATH, input="", regex="")
        downloader.build_pack_content()
        assert ordered(downloader.pack_content) == ordered(env.PACK_CONTENT)

    def test_build_pack_content_object(self, tmp_path):
        env = Environment(tmp_path)
        parameters = [
            {
                "entity": INTEGRATIONS_DIR,
                "path": env.INTEGRATION_INSTANCE_PATH,
                "out": env.INTEGRATION_PACK_OBJECT,
            },
            {
                "entity": SCRIPTS_DIR,
                "path": env.SCRIPT_INSTANCE_PATH,
                "out": env.SCRIPT_PACK_OBJECT,
            },
            {
                "entity": PLAYBOOKS_DIR,
                "path": env.PLAYBOOK_INSTANCE_PATH,
                "out": env.PLAYBOOK_PACK_OBJECT,
            },
            {
                "entity": LAYOUTS_DIR,
                "path": env.LAYOUT_INSTANCE_PATH,
                "out": env.LAYOUT_PACK_OBJECT,
            },
            {
                "entity": LAYOUTS_DIR,
                "path": "demisto_sdk/commands/download/tests/downloader_test.py",
                "out": {},
            },
            {
                "entity": LAYOUTS_DIR,
                "path": env.LAYOUTSCONTAINER_INSTANCE_PATH,
                "out": env.LAYOUTSCONTAINER_PACK_OBJECT,
            },
            {
                "entity": PRE_PROCESS_RULES_DIR,
                "path": env.PRE_PROCESS_RULES_INSTANCE_PATH,
                "out": [],
            },
            {"entity": LISTS_DIR, "path": env.LISTS_INSTANCE_PATH, "out": []},
            {"entity": JOBS_DIR, "path": env.JOBS_INSTANCE_PATH, "out": []},
        ]
        downloader = Downloader(output="", input="", regex="")
        for param in parameters:
            pack_content_object = downloader.build_pack_content_object(
                param["entity"], param["path"]
            )
            assert ordered(pack_content_object) == ordered(param["out"])

    def test_get_main_file_details(self, tmp_path):
        env = Environment(tmp_path)
        parameters = [
            {
                "entity": INTEGRATIONS_DIR,
                "path": env.INTEGRATION_INSTANCE_PATH,
                "main_id": "Test Integration",
                "main_name": "Test Integration",
            },
            {
                "entity": LAYOUTS_DIR,
                "path": env.LAYOUT_INSTANCE_PATH,
                "main_id": "Hello World Alert",
                "main_name": "Hello World Alert",
            },
            {
                "entity": LAYOUTS_DIR,
                "path": "demisto_sdk/commands/download/tests/downloader_test.py",
                "main_id": "",
                "main_name": "",
            },
        ]
        downloader = Downloader(output="", input="", regex="")
        for param in parameters:
            op_id, op_name = downloader.get_main_file_details(
                param["entity"], os.path.abspath(param["path"])
            )
            assert op_id == param["main_id"]
            assert op_name == param["main_name"]


class TestBuildCustomContent:
    def test_exist_in_pack_content(self, tmp_path):
        env = Environment(tmp_path)
        parameters = [
            {
                "custom_content_object": env.INTEGRATION_CUSTOM_CONTENT_OBJECT,
                "exist_in_pack": True,
            },
            {
                "custom_content_object": env.SCRIPT_CUSTOM_CONTENT_OBJECT,
                "exist_in_pack": True,
            },
            {
                "custom_content_object": env.PLAYBOOK_CUSTOM_CONTENT_OBJECT,
                "exist_in_pack": True,
            },
            {
                "custom_content_object": env.LAYOUT_CUSTOM_CONTENT_OBJECT,
                "exist_in_pack": True,
            },
            {
                "custom_content_object": env.FAKE_CUSTOM_CONTENT_OBJECT,
                "exist_in_pack": False,
            },
        ]
        with patch.object(Downloader, "__init__", lambda a, b, c: None):
            downloader = Downloader("", "")
            downloader.pack_content = env.PACK_CONTENT
            for param in parameters:
                assert (
                    downloader.exist_in_pack_content(param["custom_content_object"])
                    is param["exist_in_pack"]
                )

    def test_build_custom_content_object(self, tmp_path):
        env = Environment(tmp_path)
        parameters = [
            {
                "path": env.CUSTOM_CONTENT_SCRIPT_PATH,
                "output_custom_content_object": env.SCRIPT_CUSTOM_CONTENT_OBJECT,
            },
            {
                "path": env.CUSTOM_CONTENT_INTEGRATION_PATH,
                "output_custom_content_object": env.INTEGRATION_CUSTOM_CONTENT_OBJECT,
            },
            {
                "path": env.CUSTOM_CONTENT_LAYOUT_PATH,
                "output_custom_content_object": env.LAYOUT_CUSTOM_CONTENT_OBJECT,
            },
            {
                "path": env.CUSTOM_CONTENT_PLAYBOOK_PATH,
                "output_custom_content_object": env.PLAYBOOK_CUSTOM_CONTENT_OBJECT,
            },
        ]
        downloader = Downloader(output="", input="", regex="")
        for param in parameters:
            assert (
                downloader.build_custom_content_object(param["path"])
                == param["output_custom_content_object"]
            )


class TestPackHierarchy:
    def test_update_pack_hierarchy(self, tmp_path):
        env = Environment(tmp_path)
        script_dir_path = os.path.dirname(env.SCRIPT_INSTANCE_PATH)
        shutil.rmtree(env.INTEGRATION_INSTANCE_PATH)
        shutil.rmtree(script_dir_path)

        with patch.object(Downloader, "__init__", lambda a, b, c: None):
            downloader = Downloader("", "")
            downloader.output_pack_path = env.PACK_INSTANCE_PATH
            downloader.custom_content = env.CUSTOM_CONTENT
            downloader.update_pack_hierarchy()
            assert os.path.isdir(env.INTEGRATION_INSTANCE_PATH)
            assert os.path.isdir(env.SCRIPT_INSTANCE_PATH)


class TestMergeExistingFile:
    def test_merge_and_extract_existing_file_corrupted_dir(self, tmp_path, mocker):
        """
        Given
            - The integration exist in output pack, the directory is corrupted
            (i.e. a file is missing, for example: the image file)

        When
            - An integration about to be downloaded

        Then
            - Ensure integration is downloaded successfully
        """
        logger_info = mocker.patch.object(logging.getLogger("demisto-sdk"), "info")
        env = Environment(tmp_path)
        mocker.patch.object(
            Downloader, "get_corresponding_pack_file_object", return_value={}
        )
        with patch.object(Downloader, "__init__", lambda a, b, c: None):
            downloader = Downloader("", "")
            downloader.output_pack_path = env.PACK_INSTANCE_PATH
            downloader.pack_content = env.PACK_CONTENT
            downloader.run_format = False
            downloader.num_merged_files = 0
            downloader.num_added_files = 0
            downloader.merge_and_extract_existing_file(
                env.INTEGRATION_CUSTOM_CONTENT_OBJECT
            )
            assert str_in_call_args_list(logger_info.call_args_list, "Merged")

    def test_merge_and_extract_existing_file_js(self, tmp_path):
        with patch.object(Downloader, "__init__", lambda a, b, c: None):
            downloader = Downloader("", "")
            downloader.num_merged_files = 0
            downloader.num_added_files = 0
            downloader.files_not_downloaded = []
            downloader.pack_content = {
                entity: list() for entity in CONTENT_ENTITIES_DIRS
            }
            js_custom_content_object = {
                "id": "SumoLogic",
                "name": "SumoLogic",
                "path": "demisto_sdk/commands/download/tests/tests_data/custom_content/integration-DummyJSIntegration"
                ".yml",
                "entity": "Integrations",
                "type": "integration",
                "file_ending": "yml",
                "exist_in_pack": True,
                "code_lang": "javascript",
            }
            downloader.merge_and_extract_existing_file(js_custom_content_object)

    def test_merge_and_extract_existing_file(self, tmp_path):
        env = Environment(tmp_path)

        with patch.object(Downloader, "__init__", lambda a, b, c: None):
            downloader = Downloader("", "")
            downloader.pack_content = env.PACK_CONTENT
            downloader.run_format = False
            downloader.num_merged_files = 0
            downloader.num_added_files = 0
            downloader.merge_and_extract_existing_file(
                env.INTEGRATION_CUSTOM_CONTENT_OBJECT
            )
            paths = [
                file["path"] for file in env.INTEGRATION_PACK_OBJECT["Test Integration"]
            ]
            for path in paths:
                assert os.path.isfile(path)
            yml_data = get_yaml(
                env.INTEGRATION_PACK_OBJECT["Test Integration"][2]["path"]
            )
            for field in DELETED_YML_FIELDS_BY_DEMISTO:
                obj = yml_data
                dotted_path_list = field.split(".")
                for path_part in dotted_path_list:
                    if path_part != dotted_path_list[-1]:
                        obj = obj.get(path_part)
                    else:
                        if obj.get(path_part):
                            assert True
                        else:
                            assert False
            with open(
                env.INTEGRATION_PACK_OBJECT["Test Integration"][5]["path"]
            ) as description_file:
                description_data = description_file.read()
            assert "Test Integration Long Description TEST" in description_data
            with open(
                env.INTEGRATION_PACK_OBJECT["Test Integration"][0]["path"]
            ) as code_file:
                code_data = code_file.read()
            assert "TEST" in code_data

    def test_merge_existing_file(self, tmp_path):
        env = Environment(tmp_path)
        parameters = [
            {
                "custom_content_object": env.PLAYBOOK_CUSTOM_CONTENT_OBJECT,
                "ending": "yml",
                "method": get_yaml,
                "instance_path": env.PLAYBOOK_INSTANCE_PATH,
                "fields": ["fromversion", "toversion"],
            },
            {
                "custom_content_object": env.LAYOUT_CUSTOM_CONTENT_OBJECT,
                "ending": "json",
                "method": get_json,
                "instance_path": env.LAYOUT_INSTANCE_PATH,
                "fields": ["fromVersion", "toVersion"],
            },
        ]

        with patch.object(Downloader, "__init__", lambda a, b, c: None):
            downloader = Downloader("", "")
            downloader.pack_content = env.PACK_CONTENT
            downloader.run_format = False
            downloader.num_merged_files = 0
            downloader.num_added_files = 0
            for param in parameters:
                downloader.merge_existing_file(
                    param["custom_content_object"], param["ending"]
                )
                assert os.path.isfile(param["instance_path"])
                file_data = param["method"](param["instance_path"], cache_clear=True)
                for field in param["fields"]:
                    if file_data.get(field):
                        assert True
                    else:
                        assert False
                if param["ending"] == "yml":
                    task_4_name = file_data["tasks"]["4"]["task"]["name"]
                    assert task_4_name == "Done TEST"

    def test_get_corresponding_pack_content_object(self, tmp_path):
        env = Environment(tmp_path)
        parameters = [
            {
                "custom_content_obj": env.INTEGRATION_CUSTOM_CONTENT_OBJECT,
                "pack_content_obj": env.INTEGRATION_PACK_OBJECT,
            },
            {
                "custom_content_obj": env.SCRIPT_CUSTOM_CONTENT_OBJECT,
                "pack_content_obj": env.SCRIPT_PACK_OBJECT,
            },
            {
                "custom_content_obj": env.PLAYBOOK_CUSTOM_CONTENT_OBJECT,
                "pack_content_obj": env.PLAYBOOK_PACK_OBJECT,
            },
            {
                "custom_content_obj": env.LAYOUT_CUSTOM_CONTENT_OBJECT,
                "pack_content_obj": env.LAYOUT_PACK_OBJECT,
            },
            {
                "custom_content_obj": env.FAKE_CUSTOM_CONTENT_OBJECT,
                "pack_content_obj": {},
            },
        ]
        with patch.object(Downloader, "__init__", lambda a, b, c: None):
            downloader = Downloader("", "")
            downloader.pack_content = env.PACK_CONTENT
            for param in parameters:
                corr_obj = downloader.get_corresponding_pack_content_object(
                    param["custom_content_obj"]
                )
                assert ordered(corr_obj) == ordered(param["pack_content_obj"])

    def test_get_corresponding_pack_file_object(self, tmp_path):
        env = Environment(tmp_path)
        parameters = [
            {
                "file_name": "Test Integration",
                "ex_file_ending": "yml",
                "ex_file_detail": "yaml",
                "corr_pack_object": env.INTEGRATION_PACK_OBJECT,
                "pack_file_object": env.INTEGRATION_PACK_OBJECT["Test Integration"][2],
            },
            {
                "file_name": "Test Integration",
                "ex_file_ending": "py",
                "ex_file_detail": "python",
                "corr_pack_object": env.INTEGRATION_PACK_OBJECT,
                "pack_file_object": env.INTEGRATION_PACK_OBJECT["Test Integration"][0],
            },
            {
                "file_name": "Test Integration",
                "ex_file_ending": "png",
                "ex_file_detail": "image",
                "corr_pack_object": env.INTEGRATION_PACK_OBJECT,
                "pack_file_object": env.INTEGRATION_PACK_OBJECT["Test Integration"][3],
            },
            {
                "file_name": "Test Integration",
                "ex_file_ending": "md",
                "ex_file_detail": "description",
                "corr_pack_object": env.INTEGRATION_PACK_OBJECT,
                "pack_file_object": env.INTEGRATION_PACK_OBJECT["Test Integration"][5],
            },
            {
                "file_name": "TestScript",
                "ex_file_ending": "yml",
                "ex_file_detail": "yaml",
                "corr_pack_object": env.SCRIPT_PACK_OBJECT,
                "pack_file_object": env.SCRIPT_PACK_OBJECT["TestScript"][1],
            },
            {
                "file_name": "TestScript",
                "ex_file_ending": "py",
                "ex_file_detail": "python",
                "corr_pack_object": env.SCRIPT_PACK_OBJECT,
                "pack_file_object": env.SCRIPT_PACK_OBJECT["TestScript"][0],
            },
            {
                "file_name": "Fake Name",
                "ex_file_ending": "py",
                "ex_file_detail": "python",
                "corr_pack_object": env.SCRIPT_PACK_OBJECT,
                "pack_file_object": {},
            },
        ]
        with patch.object(Downloader, "__init__", lambda a, b, c: None):
            downloader = Downloader("", "")
            downloader.pack_content = env.PACK_CONTENT
            for param in parameters:
                file_name = param["file_name"]
                ex_file_ending = param["ex_file_ending"]
                ex_file_detail = param["ex_file_detail"]
                corr_pack_object = param["corr_pack_object"]
                pack_file_object = param["pack_file_object"]
                searched_basename = downloader.get_searched_basename(
                    file_name, ex_file_ending, ex_file_detail
                )
                corr_file = downloader.get_corresponding_pack_file_object(
                    searched_basename, corr_pack_object
                )
                assert ordered(corr_file) == ordered(pack_file_object)

    def test_update_data_yml(self, tmp_path):
        env = Environment(tmp_path)
        downloader = Downloader(output="", input="", regex="")
        downloader.update_data(
            env.CUSTOM_CONTENT_INTEGRATION_PATH,
            f"{env.INTEGRATION_INSTANCE_PATH}/TestIntegration.yml",
            "yml",
        )

        file_yaml_object = get_yaml(env.CUSTOM_CONTENT_INTEGRATION_PATH)
        for field in DELETED_YML_FIELDS_BY_DEMISTO:
            obj = file_yaml_object
            dotted_path_list = field.split(".")
            for path_part in dotted_path_list:
                if path_part != dotted_path_list[-1]:
                    obj = obj.get(path_part)
                else:
                    if obj.get(path_part):
                        assert True
                    else:
                        assert False

    def test_update_data_json(self, tmp_path):
        env = Environment(tmp_path)
        downloader = Downloader(output="", input="", regex="")
        downloader.update_data(
            env.CUSTOM_CONTENT_LAYOUT_PATH, env.LAYOUT_INSTANCE_PATH, "json"
        )
        file_data: dict = get_json(env.CUSTOM_CONTENT_LAYOUT_PATH)
        for field in DELETED_JSON_FIELDS_BY_DEMISTO:
            obj = file_data
            dotted_path_list = field.split(".")
            for path_part in dotted_path_list:
                if path_part != dotted_path_list[-1]:
                    obj = obj.get(path_part)
                else:
                    if obj.get(path_part):
                        assert True
                    else:
                        assert False


class TestMergeNewFile:
    def test_merge_and_extract_new_file(self, tmp_path):
        env = Environment(tmp_path)
        parameters = [
            {
                "custom_content_object": env.INTEGRATION_CUSTOM_CONTENT_OBJECT,
                "raw_files": [
                    "odp/bn.py",
                    "odp/bn.yml",
                    "odp/bn_image.png",
                    "odp/bn_description.md",
                    "odp/README.md",
                ],
            },
            {
                "custom_content_object": env.SCRIPT_CUSTOM_CONTENT_OBJECT,
                "raw_files": ["odp/bn.py", "odp/bn.yml", "odp/README.md"],
            },
        ]
        for param in parameters:
            temp_dir = env.tmp_path / f"temp_dir_{parameters.index(param)}"
            os.mkdir(temp_dir)
            entity = param["custom_content_object"]["entity"]
            downloader = Downloader(output=str(temp_dir), input="", regex="")
            basename = downloader.create_dir_name(
                param["custom_content_object"]["name"]
            )
            output_entity_dir_path = f"{temp_dir}/{entity}"
            os.mkdir(output_entity_dir_path)
            output_dir_path = f"{output_entity_dir_path}/{basename}"
            os.mkdir(output_dir_path)
            files = [
                file.replace("odp", output_dir_path).replace("bn", basename)
                for file in param["raw_files"]
            ]

            downloader.merge_and_extract_new_file(param["custom_content_object"])
            output_files = get_child_files(output_dir_path)
            assert sorted(output_files) == sorted(files)

    def test_merge_new_file(self, tmp_path):
        env = Environment(tmp_path)
        parameters = [
            {"custom_content_object": env.PLAYBOOK_CUSTOM_CONTENT_OBJECT},
            {"custom_content_object": env.LAYOUT_CUSTOM_CONTENT_OBJECT},
        ]
        for param in parameters:
            temp_dir = env.tmp_path / f"temp_dir_{parameters.index(param)}"
            os.mkdir(temp_dir)
            entity = param["custom_content_object"]["entity"]
            output_dir_path = f"{temp_dir}/{entity}"
            os.mkdir(output_dir_path)
            old_file_path = param["custom_content_object"]["path"]
            new_file_path = f"{output_dir_path}/{os.path.basename(old_file_path)}"
            downloader = Downloader(output=temp_dir, input="", regex="")
            downloader.merge_new_file(param["custom_content_object"])
            assert os.path.isfile(new_file_path)


class TestVerifyPackPath:
    @pytest.mark.parametrize(
        "output_path, valid_ans",
        [
            ("Integrations", False),
            ("Packs/TestPack/", True),
            ("Demisto", False),
            ("Packs", False),
            ("Packs/TestPack", True),
        ],
    )
    def test_verify_output_path_is_pack(self, tmp_path, output_path, valid_ans):
        env = Environment(tmp_path)
        downloader = Downloader(
            output=f"{env.CONTENT_BASE_PATH}/{output_path}", input="", regex=""
        )
        assert downloader.verify_output_pack_is_pack() is valid_ans


@pytest.mark.parametrize(
    "input, system, it, insecure, endpoint, req_type, req_body",
    [
        (
            ["PB1", "PB2"],
            True,
            "Playbook",
            False,
            "/playbook/search",
            "GET",
            {"query": "name:PB1 or PB2"},
        ),
        (
            ["Mapper1", "Mapper2"],
            True,
            "Mapper",
            True,
            "/classifier/search",
            "POST",
            {"query": "name:Mapper1 or Mapper2"},
        ),
        (["Field1", "Field2"], True, "Field", True, "/incidentfields", "GET", {}),
        (
            ["Classifier1", "Classifier2"],
            True,
            "Classifier",
            False,
            "/classifier/search",
            "POST",
            {"query": "name:Classifier1 or Classifier2"},
        ),
    ],
)
def test_build_req_params(
    input, system, it, insecure, endpoint, req_type, req_body, monkeypatch
):
    with patch.object(Downloader, "__init__", lambda x, y, z: None):
        monkeypatch.setenv("DEMISTO_BASE_URL", "http://demisto.instance.com:8080/")
        monkeypatch.setenv("DEMISTO_API_KEY", "API_KEY")
        downloader = Downloader("", "")
        downloader.system_item_type = it
        downloader.insecure = insecure
        downloader.input_files = input
        res_endpoint, res_req_type, res_req_body = downloader.build_req_params()
        assert endpoint == res_endpoint
        assert req_type == res_req_type
        assert req_body == res_req_body


def test_arrange_response():
    with patch.object(Downloader, "__init__", lambda x, y, z: None):
        downloader = Downloader("", "")

        downloader.system_item_type = "Playbook"
        system_items_list = downloader.arrange_response([])
        assert system_items_list == []

        downloader.system_item_type = "Classifier"
        system_items_list = downloader.arrange_response({"classifiers": []})
        assert system_items_list == []

        downloader.system_item_type = "Automation"
        system_items_list = downloader.arrange_response([])
        assert system_items_list == []


def test_build_file_name():
    with patch.object(Downloader, "__init__", lambda x, y, z: None):
        downloader = Downloader("", "")

        downloader.system_item_type = "Playbook"
        file_name = downloader.build_file_name({"name": "name 1", "id": "id"})
        assert file_name == "name_1.yml"

        downloader.system_item_type = "Field"
        file_name = downloader.build_file_name({"name": "name 1", "id": "id"})
        assert file_name == "name_1.json"

        downloader.system_item_type = "Field"
        file_name = downloader.build_file_name({"id": "id 1"})
        assert file_name == "id_1.json"


@pytest.mark.parametrize(
    "original_string, object_name, expected_string, should_download_expected_res",
    [
        (
            "name: TestingScript\ncommonfields:\n id: f1e4c6e5-0d44-48a0-8020-a9711243e918",
            "automation-Testing.yml",
            "name: TestingScript\ncommonfields:\n id: f1e4c6e5-0d44-48a0-8020-a9711243e918",
            False,
        ),
        (
            "name: Playbook\ncommonfields:\n id: f1e4c6e5-0d44-48a0-8020-a9711243e918",
            "playbook-Testing.yml",
            "name: Playbook\ncommonfields:\n id: f1e4c6e5-0d44-48a0-8020-a9711243e918",
            True,
        ),
    ],
)
def test_download_playbook(
    original_string, object_name, expected_string, should_download_expected_res
):
    downloader = Downloader(output="", input="", regex="", all_custom_content=True)
    should_download_playbook = downloader.should_download_playbook(object_name)
    final_string = downloader.download_playbook_yaml(original_string)
    assert should_download_playbook == should_download_expected_res
    assert final_string == expected_string


@pytest.mark.parametrize(
    "original_string, uuids_to_name_map, expected_string",
    [
        (
            "name: TestingScript\ncommonfields:\n id: f1e4c6e5-0d44-48a0-8020-a9711243e918",
            {},
            "name: TestingScript\ncommonfields:\n id: f1e4c6e5-0d44-48a0-8020-a9711243e918",
        ),
        (
            '{"name":"TestingField","script":"f1e4c6e5-0d44-48a0-8020-a9711243e918"}',
            {"f1e4c6e5-0d44-48a0-8020-a9711243e918": "TestingScript"},
            '{"name":"TestingField","script":"TestingScript"}',
        ),
        (
            '{"name":"TestingLayout","detailsV2":{"tabs":[{"sections":[{'
            '"items":[{"scriptId":"f1e4c6e5-0d44-48a0-8020-a9711243e918"'
            "}]}]}]}}",
            {"f1e4c6e5-0d44-48a0-8020-a9711243e918": "TestingScript"},
            '{"name":"TestingLayout","detailsV2":{"tabs":[{"sections":[{'
            '"items":[{"scriptId":"TestingScript"'
            "}]}]}]}}",
        ),
    ],
)
def test_replace_uuids(original_string, uuids_to_name_map, expected_string):
    downloader = Downloader(output="", input="", regex="", all_custom_content=True)
    final_string = downloader.replace_uuids(
        original_string, uuids_to_name_map, "file_name"
    )
    assert final_string == expected_string


@pytest.mark.parametrize("source_is_unicode", (True, False))
@pytest.mark.parametrize(
    "suffix,dumps_method,write_method,fields",
    (
        (
            ".json",
            json.dumps,
            lambda f, data: json.dump(data, f),
            ("fromVersion", "toVersion"),
        ),
        (
            ".yml",
            yaml.dumps,
            lambda f, data: yaml.dump(data, f),
            ("fromversion", "toversion"),
        ),
    ),
)
def test_safe_write_unicode_to_non_unicode(
    tmp_path: Path,
    suffix: str,
    dumps_method: Callable,
    write_method: Callable[[TextIOWrapper, dict], None],
    source_is_unicode: bool,
    fields: Tuple[
        str, str
    ],  # not all field names are merged, and they depend on the file type
) -> None:
    """
    Given: A format to check (yaml/json), with its writing method
    When: Calling Downloader.update_data
    Then:
        1. Make sure that dowloading unicode content into a non-unicode file works (result should be all unicode)
        2. Make sure that dowloading non-unicode content into a unicode file works (result should be all unicode)
    """
    from demisto_sdk.commands.download.downloader import Downloader

    non_unicode_path = (tmp_path / "non_unicode").with_suffix(suffix)
    with non_unicode_path.open("wb") as f:
        f.write(
            dumps_method({fields[0]: SENTENCE_WITH_UMLAUTS}).encode(
                "latin-1", "backslashreplace"
            )
        )
    assert "ü" in non_unicode_path.read_text(
        encoding="latin-1"
    )  # assert it was written as latin-1

    unicode_path = (tmp_path / "unicode").with_suffix(suffix)
    with open(unicode_path, "w") as f:
        write_method(f, {fields[1]: SENTENCE_WITH_UMLAUTS})
    assert "ü" in unicode_path.read_text(
        encoding="utf-8"
    )  # assert the content was written as unicode

    source, dest = (
        (unicode_path, non_unicode_path)
        if source_is_unicode
        else (
            non_unicode_path,
            unicode_path,
        )
    )

    Downloader.update_data(
        output_path=str(dest), file_path_to_read=str(source), file_ending=suffix[1:]
    )

    # make sure the two files were merged correctly
    result = get_file(dest, suffix)
    assert set(result.keys()) == set(fields)
    assert set(result.values()) == {SENTENCE_WITH_UMLAUTS}


def test_find_uuids_in_content_item():
    """
    Given: a mock tar file download_tar.tar
    When: calling find_uuids_in_content_item on the mock tar
    Then: Find all UUIDs in different content items:
          playbook, automation, layout, incident
          and replaces these UUIDs with the corresponding names in strings_to_write
    """
    expected_UUIDs = {
        "a53a2f17-2f05-486d-867f-a36c9f5b88d4",
        "e4c2306d-5d4b-4b19-8320-6fdad94595d4",
        "de57b1f7-b754-43d2-8a8c-379d12bdddcd",
        "84731e69-0e55-40f9-806a-6452f97a01a0",
        "4d45f0d7-5fdd-4a4b-8f1e-5f2502f90a61",
    }
    io_bytes = io.BytesIO(
        Path(
            f"{git_path()}/demisto_sdk/commands/download/tests/tests_data/custom_content/\
download_tar.tar"
        ).read_bytes()
    )
    downloader = Downloader(
        output="",
        input="",
        regex="",
        all_custom_content=True,
    )
    with tarfile.open(fileobj=io_bytes, mode="r") as tar:
        strings_to_write, scripts_id_name = downloader.find_uuids_in_content_item(tar)
    ids = set(scripts_id_name.keys())
    assert ids.issubset(expected_UUIDs)
    assert ids.isdisjoint(strings_to_write)


def test_get_system_playbook(mocker):
    """
    Given: a mock file raw_playbook.txt
    When: calling get_system_playbook function.
    Then:
        - Ensure the playbook returns as valid json as expected
        - Ensure a list is returned from the function
    """

    playbook_path = Path(
        f"{git_path()}/demisto_sdk/commands/download/tests/tests_data/playbook-DummyPlaybook2.yml"
    )

    raw_playbook = playbook_path.read_bytes()

    expected_pb = get_yaml(playbook_path)
    mocker.patch.object(
        demisto_client, "generic_request_func", return_value=[raw_playbook]
    )

    downloader = Downloader(input=["test"], output="test")
    playbooks = downloader.get_system_playbook(req_type="GET")
    assert isinstance(playbooks, list)
    assert playbooks[0] == expected_pb
    assert len(playbooks) == 1


def test_get_system_playbook_item_does_not_exist_by_name(mocker):
    """
    Given: a mock file raw_playbook.txt
    When: calling get_system_playbook function.
    Then:
        - Ensure the playbook returns as valid json as expected
        - Ensure a list is returned from the function
    """
    playbook_path = Path(
        f"{git_path()}/demisto_sdk/commands/download/tests/tests_data/playbook-DummyPlaybook2.yml"
    )

    playbook = get_yaml(playbook_path)
    playbook["id"] = "dummy_-_playbook"
    mocker.patch.object(
        demisto_client,
        "generic_request_func",
        side_effect=(ApiException("Item not found"), [playbook_path.read_bytes()]),
    )
    mocker.patch.object(
        Downloader, "get_playbook_id_by_playbook_name", return_value="test"
    )
    downloader = Downloader(input=["DummyPlaybook"], output="test")
    playbooks = downloader.get_system_playbook(req_type="GET")
    assert isinstance(playbooks, list)
    assert len(playbooks) == 1


@pytest.mark.parametrize(
    "exception, mock_value, expected_call",
    [(Exception, "test", 0), (ApiException, None, 1)],
)
def test_get_system_playbook_failure(mocker, exception, mock_value, expected_call):
    """
    Given: a mock exception
    When: calling get_system_playbook function.
    Then:
        - Ensure that when the API call throws a non-ApiException error,
          a second attempt is not made to retrieve the playbook by the ID.
        - Ensure that when the API call throws an ApiException error and the id extraction fails,
          the function raises the same error.
    """
    mocker.patch.object(demisto_client, "generic_request_func", side_effect=exception())
    get_id_by_name_mock = mocker.patch.object(
        Downloader, "get_playbook_id_by_playbook_name", return_value=mock_value
    )
    downloader = Downloader(input=["DummyPlaybook"], output="test")
    with pytest.raises(exception):
        downloader.get_system_playbook(req_type="GET")
    assert get_id_by_name_mock.call_count == expected_call
