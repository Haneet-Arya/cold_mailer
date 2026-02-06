"""Click CLI commands for Cold Mailer."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .config import Config, get_config
from .exceptions import (
    ColdMailerError,
    DuplicateRecruiterError,
    RecruiterNotFoundError,
    TemplateError,
)
from .mailer import Mailer
from .rate_limiter import RateLimiter
from .recruiter_manager import RecruiterManager
from .template_engine import TemplateEngine, create_default_templates
from .validators import parse_custom_fields, validate_data_format

console = Console()


def get_project_root() -> Path:
    """Get project root directory."""
    return Path.cwd()


@click.group()
@click.version_option(version="1.0.0", prog_name="cold-mailer")
@click.pass_context
def cli(ctx):
    """Cold Mailer CLI - Send personalized cold emails to recruiters."""
    ctx.ensure_object(dict)
    ctx.obj["root"] = get_project_root()


@cli.command()
@click.option(
    "--format",
    "data_format",
    type=click.Choice(["csv", "json"]),
    default="csv",
    help="Data format for recruiter storage.",
)
@click.pass_context
def init(ctx, data_format):
    """Initialize project directories and sample files."""
    root = ctx.obj["root"]

    directories = ["templates", "data", "attachments", "logs", "config"]

    console.print("\n[bold]Initializing Cold Mailer...[/bold]\n")

    for dir_name in directories:
        dir_path = root / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        console.print(f"  [green]✓[/green] Created {dir_name}/")

    gitkeep_dirs = ["data", "attachments", "logs"]
    for dir_name in gitkeep_dirs:
        gitkeep = root / dir_name / ".gitkeep"
        gitkeep.touch()

    config_path = root / "config" / "config.yaml"
    if not config_path.exists():
        from .config import Config as ConfigClass

        config = ConfigClass(root)
        config.set_data_format(data_format)
        console.print(f"  [green]✓[/green] Created config/config.yaml")
    else:
        console.print(f"  [yellow]~[/yellow] config/config.yaml already exists")

    templates_path = root / "templates"
    existing_templates = list(templates_path.glob("*.j2"))
    if not existing_templates:
        create_default_templates(templates_path)
        console.print(f"  [green]✓[/green] Created default templates")
    else:
        console.print(f"  [yellow]~[/yellow] Templates already exist")

    config = get_config(root)
    manager = RecruiterManager(config)

    data_file = root / "data" / f"recruiters.{data_format}"
    if not data_file.exists():
        manager.create_sample_data(data_format)
        console.print(f"  [green]✓[/green] Created sample recruiters.{data_format}")
    else:
        console.print(f"  [yellow]~[/yellow] recruiters.{data_format} already exists")

    env_file = root / ".env"
    if not env_file.exists():
        console.print(f"\n  [yellow]![/yellow] Remember to create .env file with Gmail credentials")
        console.print(f"    See .env.example for template")

    console.print("\n[bold green]Initialization complete![/bold green]\n")
    console.print("Next steps:")
    console.print("  1. Copy .env.example to .env and add your Gmail credentials")
    console.print("  2. Edit config/config.yaml with your sender information")
    console.print("  3. Add recruiters: [cyan]cold-mailer add recruiter[/cyan]")
    console.print("  4. Test connection: [cyan]cold-mailer config test-smtp[/cyan]")
    console.print("  5. Send emails: [cyan]cold-mailer send --all[/cyan]")


@cli.group()
def send():
    """Send emails to recruiters."""
    pass


@send.command("all")
@click.option("-t", "--template", default=None, help="Template to use.")
@click.option("--custom", default="", help="Custom variables (key=value,key2=value2).")
@click.option("--dry-run", is_flag=True, help="Preview without sending.")
@click.pass_context
def send_all(ctx, template, custom, dry_run):
    """Send emails to all pending recruiters."""
    root = ctx.obj["root"]
    config = get_config(root)

    try:
        custom_vars = parse_custom_fields(custom) if custom else None
        mailer = Mailer(config)
        manager = RecruiterManager(config)

        pending = manager.get_pending()
        if not pending:
            console.print("[yellow]No pending recruiters to email.[/yellow]")
            return

        template_name = template or config.app.email.default_template
        engine = TemplateEngine(config)

        if not engine.template_exists(template_name):
            console.print(f"[red]Template '{template_name}' not found.[/red]")
            console.print(f"Available templates: {', '.join(engine.list_templates())}")
            sys.exit(1)

        console.print(f"\n[bold]Sending to {len(pending)} pending recruiter(s)...[/bold]")
        if dry_run:
            console.print("[yellow](DRY RUN - no emails will be sent)[/yellow]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Sending...", total=len(pending))

            def update_progress(current, total, recruiter):
                progress.update(
                    task,
                    description=f"[{current}/{total}] {recruiter.email}",
                    completed=current,
                )

            results = mailer.send_to_all_pending(
                template_name=template_name,
                custom_vars=custom_vars,
                dry_run=dry_run,
                progress_callback=update_progress,
            )

        console.print(f"\n[bold]Results:[/bold]")
        console.print(f"  Sent: [green]{results['sent']}[/green]")
        console.print(f"  Failed: [red]{results['failed']}[/red]")
        console.print(f"  Skipped (rate limit): [yellow]{results['skipped']}[/yellow]")

        if results["errors"]:
            console.print("\n[bold red]Errors:[/bold red]")
            for error in results["errors"]:
                console.print(f"  {error['email']}: {error['error']}")

    except ColdMailerError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@send.command("to")
@click.option("-r", "--recruiter", required=True, help="Recruiter email address.")
@click.option("-t", "--template", default=None, help="Template to use.")
@click.option("--custom", default="", help="Custom variables (key=value,key2=value2).")
@click.option("--dry-run", is_flag=True, help="Preview without sending.")
@click.pass_context
def send_to(ctx, recruiter, template, custom, dry_run):
    """Send email to a specific recruiter."""
    root = ctx.obj["root"]
    config = get_config(root)

    try:
        custom_vars = parse_custom_fields(custom) if custom else None
        manager = RecruiterManager(config)
        mailer = Mailer(config)

        try:
            rec = manager.get_by_email(recruiter)
        except RecruiterNotFoundError:
            console.print(f"[red]Recruiter with email '{recruiter}' not found.[/red]")
            sys.exit(1)

        template_name = template or config.app.email.default_template
        engine = TemplateEngine(config)

        if not engine.template_exists(template_name):
            console.print(f"[red]Template '{template_name}' not found.[/red]")
            sys.exit(1)

        if dry_run:
            preview = mailer.preview_email(rec, template_name, custom_vars)
            console.print(preview)
            return

        console.print(f"Sending to {rec.email}...")

        success, message = mailer.send_email(rec, template_name, custom_vars)

        if success:
            console.print(f"[green]{message}[/green]")
        else:
            console.print(f"[red]{message}[/red]")
            sys.exit(1)

    except ColdMailerError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.group("list")
def list_cmd():
    """List templates or recruiters."""
    pass


@list_cmd.command("templates")
@click.pass_context
def list_templates(ctx):
    """List available email templates."""
    root = ctx.obj["root"]
    config = get_config(root)
    engine = TemplateEngine(config)

    templates = engine.list_templates()

    if not templates:
        console.print("[yellow]No templates found.[/yellow]")
        console.print(f"Run [cyan]cold-mailer init[/cyan] to create default templates.")
        return

    table = Table(title="Available Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="dim")

    for name in templates:
        path = engine.get_template_path(name)
        table.add_row(name, str(path.relative_to(root)))

    console.print(table)


@list_cmd.command("recruiters")
@click.option("--status", type=click.Choice(["all", "pending", "sent", "replied", "bounced"]), default="all")
@click.pass_context
def list_recruiters(ctx, status):
    """List recruiters."""
    root = ctx.obj["root"]
    config = get_config(root)
    manager = RecruiterManager(config)

    if status == "all":
        recruiters = manager.get_all()
    else:
        recruiters = manager.get_by_status(status)

    if not recruiters:
        console.print(f"[yellow]No recruiters found{' with status ' + status if status != 'all' else ''}.[/yellow]")
        return

    table = Table(title=f"Recruiters ({status})")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Email")
    table.add_column("Company")
    table.add_column("Status")
    table.add_column("Last Contacted", style="dim")

    status_colors = {
        "pending": "yellow",
        "sent": "blue",
        "replied": "green",
        "bounced": "red",
    }

    for r in recruiters:
        status_style = status_colors.get(r.status, "white")
        last_contacted = r.last_contacted.strftime("%Y-%m-%d") if r.last_contacted else "-"
        table.add_row(
            r.id,
            r.get_full_name(),
            r.email,
            r.company,
            f"[{status_style}]{r.status}[/{status_style}]",
            last_contacted,
        )

    console.print(table)


@cli.group("add")
def add_cmd():
    """Add new data."""
    pass


@add_cmd.command("recruiter")
@click.option("--email", prompt="Email", help="Recruiter email address.")
@click.option("--first-name", prompt="First name", help="First name.")
@click.option("--last-name", prompt="Last name", default="", help="Last name.")
@click.option("--company", prompt="Company", help="Company name.")
@click.option("--title", prompt="Title (Mr./Ms./Dr./Prof.)", default="", help="Honorific title.")
@click.option("--job-title", prompt="Job title applying for", default="", help="Position applying for.")
@click.option("--greeting-style", type=click.Choice(["formal", "semi_formal", "casual", "professional"]), default="semi_formal", prompt="Greeting style")
@click.pass_context
def add_recruiter(ctx, email, first_name, last_name, company, title, job_title, greeting_style):
    """Add a new recruiter interactively."""
    root = ctx.obj["root"]
    config = get_config(root)
    manager = RecruiterManager(config)

    try:
        recruiter = manager.add(
            email=email,
            first_name=first_name,
            last_name=last_name,
            company=company,
            title=title if title else None,
            job_title=job_title,
            greeting_style=greeting_style,
        )

        console.print(f"\n[green]Recruiter added successfully![/green]")
        console.print(f"  ID: {recruiter.id}")
        console.print(f"  Name: {recruiter.get_full_name()}")
        console.print(f"  Email: {recruiter.email}")
        console.print(f"  Company: {recruiter.company}")

    except DuplicateRecruiterError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except ColdMailerError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.group("config")
def config_cmd():
    """Configuration commands."""
    pass


@config_cmd.command("test-smtp")
@click.pass_context
def test_smtp(ctx):
    """Test SMTP connection to Gmail."""
    root = ctx.obj["root"]
    config = get_config(root)
    mailer = Mailer(config)

    console.print("\n[bold]Testing SMTP connection...[/bold]")

    success, message = mailer.test_connection()

    if success:
        console.print(f"[green]✓ {message}[/green]")
    else:
        console.print(f"[red]✗ {message}[/red]")
        sys.exit(1)


@config_cmd.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx, key, value):
    """Set a configuration value."""
    root = ctx.obj["root"]
    config = get_config(root)

    if key == "data_format":
        try:
            value = validate_data_format(value)
            config.set_data_format(value)
            console.print(f"[green]Set data_format to '{value}'[/green]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
    else:
        console.print(f"[yellow]Unknown config key: {key}[/yellow]")
        console.print("Available keys: data_format")


@cli.command()
@click.pass_context
def status(ctx):
    """Show statistics and status."""
    root = ctx.obj["root"]
    config = get_config(root)

    manager = RecruiterManager(config)
    rate_limiter = RateLimiter(config)

    recruiter_stats = manager.get_statistics()
    rate_stats = rate_limiter.get_statistics()

    console.print("\n")

    recruiter_table = Table(title="Recruiter Statistics", box=None)
    recruiter_table.add_column("Metric", style="cyan")
    recruiter_table.add_column("Value", justify="right")

    recruiter_table.add_row("Total Recruiters", str(recruiter_stats["total"]))
    recruiter_table.add_row("Pending", f"[yellow]{recruiter_stats['pending']}[/yellow]")
    recruiter_table.add_row("Sent", f"[blue]{recruiter_stats['sent']}[/blue]")
    recruiter_table.add_row("Replied", f"[green]{recruiter_stats['replied']}[/green]")
    recruiter_table.add_row("Bounced", f"[red]{recruiter_stats['bounced']}[/red]")

    console.print(recruiter_table)
    console.print()

    rate_table = Table(title="Rate Limiting", box=None)
    rate_table.add_column("Metric", style="cyan")
    rate_table.add_column("Value", justify="right")

    rate_table.add_row(
        "Hourly",
        f"{rate_stats['emails_last_hour']}/{rate_stats['hourly_limit']} ({rate_stats['hourly_remaining']} remaining)"
    )
    rate_table.add_row(
        "Daily",
        f"{rate_stats['emails_today']}/{rate_stats['daily_limit']} ({rate_stats['daily_remaining']} remaining)"
    )
    rate_table.add_row("Total Sent (all time)", str(rate_stats["total_sent"]))
    rate_table.add_row("Delay Between Emails", f"{rate_stats['delay_between_emails']}s")

    console.print(rate_table)
    console.print()

    recent = rate_limiter.get_sent_history(5)
    if recent:
        history_table = Table(title="Recent Sent Emails", box=None)
        history_table.add_column("Time", style="dim")
        history_table.add_column("Email")
        history_table.add_column("Template")

        for entry in recent:
            from datetime import datetime
            ts = datetime.fromisoformat(entry["timestamp"])
            history_table.add_row(
                ts.strftime("%Y-%m-%d %H:%M"),
                entry["email"],
                entry["template"],
            )

        console.print(history_table)


@cli.command()
@click.option("--to", "target_format", type=click.Choice(["csv", "json"]), required=True, help="Target format.")
@click.pass_context
def convert(ctx, target_format):
    """Convert recruiter data between CSV and JSON formats."""
    root = ctx.obj["root"]
    config = get_config(root)
    manager = RecruiterManager(config)

    console.print(f"\n[bold]Converting to {target_format.upper()} format...[/bold]")

    try:
        output_path = manager.convert_format(target_format)
        console.print(f"[green]✓ Converted successfully![/green]")
        console.print(f"  Output: {output_path.relative_to(root)}")

        if click.confirm(f"\nSet {target_format} as the default data format?"):
            config.set_data_format(target_format)
            console.print(f"[green]✓ Default format set to {target_format}[/green]")

    except ColdMailerError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
@click.option("--port", default=8000, type=int, help="Port to bind to.")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development.")
@click.pass_context
def serve(ctx, host, port, reload):
    """Start the web server."""
    try:
        import uvicorn
        from .web.app import create_app
    except ImportError:
        console.print("[red]Error: Web dependencies not installed.[/red]")
        console.print("Install them with: [cyan]uv pip install -e .[/cyan]")
        sys.exit(1)

    root = ctx.obj["root"]
    console.print(f"\n[bold]Starting Cold Mailer Web UI...[/bold]")
    console.print(f"  URL: [cyan]http://{host}:{port}[/cyan]")
    console.print(f"  Project root: {root}")
    if reload:
        console.print(f"  Auto-reload: [green]enabled[/green]")
    console.print("\nPress Ctrl+C to stop.\n")

    # Create app with project root
    app = create_app(root)

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    cli()
