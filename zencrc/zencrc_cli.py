import os
from pathlib import Path
from typing import List, Tuple, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

from zencrc import crc32, __version__

console = Console()


class ErrorHandler:
    @staticmethod
    def show_no_files_error():
        """
        Prints a standardized "no files" error message to the console and aborts command execution.
        
        This helper outputs user-facing guidance about using the recursive `-r` flag and how to view help, then terminates the current Click command by raising `click.Abort`.
        """
        console.print("\n[red]❌ Error: No valid files found to process.[/red]")
        console.print("\nUse [green]-r[/green] flag to search recursively")
        console.print(
            "\nFor more information, run: [blue]zencrc --help[/blue]\n"
        )
        raise click.Abort()

    @staticmethod
    def show_error(message):
        """
        Print a formatted error message to the console and abort the CLI.
        
        Parameters:
            message (str): Human-readable error message to display.
        
        Raises:
            click.Abort: Always raised after printing the error to stop command execution.
        """
        console.print(f"\n[red]❌ Error: {message}[/red]")
        raise click.Abort()


def print_header(title: str) -> None:
    """
    Print a styled section header to the shared Rich console.
    
    Renders the provided title in bold green inside a horizontal rule using the module-level `console`. This writes directly to the terminal (no return value).
    """
    console.rule(f"[bold green]{title}[/bold green]")


def expand_and_filter_files(
    paths: Tuple[str, ...], recurse: bool
) -> List[Path]:
    """
    Return a list of file Paths derived from the given path strings.
    
    If recurse is True, any input that is a directory is expanded recursively and all contained files are included.
    If recurse is False, only inputs that are existing files are kept. Non-existent paths and directories (when
    not recursing) are ignored.
    
    Parameters:
        paths (Tuple[str, ...]): Iterable of path strings to files or directories.
        recurse (bool): When True, directories in `paths` are recursively expanded to include their files.
    
    Returns:
        List[Path]: List of Path objects pointing to files found (order follows the input order and recursive discovery).
    """
    expanded_paths = []
    if recurse:
        for p in paths:
            path = Path(p)
            if path.is_dir():
                expanded_paths.extend(
                    sub_path
                    for sub_path in path.rglob('*')
                    if sub_path.is_file()
                )
            elif path.is_file():
                expanded_paths.append(path)
    else:
        expanded_paths = [Path(p) for p in paths if Path(p).is_file()]
    return expanded_paths


def process_files_with_progress(
    file_paths: List[Path], process_func, description: str
) -> None:
    """
    Process each file while displaying a progress bar.
    
    Calls `process_func(path_str)` for every Path in `file_paths` in order and shows a progress bar with `description` as the task label.
    
    Parameters:
        file_paths: List[Path] — iterable of file paths to process.
        process_func: Callable[[str], Any] — function invoked for each file; receives the file path as a string.
        description: str — label shown next to the progress bar.
    
    Notes:
        - Calls are performed sequentially; any exception raised by `process_func` will propagate.
    """
    with Progress(
        "[progress.description]{task.description}",
        "[progress.percentage]{task.percentage:>3.0f}%",
        "•",
        "[progress.completed]{task.completed} of {task.total}",
        console=console,
    ) as progress:
        task = progress.add_task(description, total=len(file_paths))
        for path in file_paths:
            process_func(str(path))
            progress.update(task, advance=1)


def create_results_table(title: str) -> Table:
    """
    Create a Rich Table configured to display file CRC results.
    
    The table includes these columns:
    - Filename: dim style, fixed width (40).
    - Size: right-justified file size.
    - Status: verification/append status (e.g., OK/FAIL/No CRC).
    - CRC32: right-justified calculated or expected CRC32 value.
    
    Returns:
        Table: A configured Rich Table ready for rows of file results.
    """
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("Filename", style="dim", width=40)
    table.add_column("Size", justify="right")
    table.add_column("Status")
    table.add_column("CRC32", justify="right")
    return table


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="ZenCRC")
@click.pass_context
def cli(ctx):
    """ZenCRC: A modern CRC32 file utility."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-r", "--recurse", is_flag=True, help="Process files recursively.")
def verify(paths: Tuple[str, ...], recurse: bool):
    """
    Verify CRC32 checksums embedded in the given file names and display a results table.
    
    Expands the provided path strings to files (recursively if `recurse` is True). For each file this calls `crc32.verify_in_filename` to read a CRC from the filename (if present) and compare it to the calculated CRC, then prints a Rich table showing filename, size, status (OK / FAIL / No CRC) and the calculated CRC. If no files are found the command prints an error and aborts execution. File-specific verification errors are shown in the results table.
    """
    print_header("VERIFY MODE")
    file_paths = expand_and_filter_files(paths, recurse)

    if not file_paths:
        ErrorHandler.show_no_files_error()

    table = create_results_table("Verification Results")

    with Progress(console=console) as progress:
        task = progress.add_task("[cyan]Verifying...", total=len(file_paths))
        for path in file_paths:
            try:
                filename_crc, calculated_crc = crc32.verify_in_filename(str(path))
                if filename_crc:
                    status = "OK" if filename_crc == calculated_crc else "FAIL"
                    status_style = "green" if status == "OK" else "red"
                else:
                    status = "No CRC"
                    status_style = "yellow"

                table.add_row(
                    path.name,
                    f"{path.stat().st_size}",
                    f"[{status_style}]{status}[/{status_style}]",
                    calculated_crc,
                )
            except ValueError as e:
                table.add_row(path.name, "-", f"[red]{e}[/red]", "-")
            progress.update(task, advance=1)

    console.print(table)


@cli.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-r", "--recurse", is_flag=True, help="Process files recursively.")
def append(paths: Tuple[str, ...], recurse: bool):
    """
    Append CRC32 checksums to the given files' filenames and report progress.
    
    This command expands the provided path arguments (recursively if requested), appends a CRC32 checksum to each file's name using crc32.append_to_filename, and displays a progress bar and a final count of processed files.
    
    Parameters:
        paths (Tuple[str, ...]): File and/or directory paths to process. Directories are expanded into files when `recurse` is True.
        recurse (bool): If True, directories in `paths` are traversed recursively to collect files.
    
    Side effects:
        - Renames files to include CRC32 checksums.
        - Prints progress and summary to the console.
        - If no files are found after expansion/filtering, the operation aborts (ErrorHandler.show_no_files_error).
    """
    print_header("APPEND MODE")
    file_paths = expand_and_filter_files(paths, recurse)

    if not file_paths:
        ErrorHandler.show_no_files_error()

    process_files_with_progress(file_paths, crc32.append_to_filename, "[cyan]Appending CRC32...")
    console.print(f"\n[bold blue]Processed {len(file_paths)} files.[/bold blue]")


@cli.command()
@click.option("-f", "--file", "sfv_file", required=True, type=click.Path(), help="SFV file to create or verify.")
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("-r", "--recurse", is_flag=True, help="Recursively add files to SFV.")
def sfv(sfv_file: str, paths: Tuple[str, ...], recurse: bool):
    """
    Create an SFV file from given files or verify an existing SFV file.
    
    If `paths` is non-empty, expands (optionally recursively) the given paths to files and writes an SFV file at `sfv_file` containing CRC32 entries for those files. If no files are found, the function aborts via ErrorHandler.show_no_files_error().
    
    If `paths` is empty, treats `sfv_file` as an existing SFV and verifies each listed entry, printing a results table to the console. If the SFV file is missing or a directory, the function reports the error via ErrorHandler.show_error().
    
    Parameters:
        sfv_file (str): Path to the SFV file to create or verify.
        paths (Tuple[str, ...]): File or directory paths to include in the SFV. If empty, the command runs in verify mode.
        recurse (bool): When creating an SFV, if True directories in `paths` are traversed recursively to include files.
    """
    if paths:
        print_header("CREATE SFV")
        file_paths = expand_and_filter_files(paths, recurse)
        if not file_paths:
            ErrorHandler.show_no_files_error()

        crc32.create_sfv_file(sfv_file, [str(p) for p in file_paths])
        console.print(f"\n[bold green]Successfully created {sfv_file}[/bold green]")
    else:
        print_header("VERIFY SFV")
        try:
            results = crc32.verify_sfv_file(sfv_file)
            table = Table(title=f"SFV Verification Results for {sfv_file}", show_header=True, header_style="bold magenta")
            table.add_column("Filename", style="dim", width=40)
            table.add_column("Status")
            table.add_column("Expected CRC32")
            table.add_column("Actual CRC32")

            for result in results:
                status = "[green]OK[/green]" if result['ok'] else "[red]FAIL[/red]"
                table.add_row(
                    result['file'],
                    status,
                    result['expected_crc'],
                    result.get('actual_crc', '-'),
                )
            console.print(table)
        except FileNotFoundError:
            ErrorHandler.show_error(f"SFV file not found: {sfv_file}")
        except IsADirectoryError:
            ErrorHandler.show_error("SFV file cannot be a directory.")


def main():
    """
    Program entry point: invoke the Click-based command-line interface.
    
    This function boots the CLI group (registered as the console entry point) and
    should be used as the package's main entry for command-line execution.
    """
    cli()

if __name__ == "__main__":
    main()
