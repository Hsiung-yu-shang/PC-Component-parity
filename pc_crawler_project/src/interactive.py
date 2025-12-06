from pchome_core import PChomeSpider
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

# 初始化 Rich Console
console = Console()

def display_table(keyword, products):
    """使用 Rich 建立美觀的終端機表格"""
    table = Table(title=f"搜尋結果: {keyword}", show_header=True, header_style="bold magenta")

    table.add_column("ID", style="cyan", width=12)
    table.add_column("品名", style="white")
    table.add_column("價格", justify="right", style="green")
    table.add_column("描述 (摘要)", style="dim", width=40)

    for p in products:
        # 擷取描述的前 30 個字
        desc_short = p['describe'].replace('\r\n', ' ')[:30] + "..."
        table.add_row(
            p['id'], 
            p['name'], 
            f"${p['price']:,}", 
            desc_short
        )

    console.print(table)

if __name__ == "__main__":
    spider = PChomeSpider()
    
    rprint(Panel.fit("[bold yellow]PC 零件比價系統 - 使用者查詢端[/bold yellow]\n[dim]Powered by Python & Rich[/dim]"))

    while True:
        try:
            keyword = console.input("\n[bold blue]請輸入零件關鍵字 (如 RTX4060, SSD) *q 離開*: [/bold blue]").strip()
            
            if keyword.lower() == 'q':
                rprint("[red]系統關閉[/red]")
                break
            if not keyword:
                continue

            products = []
            with console.status(f"[bold green]正在 PChome 搜尋 '{keyword}'...[/bold green]", spinner="dots"):
                # 主動搜尋通常只需要看第 1 頁
                for prod in spider.run(keyword, max_pages=1):
                    products.append(prod)
            
            if products:
                display_table(keyword, products)
                rprint(f"[bold]共找到 {len(products)} 筆商品[/bold]")
            else:
                rprint("[yellow]查無資料，請嘗試其他關鍵字[/yellow]")

        except KeyboardInterrupt:
            print("\n程式結束。")
            break