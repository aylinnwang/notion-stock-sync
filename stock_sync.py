import os
from datetime import datetime
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

        r = requests.post(url, headers=HEADERS, json=payload, timeout=20)
        data = r.json()

        if r.status_code != 200:
            print(data)
            raise Exception("查询Notion失败")

        results.extend(data["results"])

        if not data.get("has_more"):
            break

        start_cursor = data.get("next_cursor")

    return results


def safe_float(value):
    try:
        return float(value)
    except:
        return 0


def get_secid(code):
    if code.startswith("6"):
        return f"1.{code}"
    return f"0.{code}"


def get_stock_data(code):
    secid = get_secid(code)

    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "secid": secid,
        "fields": "f43,f57,f58,f169,f170"
    }

    r = requests.get(url, params=params, timeout=20)
    data = r.json().get("data", {})

    price = safe_float(data.get("f43", 0)) / 100
    pct = safe_float(data.get("f170", 0)) / 100

    return price, pct


def update_page(page_id, price, pct):
    if pct > 0:
        show = f"🔴 +{pct:.2f}%"
    elif pct < 0:
        show = f"🟢 {pct:.2f}%"
    else:
        show = f"⚪ {pct:.2f}%"

    payload = {
        "properties": {
            "当前价格": {
                "number": price
            },
            "今日涨幅": {
                "number": pct
            },
            "涨跌显示": {
                "rich_text": [
                    {
                        "text": {
                            "content": show
                        }
                    }
                ]
            },
            "更新日期": {
                "date": {
                    "start": datetime.now().isoformat()
                }
            }
        }
    }

    url = f"https://api.notion.com/v1/pages/{page_id}"
    r = requests.patch(url, headers=HEADERS, json=payload, timeout=20)

    if r.status_code != 200:
        print(r.text)
        raise Exception("更新Notion失败")


def main():
    print("开始同步A股数据")

    pages = query_database()

    for page in pages:
        props = page["properties"]

        code_text = props["股票代码"]["rich_text"]
        if not code_text:
            continue

        code = code_text[0]["plain_text"].strip().zfill(6)

        price, pct = get_stock_data(code)

        update_page(page["id"], price, pct)

        print(f"已更新 {code} 当前价:{price} 涨幅:{pct}%")

    print("同步完成")


if __name__ == "__main__":
    main()
