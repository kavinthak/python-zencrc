"""
Unit tests for the zencrc.crc32 module.
"""
import tempfile
from pathlib import Path

from zencrc import crc32


def test_crc32_from_file(tmp_path):
    """Test CRC32 calculation from a file."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, ZenCRC!")
    expected_crc = "F274708E"
    assert crc32.crc32_from_file(str(test_file)) == expected_crc


def test_extract_crc_from_filename(tmp_path):
    """Test extracting CRC32 from filename."""
    file_with_crc = tmp_path / "test [F274708E].txt"
    assert crc32.extract_crc_from_filename(str(file_with_crc)) == "F274708E"
    file_without_crc = tmp_path / "test.txt"
    assert crc32.extract_crc_from_filename(str(file_without_crc)) is None


def test_verify_in_filename(tmp_path):
    """Test verifying CRC32 in filename."""
    file = tmp_path / "test.txt"
    file.write_text("Hello, ZenCRC!")
    crc = crc32.crc32_from_file(str(file))

    # Test correct CRC
    file_with_crc = tmp_path / f"test [{crc}].txt"
    file.rename(file_with_crc)
    filename_crc, calculated_crc = crc32.verify_in_filename(str(file_with_crc))
    assert filename_crc == calculated_crc

    # Test incorrect CRC
    file_with_wrong_crc = tmp_path / "test [DEADBEEF].txt"
    file_with_crc.rename(file_with_wrong_crc)
    filename_crc, calculated_crc = crc32.verify_in_filename(str(file_with_wrong_crc))
    assert filename_crc != calculated_crc


def test_append_to_filename(tmp_path):
    """Test appending CRC32 to filename."""
    file = tmp_path / "test.txt"
    file.write_text("Hello, ZenCRC!")
    crc = crc32.crc32_from_file(str(file))

    crc32.append_to_filename(str(file))
    assert not file.exists()
    assert (tmp_path / f"test [{crc}].txt").exists()


def test_parse_sfv_line():
    """Test parsing SFV file lines."""
    assert crc32.parse_sfv_line("file.txt 12345678") == ("file.txt", "12345678")
    assert crc32.parse_sfv_line("; comment") is None
    assert crc32.parse_sfv_line("") is None


def test_verify_sfv_file(tmp_path):
    """Test verifying SFV files."""
    file1 = tmp_path / "file1.txt"
    file1.write_text("file1")
    crc1 = crc32.crc32_from_file(str(file1))

    sfv_file = tmp_path / "test.sfv"
    with open(sfv_file, "w") as f:
        f.write(f"{file1.name} {crc1}\n")
        f.write("file2.txt DEADBEEF\n")

    results = crc32.verify_sfv_file(str(sfv_file))
    assert len(results) == 2
    assert results[0]["ok"]
    assert not results[1]["ok"]


def test_create_sfv_file(tmp_path):
    """
    Verify that create_sfv_file writes an SFV file listing the given files with their CRC32 values.
    
    Creates a temporary file, computes its CRC32, calls create_sfv_file to generate an SFV at the specified path, and asserts the SFV contains a line with "filename <CRC>" for the file.
    """
    file1 = tmp_path / "file1.txt"
    file1.write_text("file1")
    crc1 = crc32.crc32_from_file(str(file1))

    sfv_file = tmp_path / "test.sfv"
    crc32.create_sfv_file(str(sfv_file), [str(file1)])

    with open(sfv_file, "r") as f:
        content = f.read()
        assert f"{file1.name} {crc1}" in content