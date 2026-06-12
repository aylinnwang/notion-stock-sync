import os
import time
from datetime import datetime

import requests

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def query_database():

    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    response = requests.post(
        url,
        headers=NOTION_HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return response.json()["results"]


def get_market(code):

    code = str(code)

    if code.startswith(("6", "9")):
        return "sh"

    if code.startswith(("0", "2", "3")):
        return "sz"

    return "sh"


def get_stock_data(code):

    market = get_market(code)

    url = f"https://hq.sinajs.cn/list={market}{code}"

    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    response.encoding = "gbk"

    text = response.text

    if '="' not in text:
        return None

    data = text.split('="')[1].split('"')[0]

    arr = data.split(",")

    if len(arr) < 4:
        return None

    name = arr[0]

    yesterday = float(arr[2])

    current = float(arr[3])

    pct = round(
        (current - yesterday) / yesterday * 100,
        2
    )

    return {
        "name": name,
        "price": round(current, 2),
        "pct": pct
    }


def get_display_text(pct):

    if pct > 0:
        return f"💖 +{pct:.2f}%"

    if pct < 0:
        return f"💚 {pct:.2f}%"

    return f"🤍 {pct:.2f}%"


def update_page(page_id, price, pct):

    display_text = get_display_text(pct)

    url = f"https://api.notion.com/v1/pages/{page_id}"

    payload = {
        "properties": {

            "当前价格": {
                "number": price
            },

            "涨跌显示": {
                "rich_text": [
                    {
                        "text": {
                            "content": display_text
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

    response = requests.patch(
        url,
        headers=NOTION_HEADERS,
        json=payload,
        timeout=30
    )

    response.raise_for_status()


def main():

    print("开始同步")

    pages = query_database()

    print(f"股票数量: {len(pages)}")

    for page in pages:

        try:

            props = page["properties"]

            code_text = props["股票代码"]["rich_text"]

            if len(code_text) == 0:
                continue

            code = code_text[0]["plain_text"].strip()

            stock = get_stock_data(code)

            if not stock:
                print(f"{code} 获取失败")
                continue

            update_page(
                page["id"],
                stock["price"],
                stock["pct"]
            )

            print(
                f"{stock['name']} "
                f"{stock['price']} "
                f"{stock['pct']}%"
            )

            time.sleep(1)

        except Exception as e:

            print("更新失败")

            print(str(e))

    print("同步完成")


if __name__ == "__main__":
    main()
