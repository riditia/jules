from rich.console import Console
from rich.table import Table

console = Console()

def display_indicators(indicators):
    """
    Displays the technical indicators in a table.
    """
    table = Table(title="Technical Indicators (NIFTY 50)")
    table.add_column("Indicator", style="cyan")
    table.add_column("1H", style="magenta")
    table.add_column("1D", style="magenta")

    for indicator, values in indicators.items():
        table.add_row(indicator, f"{values['1H']:.2f}", f"{values['1D']:.2f}")

    console.print(table)

def display_positions(positions):
    """
    Displays the open positions in a table.
    """
    table = Table(title="Open Positions")
    table.add_column("Scrip Name", style="cyan")
    table.add_column("P/L (%)", style="magenta")

    for position in positions:
        table.add_row(position['symbol'], f"{position['pnl_percentage']:.2f}%")

    console.print(table)

def display_funds(funds):
    """
    Displays the available funds.
    """
    console.print(f"[bold green]Available Funds:[/] [yellow]₹{funds.get('availableBalance', 0.0):.2f}[/]")
