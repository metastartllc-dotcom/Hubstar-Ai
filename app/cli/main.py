import typer
from rich.console import Console

app = typer.Typer(
    help="Hubstar AI - Барилгын төслийн удирдлага, төсвийн систем",
    invoke_without_command=True,
)
console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Hubstar AI CLI-г эхлүүлэх."""
    if ctx.invoked_subcommand is None:
        interactive()

def display_menu():
    console.print("\n[bold blue]--- Үндсэн цэс ---[/bold blue]")
    console.print("1. Төслийн мэдээлэл")
    console.print("2. Ажлын жагсаалт")
    console.print("3. Материалын жагсаалт")
    console.print("4. Ажил–материалын холбоос")
    console.print("5. Материалын үнэ")
    console.print("6. Ажлын хөлс")
    console.print("7. Машин механизм")
    console.print("8. Нэгдсэн төсөв")
    console.print("9. Нэмэлт материал")
    console.print("10. CSV тайлан гаргах")
    console.print("11. Давхар тооцооны хяналт")
    console.print("12. Төсөв баталгаажуулалт")
    console.print("13. Excel-ээр мэдээлэл, үнэ импортлох")
    console.print("14. Тээврийн зардал тооцох")
    console.print("15. Гарах")

@app.command()
def interactive():
    """Интерактив цэсээр ажиллах"""
    while True:
        display_menu()
        choice = typer.prompt("Сонголт хийнэ үү")
        
        if choice == "1":
            console.print("[green]Төслийн мэдээлэл цэс...[/green]")
        elif choice == "2":
            console.print("[green]Ажлын жагсаалт...[/green]")
        elif choice == "10":
            console.print("[green]CSV тайлан гаргаж байна...[/green]")
        elif choice == "13":
            console.print("[green]Excel импортлох цэс...[/green]")
        elif choice == "14":
            console.print("[green]Тээврийн зардал тооцох...[/green]")
        elif choice == "15":
            console.print("[yellow]Програмаас гарч байна. Баяртай![/yellow]")
            break
        else:
            console.print("[red]Буруу сонголт байна. Дахин оролдоно уу.[/red]")

if __name__ == "__main__":
    app()
