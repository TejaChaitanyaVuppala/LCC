import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.syntax import Syntax
    HAS_RICH = True
    console = Console()
except ImportError:
    HAS_RICH = False
    class DummyConsole:
        def print(self, *args, **kwargs):
            if args:
                # Basic string conversion
                msg = str(args[0])
                # Strip simple rich formatting tags for fallback
                for tag in ["[bold cyan]", "[/bold cyan]", "[bold green]", "[/bold green]",
                            "[bold yellow]", "[/bold yellow]", "[bold red]", "[/bold red]",
                            "[bold magenta]", "[/bold magenta]", "[italic cyan]", "[/italic cyan]",
                            "[green]", "[yellow]", "[red]", "[/]", "[bold]", "[/bold]"]:
                    msg = msg.replace(tag, "")
                print(msg)
            else:
                print()
    console = DummyConsole()

def log_info(message: str):
    if HAS_RICH:
        console.print(f"[bold cyan]ℹ [INFO][/bold cyan] {message}")
    else:
        print(f"ℹ [INFO] {message}")

def log_success(message: str):
    if HAS_RICH:
        console.print(f"[bold green]✔ [SUCCESS][/bold green] {message}")
    else:
        print(f"✔ [SUCCESS] {message}")

def log_warning(message: str):
    if HAS_RICH:
        console.print(f"[bold yellow]⚠ [WARNING][/bold yellow] {message}")
    else:
        print(f"⚠ [WARNING] {message}")

def log_error(message: str):
    if HAS_RICH:
        console.print(f"[bold red]✖ [ERROR][/bold red] {message}")
    else:
        print(f"✖ [ERROR] {message}", file=sys.stderr)

def print_banner():
    if HAS_RICH:
        banner_text = Text()
        banner_text.append("🚀 LeetCode Daily Streak Bot\n", style="bold magenta")
        banner_text.append("Autonomous Daily Problem Solver powered by Gemini AI", style="italic cyan")
        console.print(Panel(banner_text, border_style="bright_blue", expand=False))
    else:
        print("=" * 60)
        print("🚀 LeetCode Daily Streak Bot")
        print("Autonomous Daily Problem Solver powered by Gemini AI")
        print("=" * 60)
