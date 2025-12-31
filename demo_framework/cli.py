"""
CLI Entry Point for Demo Framework.

Provides command-line interface for running demo scenarios.
"""

import asyncio
import sys
from typing import Optional

try:
    import click
    CLICK_AVAILABLE = True
except ImportError:
    CLICK_AVAILABLE = False

from .runner import DemoRunner, ScenarioRegistry, run_demo
from .scenarios.base import DemoConfig


def load_scenarios():
    """Load all scenario modules to populate registry."""
    # Import scenario modules to trigger registration

    # Signal scenarios
    try:
        from .scenarios.signal import entry_scenarios
    except ImportError:
        pass

    try:
        from .scenarios.signal import pyramid_scenarios
    except ImportError:
        pass

    try:
        from .scenarios.signal import exit_scenarios
    except ImportError:
        pass

    # Queue scenarios
    try:
        from .scenarios.queue import operations_scenarios
    except ImportError:
        pass

    try:
        from .scenarios.queue import priority_scenarios
    except ImportError:
        pass

    # Risk scenarios
    try:
        from .scenarios.risk import validation_scenarios
    except ImportError:
        pass

    try:
        from .scenarios.risk import timer_offset_scenarios
    except ImportError:
        pass

    # Order Execution scenarios
    try:
        from .scenarios.order import execution_scenarios
    except ImportError:
        pass

    # Error Handling scenarios
    try:
        from .scenarios.error import handling_scenarios
    except ImportError:
        pass

    # Edge Case scenarios
    try:
        from .scenarios.edge import boundary_scenarios
    except ImportError:
        pass

    # Lifecycle scenarios
    try:
        from .scenarios.lifecycle import complete_scenarios
    except ImportError:
        pass

    # Configuration scenarios
    try:
        from .scenarios.config import validation_scenarios as config_validation
    except ImportError:
        pass


if CLICK_AVAILABLE:

    @click.group()
    @click.version_option(version="1.0.0")
    def cli():
        """Trading Engine Demo Framework - Scenario-based testing for live demos."""
        load_scenarios()

    @cli.command()
    @click.option(
        "--category", "-c",
        type=click.Choice([
            "signal", "queue", "risk",  # existing
            "order", "error", "edge", "lifecycle", "config",  # new
            "all"
        ]),
        default=None,
        help="Run all scenarios in category",
    )
    @click.option(
        "--scenario", "-s",
        type=str,
        default=None,
        help="Run specific scenario by ID (e.g., S-001)",
    )
    @click.option(
        "--auto", "-a",
        is_flag=True,
        help="Auto-continue without pauses",
    )
    @click.option(
        "--delay",
        type=float,
        default=2.0,
        help="Pause delay in auto mode (seconds)",
    )
    @click.option(
        "--clean/--no-clean",
        default=True,
        help="Reset to clean slate before running",
    )
    @click.option(
        "--username", "-u",
        type=str,
        default="zmomz",
        help="Demo user username",
    )
    @click.option(
        "--password", "-p",
        type=str,
        default="zm0mzzm0mz",
        help="Demo user password",
    )
    @click.option(
        "--engine-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="Trading engine URL",
    )
    @click.option(
        "--mock-url",
        type=str,
        default="http://127.0.0.1:9000",
        help="Mock exchange URL",
    )
    def run(
        category: Optional[str],
        scenario: Optional[str],
        auto: bool,
        delay: float,
        clean: bool,
        username: str,
        password: str,
        engine_url: str,
        mock_url: str,
    ):
        """Run demo scenarios."""
        config = DemoConfig(
            username=username,
            password=password,
            engine_url=engine_url,
            mock_exchange_url=mock_url,
            auto_mode=auto,
            pause_delay=delay,
        )

        if category == "all":
            category = None

        results = asyncio.run(run_demo(
            scenario_id=scenario,
            category=category,
            auto_mode=auto,
            clean_slate=clean,
            config=config,
        ))

        # Exit with error code if any failed
        failed = sum(1 for r in results if r.status.value == "failed")
        if failed:
            sys.exit(1)

    @cli.command("list")
    @click.option(
        "--category", "-c",
        type=str,
        default=None,
        help="Filter by category",
    )
    def list_scenarios(category: Optional[str]):
        """List all available scenarios."""
        scenarios = ScenarioRegistry.list_all()

        if category:
            scenarios = [s for s in scenarios if s["category"] == category]

        if not scenarios:
            click.echo("No scenarios found.")
            return

        # Group by category
        by_category = {}
        for s in scenarios:
            cat = s["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(s)

        for cat, cat_scenarios in sorted(by_category.items()):
            click.echo(f"\n{cat.upper()} ({len(cat_scenarios)} scenarios)")
            click.echo("-" * 50)
            for s in sorted(cat_scenarios, key=lambda x: x["id"]):
                click.echo(f"  {s['id']}: {s['name']}")

    @cli.command()
    @click.option("--auto", "-a", is_flag=True, help="Auto-continue")
    def quick(auto: bool):
        """Run quick smoke test (key scenarios from each category)."""
        config = DemoConfig(auto_mode=auto)

        async def _run():
            runner = DemoRunner(config=config, auto_mode=auto)
            try:
                if not await runner.setup():
                    return []
                results = await runner.run_quick_smoke()
                runner.show_summary()
                return results
            finally:
                await runner.cleanup()

        results = asyncio.run(_run())
        failed = sum(1 for r in results if r.status.value == "failed")
        if failed:
            sys.exit(1)

    @cli.command()
    def categories():
        """List all scenario categories."""
        cats = ScenarioRegistry.get_categories()
        if not cats:
            click.echo("No categories found. Scenarios may not be loaded.")
            return

        click.echo("Available categories:")
        for cat in sorted(cats):
            count = len(ScenarioRegistry.get_by_category(cat))
            click.echo(f"  {cat}: {count} scenarios")

else:
    # Fallback CLI without Click

    def cli():
        """Simple CLI fallback when Click is not installed."""
        import argparse

        parser = argparse.ArgumentParser(
            description="Trading Engine Demo Framework"
        )
        subparsers = parser.add_subparsers(dest="command")

        # Run command
        run_parser = subparsers.add_parser("run", help="Run demo scenarios")
        run_parser.add_argument("-c", "--category", help="Category to run")
        run_parser.add_argument("-s", "--scenario", help="Specific scenario ID")
        run_parser.add_argument("-a", "--auto", action="store_true")
        run_parser.add_argument("--username", default="zmomz")
        run_parser.add_argument("--password", default="zm0mzzm0mz")

        # List command
        subparsers.add_parser("list", help="List scenarios")

        # Quick command
        quick_parser = subparsers.add_parser("quick", help="Quick smoke test")
        quick_parser.add_argument("-a", "--auto", action="store_true")

        args = parser.parse_args()

        load_scenarios()

        if args.command == "run":
            config = DemoConfig(
                username=args.username,
                password=args.password,
                auto_mode=args.auto,
            )
            asyncio.run(run_demo(
                scenario_id=args.scenario,
                category=args.category if args.category != "all" else None,
                auto_mode=args.auto,
                config=config,
            ))

        elif args.command == "list":
            scenarios = ScenarioRegistry.list_all()
            for s in scenarios:
                print(f"{s['id']}: {s['name']} [{s['category']}]")

        elif args.command == "quick":
            config = DemoConfig(auto_mode=args.auto)

            async def _run():
                runner = DemoRunner(config=config, auto_mode=args.auto)
                try:
                    if not await runner.setup():
                        return
                    await runner.run_quick_smoke()
                    runner.show_summary()
                finally:
                    await runner.cleanup()

            asyncio.run(_run())

        else:
            parser.print_help()


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
