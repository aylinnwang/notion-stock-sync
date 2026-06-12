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

        response = requests.post(url, headers=HEADERS, json=payload)

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


def get_stock_map():
    df = ak.stock_zh_a_spot_em()
    stock_map = {}

    print("AkShare字段：", list(df.columns))

    for _, row in df.iterrows():
        code = str(row["代码"]).zfill(6)

        price = safe_float(row["最新价"])
        pct = safe_float(row["涨跌幅"])

        stock_map[code] = {
            "name": row["名称"],
            "price": price,
            "pct": pct,
        }

    return stock_map


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

    response = requests.patch(url, headers=HEADERS, json=payload)

    if response.status_code != 200:
        print("更新页面失败：", response.status_code)
        print(response.text)
        raise Exception("Notion page update failed")


def main():
    print("开始同步A股数据")

    pages = query_database()
    print(f"Notion股票数量：{len(pages)}")

    stock_map = get_stock_map()

    for page in pages:
        props = page["properties"]

        code_rich_text = props["股票代码"]["rich_text"]

        if len(code_rich_text) == 0:
            print("跳过：股票代码为空")
            continue

        code = code_rich_text[0]["plain_text"].strip().zfill(6)

        if code not in stock_map:
            print(f"未找到股票代码：{code}")
            continue

        data = stock_map[code]

        update_page(
            page_id=page["id"],
            price=data["price"],
            pct=data["pct"]
        )

        print(
            f"已更新：{code} {data['name']} "
            f"当前价：{data['price']} 涨幅：{data['pct']}%"
        )

    print("同步完成")


if __name__ == "__main__":
    main()
