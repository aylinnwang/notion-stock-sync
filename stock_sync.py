import os
from datetime import datetime
import akshare as ak
from notion_client import Client

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

notion = Client(auth=NOTION_TOKEN)

def query_database():
    results = []
    start_cursor = None

    while True:
        payload = {"database_id": DATABASE_ID}
        if start_cursor:
            payload["start_cursor"] = start_cursor

        response = notion.data_sources.query(**payload)
        results.extend(response["results"])

        if not response.get("has_more"):
            break
        start_cursor = response.get("next_cursor")

    return results

def get_stock_map():
    df = ak.stock_zh_a_spot_em()

    stock_map = {}
    for _, row in df.iterrows():
        code = str(row["代码"]).zfill(6)
        stock_map[code] = {
            "name": row["名称"],
            "price": float(row["最新价"]) if row["最新价"] != "-" else 0,
            "pct": float(row["涨跌幅"]) if row["涨跌幅"] != "-" else 0,
        }
    return stock_map

def update_page(page_id, price, pct):
    notion.pages.update(
        page_id=page_id,
        properties={
            "当前价格": {
                "number": price
            },
            "今日涨幅": {
                "number": pct
            },
            "更新日期": {
                "date": {
                    "start": datetime.now().isoformat()
                }
            }
        }
    )

def main():
    print("开始同步 A股数据")

    pages = query_database()
    stock_map = get_stock_map()

    for page in pages:
        props = page["properties"]

        code_text = props["股票代码"]["rich_text"]
        if not code_text:
            continue

        code = code_text[0]["plain_text"].strip().zfill(6)

        if code not in stock_map:
            print(f"未找到股票代码：{code}")
            continue

        data = stock_map[code]
        update_page(
            page_id=page["id"],
            price=data["price"],
            pct=data["pct"]
        )

        print(f"已更新：{code} {data['name']} {data['pct']}%")

    print("同步完成")

if __name__ == "__main__":
    main()
