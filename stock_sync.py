import os
from datetime import datetime

import akshare as ak
import requests


NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def query_database():
    results = []
    start_cursor = None

    while True:
        url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
        payload = {}

        if start_cursor:
            payload["start_cursor"] = start_cursor

        response = requests.post(url, headers=HEADERS, json=payload, timeout=20)

        if response.status_code != 200:
            print("查询数据库失败：", response.status_code)
            print(response.text)
            raise Exception("Notion database query failed")

        data = response.json()
        results.extend(data["results"])

        if not data.get("has_more"):
            break

        start_cursor = data.get("next_cursor")

    return results


def safe_float(value):
    try:
        if value is None:
            return 0
        value = str(value).replace(",", "").strip()
        if value in ["", "-", "nan", "None"]:
            return 0
        return float(value)
    except Exception:
        return 0


def get_stock_data_by_code(code):
    try:
        df = ak.stock_bid_ask_em(symbol=code)

        data = {}
        for _, row in df.iterrows():
            item = str(row.get("item", "")).strip()
            value = row.get("value", "")
            data[item] = value

        price = safe_float(data.get("最新", 0))
        pct = safe_float(data.get("涨幅", 0))

        return {
            "price": price,
            "pct": pct
        }

    except Exception as e:
        print(f"获取股票失败：{code}，原因：{e}")
        return None


def update_page(page_id, price, pct):
    url = f"https://api.notion.com/v1/pages/{page_id}"

    payload = {
        "properties": {
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
    }

    response = requests.patch(url, headers=HEADERS, json=payload, timeout=20)

    if response.status_code != 200:
        print("更新页面失败：", response.status_code)
        print(response.text)
        raise Exception("Notion page update failed")


def main():
    print("开始同步A股数据")

    pages = query_database()
    print(f"Notion股票数量：{len(pages)}")

    for page in pages:
        props = page["properties"]

        code_rich_text = props["股票代码"]["rich_text"]

        if len(code_rich_text) == 0:
            print("跳过：股票代码为空")
            continue

        code = code_rich_text[0]["plain_text"].strip().zfill(6)

        stock_data = get_stock_data_by_code(code)

        if stock_data is None:
            print(f"跳过更新：{code}")
            continue

        price = stock_data["price"]
        pct = stock_data["pct"]

        update_page(
            page_id=page["id"],
            price=price,
            pct=pct
        )

        if pct > 0:
            direction = "🔴上涨"
        elif pct < 0:
            direction = "🟢下跌"
        else:
            direction = "⚪平盘"

        print(f"已更新：{code} 当前价：{price} 涨幅：{pct}% {direction}")

    print("同步完成")


if __name__ == "__main__":
    main()
