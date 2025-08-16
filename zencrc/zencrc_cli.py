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
        console.print("\n[red]❌ Error: No valid files found to process.[/red]")
        console.print("\nUse [green]-r[/green] flag to search recursively")
        console.print(
            "\nFor more information, run: [blue]zencrc --help[/blue]\n"
        )
        raise click.Abort()

    @staticmethod
    def show_error(message):
        console.print(f"\n[red]❌ Error: {message}[/red]")
        raise click.Abort()


def print_header(title: str) -> None:
    """Prints a styled header."""
    console.rule(f"[bold green]{title}[/bold green]")


def expand_and_filter_files(
    paths: Tuple[str, ...], recurse: bool
) -> List[Path]:
    """Expands directories and filters out non-files."""
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
    """Processes files with a progress bar."""
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
    """Creates a table for displaying results."""
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
    """Verify CRC32 checksums in filenames."""
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
    """Append CRC32 checksums to filenames."""
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
    """Create or verify SFV files."""
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
    """CLI entry point."""
    cli()

if __name__ == "__main__":
    main()
