"""
Unit tests for the zencrc.zencrc_cli module.
"""
import os
import tempfile
from pathlib import Path

from click.testing import CliRunner

from zencrc import crc32
from zencrc.zencrc_cli import cli, expand_and_filter_files


def test_expand_and_filter_files():
    """Test the expand_and_filter_files function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir)
        sub_dir = test_dir / "subdir"
        sub_dir.mkdir()

        file1 = test_dir / "file1.txt"
        file1.write_text("file1")
        file2 = sub_dir / "file2.txt"
        file2.write_text("file2")

        # Test recursion
        paths = (str(test_dir),)
        files = expand_and_filter_files(paths, recurse=True)
        assert set(files) == {file1, file2}

        # Test no recursion
        files = expand_and_filter_files(paths, recurse=False)
        assert set(files) == set()

        # Test with files
        paths = (str(file1), str(test_dir))
        files = expand_and_filter_files(paths, recurse=False)
        assert set(files) == {file1}


def test_verify_command(tmp_path):
    """Test the verify command."""
    runner = CliRunner()
    file = tmp_path / "test.txt"
    file.write_text("hello")
    crc = crc32.crc32_from_file(str(file))
    file_with_crc = tmp_path / f"test [{crc}].txt"
    file.rename(file_with_crc)

    result = runner.invoke(cli, ["verify", str(file_with_crc)])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_append_command(tmp_path):
    """Test the append command."""
    runner = CliRunner()
    file = tmp_path / "test.txt"
    file.write_text("hello")
    crc = crc32.crc32_from_file(str(file))

    result = runner.invoke(cli, ["append", str(file)])
    assert result.exit_code == 0
    assert not file.exists()
    assert (tmp_path / f"test [{crc}].txt").exists()


def test_sfv_create_command(tmp_path):
    """Test the sfv create command."""
    runner = CliRunner()
    file = tmp_path / "test.txt"
    file.write_text("hello")
    sfv_file = tmp_path / "test.sfv"

    result = runner.invoke(cli, ["sfv", "--file", str(sfv_file), str(file)])
    assert result.exit_code == 0
    assert sfv_file.exists()
    with open(sfv_file, "r") as f:
        content = f.read()
        assert "test.txt" in content


def test_sfv_verify_command(tmp_path):
    """Test the sfv verify command."""
    runner = CliRunner()
    file = tmp_path / "test.txt"
    file.write_text("hello")
    crc = crc32.crc32_from_file(str(file))
    sfv_file = tmp_path / "test.sfv"
    with open(sfv_file, "w") as f:
        f.write(f"{file.name} {crc}")

    result = runner.invoke(cli, ["sfv", "--file", str(sfv_file)])
    assert result.exit_code == 0
    assert "OK" in result.output
