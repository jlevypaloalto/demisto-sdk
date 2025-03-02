import os

import pytest
from click.testing import CliRunner
from wcmatch.pathlib import Path

from demisto_sdk.__main__ import main
from demisto_sdk.commands.common.constants import ENV_DEMISTO_SDK_MARKETPLACE
from demisto_sdk.commands.common.tools import src_root
from demisto_sdk.commands.create_artifacts.tests.content_artifacts_creator_test import (
    destroy_by_ext,
    duplicate_file,
    same_folders,
    temp_dir,
)
from TestSuite.test_tools import ChangeCWD

ARTIFACTS_CMD = "create-content-artifacts"

TEST_DATA = src_root() / "tests" / "test_files"
TEST_CONTENT_REPO = TEST_DATA / "content_slim"
ARTIFACTS_EXPEXTED_RESULTS = TEST_DATA / "artifacts"


@pytest.fixture()
def mock_git(mocker):
    from demisto_sdk.commands.common.content import Content

    # Mock git working directory
    mocker.patch.object(Content, "git")
    Content.git().working_tree_dir = TEST_CONTENT_REPO
    yield


def test_integration_create_content_artifacts_no_zip(repo):
    expected_artifacts_path = ARTIFACTS_EXPEXTED_RESULTS / "integration_test"

    with ChangeCWD(repo.path):
        dir_path = repo.make_dir()
        runner = CliRunner()
        result = runner.invoke(
            main, [ARTIFACTS_CMD, "-a", dir_path, "--no-zip", "-mp", "marketplacev2"]
        )
        os.rmdir(dir_path + "/content_packs")
        assert same_folders(dir_path, expected_artifacts_path)
        assert result.exit_code == 0
        assert os.getenv(ENV_DEMISTO_SDK_MARKETPLACE) == "marketplacev2"


def test_integration_create_content_artifacts_zip(mock_git, repo):
    with ChangeCWD(repo.path):
        dir_path = repo.make_dir()
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, [ARTIFACTS_CMD, "-a", dir_path])
        dir_path = Path(dir_path)

        assert Path(dir_path / "content_new.zip").exists()
        assert Path(dir_path / "all_content.zip").exists()
        assert Path(dir_path / "content_packs.zip").exists()
        assert Path(dir_path / "content_test.zip").exists()
        assert result.exit_code == 0


@pytest.mark.parametrize(argnames="suffix", argvalues=["yml", "json"])
def test_malformed_file_failure(mock_git, suffix: str):
    with destroy_by_ext(suffix), temp_dir() as temp:
        runner = CliRunner()
        result = runner.invoke(main, [ARTIFACTS_CMD, "-a", temp, "--no-zip"])

    assert result.exit_code == 1


def test_duplicate_file_failure(mock_git):
    with duplicate_file(), temp_dir() as temp:
        runner = CliRunner()
        result = runner.invoke(main, [ARTIFACTS_CMD, "-a", temp, "--no-zip"])

    assert result.exit_code == 1


def test_specific_pack_creation(repo, tmp_path):
    """Test the -p flag for specific packs creation"""
    pack_1 = repo.setup_one_pack("Pack1")
    pack_1.pack_metadata.write_json(
        {
            "name": "Pack Number 1",
        }
    )

    pack_2 = repo.setup_one_pack("Pack2")
    pack_2.pack_metadata.write_json(
        {
            "name": "Pack Number 2",
        }
    )

    with ChangeCWD(repo.path):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, [ARTIFACTS_CMD, "-a", tmp_path, "-p", "Pack1"])

        assert result.exit_code == 0
        assert Path.exists(tmp_path / "uploadable_packs" / "Pack1.zip")
        assert not Path.exists(tmp_path / "uploadable_packs" / "Pack2.zip")


def test_create_packs_with_filter_by_id_set(repo):
    """
    Given
        - A pack with 2 scripts
        - An ID set including only one script
    When
        - running the create-content-artifacts command.
    Then
        - Verify that only the script in the ID set is exported to the pack artifacts.
    """
    pack = repo.create_pack("Joey")
    pack.pack_metadata.write_json(
        {
            "name": "Joey",
        }
    )
    script1 = pack.create_script("HowYouDoing")
    script2 = pack.create_script("ShareFood")
    repo.id_set.write_json(
        {
            "Packs": {
                "Joey": {
                    "ContentItems": {
                        "scripts": [
                            "HowYouDoing",
                        ],
                    },
                },
            },
        }
    )

    dir_path = repo.make_dir()

    with ChangeCWD(repo.path):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                ARTIFACTS_CMD,
                "-a",
                dir_path,
                "--no-zip",
                "-fbi",
                "-idp",
                repo.id_set.path,
                "-p",
                "Joey",
            ],
        )
        assert result.exit_code == 0

    scripts_folder_path = Path(dir_path) / "content_packs" / pack.name / "Scripts"
    assert (scripts_folder_path / f"script-{script1.name}.yml").exists()
    assert not (scripts_folder_path / f"script-{script2.name}.yml").exists()
