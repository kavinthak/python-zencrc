import binascii
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict

from . import __version__

CRC_REGEX = r"[^\\\[\\(]*?([\\\[\\(])([0-9a-f]{8})([\\\]\\)])[^/]*$"


def crc32_from_file(filepath: str) -> str:
    """
    Compute the CRC32 checksum of a file and return it as an uppercase 8‑digit hexadecimal string.
    
    The function reads the entire file in binary mode, computes the CRC32 value, masks it to 32 bits, and formats it as eight uppercase hex digits (e.g. "1A2B3C4D").
    
    Parameters:
        filepath (str): Path to the file to checksum.
    
    Returns:
        str: Uppercase 8-character hexadecimal CRC32 (no `0x` prefix).
    
    Raises:
        OSError: Propagates file I/O errors such as FileNotFoundError or permission errors.
    """
    with open(filepath, "rb") as file:
        checksum = binascii.crc32(file.read()) & 0xFFFFFFFF
        return f"{checksum:08X}"


def extract_crc_from_filename(filepath: str) -> Optional[str]:
    """
    Return an 8-character uppercase CRC32 hex string found in the given filepath, or None if no CRC is present.
    
    Searches the entire filepath (not limited to basename) using CRC_REGEX and returns the matched 8-hex-digit value in uppercase when present.
    """
    match = re.search(CRC_REGEX, filepath, re.I)
    return match.group(2).upper() if match else None


def verify_in_filename(filepath: str) -> Tuple[Optional[str], str]:
    """
    Return the CRC embedded in the filename (if any) and the CRC computed from the file's contents.
    
    Parameters:
        filepath (str): Path to the file to inspect and compute CRC for.
    
    Returns:
        Tuple[Optional[str], str]: A tuple (filename_crc, calculated_crc) where `filename_crc` is the 8-hex CRC extracted from the filename (uppercase) or None if no CRC is present, and `calculated_crc` is the computed 8-hex uppercase CRC of the file's contents.
    
    Notes:
        - IO and file-related exceptions from computing the CRC are propagated to the caller.
    """
    filename_crc = extract_crc_from_filename(filepath)
    calculated_crc = crc32_from_file(filepath)
    return filename_crc, calculated_crc


def append_to_filename(filepath: str) -> None:
    """
    Append the file's CRC32 (as an 8-hex uppercase value in square brackets) into its filename if not already present.
    
    If the filename already contains an 8-digit CRC matching CRC_REGEX, the function does nothing. Otherwise it computes the file's CRC32 and renames the file by inserting ` [<CRC>]` before the file extension (e.g. `name.txt` -> `name [1A2B3C4D].txt`).
    
    Parameters:
        filepath (str): Path to the target file to inspect and potentially rename.
    
    Side effects:
        Renames the file on disk.
    
    Notes:
        Any I/O exceptions (e.g., FileNotFoundError, PermissionError, OSError) raised during CRC calculation or renaming are propagated to the caller.
    """
    if extract_crc_from_filename(filepath):
        return

    path = Path(filepath)
    crc = crc32_from_file(filepath)
    new_path = path.with_name(f"{path.stem} [{crc}]{path.suffix}")
    os.rename(filepath, new_path)


def parse_sfv_line(line: str) -> Optional[Tuple[str, str]]:
    """
    Parse a single line from an SFV file and extract the file path and its 8-hex CRC.
    
    Blank lines and comment lines (starting with ';') are ignored. The function matches
    a pattern of a file path (any characters, non-greedy) followed by whitespace and an
    8-hex-digit CRC at the end of the line. If the line matches, returns a tuple
    (file_path, crc) where `crc` is returned in uppercase; otherwise returns None.
    
    Parameters:
        line (str): One line from an SFV file (may include trailing/leading whitespace).
    
    Returns:
        Optional[Tuple[str, str]]: (relative_or_named_path, CRC8_hex_uppercase) or None
        if the line is blank, a comment, or does not match the expected format.
    """
    line = line.strip()
    if not line or line.startswith(";"):
        return None

    match = re.match(r'(.*?)\s+([0-9A-Fa-f]{8})$', line)
    if not match:
        return None

    return match.group(1), match.group(2).upper()


def verify_sfv_file(sfv_filepath: str) -> List[Dict]:
    """
    Verify every file listed in an SFV file and return per-file results.
    
    Reads the SFV file at `sfv_filepath`, parses each non-comment line, and for each entry computes the CRC32 of the referenced file (relative to the SFV file's directory). Returns a list of result dictionaries, one per valid SFV entry.
    
    Parameters:
        sfv_filepath (str): Path to the SFV file to verify.
    
    Returns:
        List[Dict]: A list of dictionaries with the following keys:
            - "file" (str): The file path as listed in the SFV (relative to the SFV file).
            - "expected_crc" (str): The 8-hex-digit CRC value from the SFV (uppercase).
            - "actual_crc" (Optional[str]): The computed CRC for the file (uppercase), or None if the file was not found.
            - "ok" (bool): True if `actual_crc` equals `expected_crc`; False otherwise.
    
    Notes:
        - Lines that are blank or start with ';' are ignored.
        - If a listed file is missing, its `actual_crc` remains None and `ok` is False.
        - File I/O or CRC calculation errors other than FileNotFoundError may propagate to the caller.
    """
    results = []
    sfv_dir = Path(sfv_filepath).parent

    with open(sfv_filepath, "r", encoding="utf-8") as f:
        for line in f:
            parsed = parse_sfv_line(line)
            if not parsed:
                continue

            filepath_str, expected_crc = parsed
            filepath = sfv_dir / filepath_str
            result = {
                "file": filepath_str,
                "expected_crc": expected_crc,
                "actual_crc": None,
                "ok": False,
            }

            try:
                actual_crc = crc32_from_file(str(filepath))
                result["actual_crc"] = actual_crc
                if actual_crc == expected_crc:
                    result["ok"] = True
            except FileNotFoundError:
                pass  # Keep status as not found

            results.append(result)

    return results


def create_sfv_file(sfv_filepath: str, filepaths: List[str]) -> None:
    """
    Create an SFV file listing CRC32 checksums for the given files.
    
    Writes an SFV at `sfv_filepath` (UTF-8) with a generated header line containing the tool version and timestamp, then one entry per existing file in `filepaths` in the form:
        <filename> <8-hex-CRC>
    
    Files that cannot be read or are directories are skipped; other I/O errors (e.g., permission errors when opening the SFV) will propagate.
    """
    with open(sfv_filepath, "w", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"; Generated by ZenCRC v{__version__} on {timestamp}\n")
        for filepath in filepaths:
            try:
                crc = crc32_from_file(filepath)
                f.write(f"{Path(filepath).name} {crc}\n")
            except (FileNotFoundError, IsADirectoryError):
                continue