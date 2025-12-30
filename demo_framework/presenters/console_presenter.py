"""
Console Presenter for Live Demo Output.

Uses Rich library for beautiful terminal output during live demonstrations.
Supports pause points, narration, and formatted tables.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..scenarios.base import ScenarioStatus, StepResult, ScenarioResult, VerificationResult


class ConsolePresenter:
    """
    Rich terminal output presenter for live demos.

    Features:
    - Scenario announcements with panels
    - Step-by-step execution display
    - Verification results with expected/actual
    - Positions and queue tables
    - Pause points for live presentations
    - Auto mode for unattended runs

    Falls back to basic print() if Rich is not installed.
    """

    def __init__(
        self,
        auto_mode: bool = False,
        pause_delay: float = 2.0,
        verbose: bool = True,
    ):
        """
        Initialize the presenter.

        Args:
            auto_mode: If True, don't wait for user input at pause points
            pause_delay: Seconds to wait in auto mode at pause points
            verbose: If True, show detailed output
        """
        self.auto_mode = auto_mode
        self.pause_delay = pause_delay
        self.verbose = verbose

        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None

    def _print(self, *args, **kwargs):
        """Print using Rich console or fallback to print()."""
        if self.console:
            self.console.print(*args, **kwargs)
        else:
            # Strip Rich markup for basic print
            text = " ".join(str(a) for a in args)
            # Very basic markup removal
            import re
            text = re.sub(r'\[/?[^\]]+\]', '', text)
            print(text)

    # -------------------------------------------------------------------------
    # Scenario Lifecycle
    # -------------------------------------------------------------------------

    def announce_scenario(self, id: str, name: str, description: str):
        """Announce a new scenario with a prominent panel."""
        self._print()

        if RICH_AVAILABLE:
            content = f"[bold cyan]{id}[/]: [bold white]{name}[/]\n\n{description}"
            self.console.print(Panel(
                content,
                title="[bold yellow]SCENARIO[/]",
                border_style="cyan",
                padding=(1, 2),
            ))
        else:
            print("\n" + "=" * 70)
            print(f"  SCENARIO: {id} - {name}")
            print("=" * 70)
            print(f"  {description}")
            print("=" * 70)

        self._print()

    def announce_phase(self, phase_num: int, name: str):
        """Announce a demo phase."""
        self._print()

        if RICH_AVAILABLE:
            self.console.print(Panel(
                f"[bold white]{name}[/]",
                title=f"[bold magenta]PHASE {phase_num}[/]",
                border_style="magenta",
                padding=(0, 2),
            ))
        else:
            print(f"\n{'=' * 70}")
            print(f"  PHASE {phase_num}: {name}")
            print(f"{'=' * 70}")

        self._print()

    def show_scenario_result(self, result: ScenarioResult):
        """Show the final result of a scenario."""
        self._print()

        if result.status == ScenarioStatus.PASSED:
            status_text = "[bold green]PASSED[/]"
            border_style = "green"
        elif result.status == ScenarioStatus.FAILED:
            status_text = "[bold red]FAILED[/]"
            border_style = "red"
        else:
            status_text = f"[bold yellow]{result.status.value.upper()}[/]"
            border_style = "yellow"

        if RICH_AVAILABLE:
            content = f"{status_text}\n\nDuration: {result.duration_ms:.0f}ms"
            if result.error:
                content += f"\n\n[red]Error: {result.error[:200]}[/]"
            self.console.print(Panel(
                content,
                title=f"[bold]{result.id}[/]",
                border_style=border_style,
                padding=(0, 2),
            ))
        else:
            status = result.status.value.upper()
            print(f"\n--- {result.id}: {status} ({result.duration_ms:.0f}ms) ---")
            if result.error:
                print(f"Error: {result.error[:200]}")

    # -------------------------------------------------------------------------
    # Steps and Verifications
    # -------------------------------------------------------------------------

    def narrate(self, text: str):
        """Narrator voice - explains what's happening."""
        if self.verbose:
            self._print(f"[dim italic]  {text}[/]")

    def start_step(self, name: str):
        """Show step starting."""
        self._print(f"\n[bold yellow]  > {name}[/]")

    def end_step(self, result: StepResult):
        """Show step result."""
        if result.status == ScenarioStatus.PASSED:
            self._print(f"    [green]{result.name}[/] [dim]({result.duration_ms:.0f}ms)[/]")
        else:
            self._print(f"    [red]{result.name}[/] - {result.message}")

    def show_verification(
        self,
        name: str,
        status: ScenarioStatus,
        expected: str,
        actual: str,
    ):
        """Show verification result."""
        icon = "" if status == ScenarioStatus.PASSED else ""
        color = "green" if status == ScenarioStatus.PASSED else "red"
        self._print(f"    [{color}]{icon}[/] {name}")
        if self.verbose or status != ScenarioStatus.PASSED:
            self._print(f"      [dim]expected: {expected}[/]")
            self._print(f"      [dim]actual:   {actual}[/]")

    # -------------------------------------------------------------------------
    # Data Display
    # -------------------------------------------------------------------------

    def show_api_response(self, response: Dict[str, Any], title: str = "API Response"):
        """Show API response in formatted panel."""
        if not self.verbose:
            return

        formatted = json.dumps(response, indent=2, default=str)
        # Truncate if too long
        if len(formatted) > 500:
            formatted = formatted[:500] + "\n..."

        if RICH_AVAILABLE:
            self.console.print(Panel(
                formatted,
                title=title,
                border_style="dim",
            ))
        else:
            print(f"\n--- {title} ---")
            print(formatted)
            print("---")

    def show_positions_table(self, positions: List[Dict]):
        """Show positions in formatted table."""
        if not positions:
            self._print("[dim]  No active positions[/]")
            return

        if RICH_AVAILABLE:
            table = Table(title="Active Positions", show_header=True)
            table.add_column("Symbol", style="cyan")
            table.add_column("Side")
            table.add_column("Pyramids", justify="right")
            table.add_column("Status")
            table.add_column("PnL %", justify="right")
            table.add_column("Risk Eligible")

            for pos in positions:
                pnl = float(pos.get("unrealized_pnl_percent", 0) or 0)
                pnl_style = "green" if pnl >= 0 else "red"
                risk_eligible = "" if pos.get("risk_eligible") else ""

                table.add_row(
                    pos.get("symbol", "N/A"),
                    pos.get("side", "N/A"),
                    str(pos.get("pyramid_count", 0)),
                    pos.get("status", "N/A"),
                    f"[{pnl_style}]{pnl:.2f}%[/]",
                    risk_eligible,
                )

            self.console.print(table)
        else:
            print("\n  Positions:")
            for pos in positions:
                pnl = float(pos.get('unrealized_pnl_percent', 0) or 0)
                print(f"    {pos.get('symbol')} | {pos.get('status')} | PnL: {pnl:.2f}%")

    def show_queue_table(self, queue: List[Dict]):
        """Show queue in formatted table."""
        if not queue:
            self._print("[dim]  Queue is empty[/]")
            return

        if RICH_AVAILABLE:
            table = Table(title="Queued Signals", show_header=True)
            table.add_column("Symbol", style="cyan")
            table.add_column("Side")
            table.add_column("Priority", justify="right")
            table.add_column("Replacements", justify="right")
            table.add_column("Status")

            for sig in queue:
                # Convert priority_score to float (may be string/Decimal from API)
                priority = float(sig.get('priority_score', 0) or 0)
                table.add_row(
                    sig.get("symbol", "N/A"),
                    sig.get("side", "N/A"),
                    f"{priority:.2f}",
                    str(sig.get("replacement_count", 0)),
                    sig.get("status", "N/A"),
                )

            self.console.print(table)
        else:
            print("\n  Queue:")
            for sig in queue:
                priority = float(sig.get('priority_score', 0) or 0)
                print(f"    {sig.get('symbol')} | Priority: {priority:.2f}")

    def show_orders_table(self, orders: List[Dict], title: str = "Orders"):
        """Show orders in formatted table."""
        if not orders:
            self._print(f"[dim]  No {title.lower()}[/]")
            return

        if RICH_AVAILABLE:
            table = Table(title=title, show_header=True)
            table.add_column("Symbol", style="cyan")
            table.add_column("Side")
            table.add_column("Type")
            table.add_column("Price", justify="right")
            table.add_column("Qty", justify="right")
            table.add_column("Status")

            for order in orders[:15]:  # Limit display
                # Convert price/quantity to float (may be string/Decimal from API)
                price = float(order.get('price', 0) or 0)
                qty = float(order.get('quantity', 0) or 0)
                table.add_row(
                    order.get("symbol", "N/A"),
                    order.get("side", "N/A"),
                    order.get("type", "N/A"),
                    f"{price:.4f}",
                    f"{qty:.6f}",
                    order.get("status", "N/A"),
                )

            self.console.print(table)
        else:
            print(f"\n  {title}:")
            for order in orders[:15]:
                print(f"    {order.get('symbol')} | {order.get('side')} | {order.get('status')}")

    # -------------------------------------------------------------------------
    # Messages
    # -------------------------------------------------------------------------

    def show_success(self, message: str):
        """Show success message."""
        self._print(f"[green]  {message}[/]")

    def show_error(self, message: str):
        """Show error message."""
        self._print(f"[red]  {message}[/]")

    def show_warning(self, message: str):
        """Show warning message."""
        self._print(f"[yellow]  {message}[/]")

    def show_info(self, message: str):
        """Show info message."""
        self._print(f"[blue]  {message}[/]")

    # -------------------------------------------------------------------------
    # Pause and Interaction
    # -------------------------------------------------------------------------

    def pause_for_audience(self, message: str = "Press Enter to continue..."):
        """Pause for live demo audience."""
        if self.auto_mode:
            import time
            self._print(f"[dim]  (Auto-continuing in {self.pause_delay}s...)[/]")
            time.sleep(self.pause_delay)
        else:
            self._print(f"\n[bold yellow]  {message}[/]")
            input()

    async def async_pause(self, message: str = "Press Enter to continue..."):
        """Async version of pause for audience."""
        if self.auto_mode:
            self._print(f"[dim]  (Auto-continuing in {self.pause_delay}s...)[/]")
            await asyncio.sleep(self.pause_delay)
        else:
            self._print(f"\n[bold yellow]  {message}[/]")
            await asyncio.get_event_loop().run_in_executor(None, input)

    def show_countdown(self, seconds: int, message: str = "Waiting"):
        """Show a countdown timer."""
        import time
        for remaining in range(seconds, 0, -1):
            self._print(f"[dim]  {message}: {remaining}s remaining...[/]", end="\r")
            time.sleep(1)
        self._print(" " * 50, end="\r")  # Clear line

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------

    def show_demo_summary(self, results: List[ScenarioResult]):
        """Show summary of all scenario results."""
        passed = sum(1 for r in results if r.status == ScenarioStatus.PASSED)
        failed = sum(1 for r in results if r.status == ScenarioStatus.FAILED)
        skipped = sum(1 for r in results if r.status == ScenarioStatus.SKIPPED)
        total_time = sum(r.duration_ms for r in results)

        self._print()

        if RICH_AVAILABLE:
            summary = f"[green] Passed: {passed}[/]\n"
            summary += f"[red] Failed: {failed}[/]\n"
            if skipped:
                summary += f"[yellow] Skipped: {skipped}[/]\n"
            summary += f"\n[dim]Total time: {total_time/1000:.1f}s[/]"

            border = "green" if failed == 0 else "red"
            self.console.print(Panel(
                summary,
                title="[bold]Demo Summary[/]",
                border_style=border,
                padding=(1, 2),
            ))
        else:
            print("\n" + "=" * 50)
            print("  DEMO SUMMARY")
            print("=" * 50)
            print(f"  Passed:  {passed}")
            print(f"  Failed:  {failed}")
            print(f"  Skipped: {skipped}")
            print(f"  Time:    {total_time/1000:.1f}s")
            print("=" * 50)

        # Show failed scenarios
        if failed > 0:
            self._print("\n[bold red]Failed Scenarios:[/]")
            for r in results:
                if r.status == ScenarioStatus.FAILED:
                    self._print(f"  - {r.id}: {r.name}")
                    if r.error:
                        self._print(f"    [dim]{r.error[:100]}...[/]")
