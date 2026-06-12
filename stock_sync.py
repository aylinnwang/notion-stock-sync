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
    results = []
    start_cursor = None

    while True:
        url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

        payload = {}

        if start_cursor:
            payload["start_cursor"] = start_cursor

        response = requests.post(
            url,
            headers=NOTION_HEADERS,
            json=payload,
            timeout=20
        )

        if response.status_code != 200:
            raise Exception(response.text)

        data = response.json()

        results.extend(data["results"])

        if not data.get("has_more"):
            break

        start_cursor = data.get("next_cursor")

    return results


def safe_float(value):
    try:
        value = str(value).replace(",", "").replace("%", "")
        return float(value)
    except:
        return 0


def get_market(code):
    code = str(code)

    if code.startswith(("6", "9")):
        return "sh"

    if code.startswith(("0", "2", "3")):
        return "sz"

    if code.startswith(("4", "8")):
        return "bj"

    return "sh"


def get_stock_data(code):

    market = get_market(code)

    url = f"https://hq.sinajs.cn/list={market}{code}"

    headers = {
        "Referer": "https://finance.sina.com.cn/",
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=15
    )

    response.encoding = "gbk"

    text = response.text

    if '="' not in text:
        raise Exception(f"获取失败 {code}")

    content = text.split('="')[1].split('"')[0]

    arr = content.split(",")

    if len(arr) < 4:
        raise Exception(f"数据异常 {code}")

    name = arr[0]

    yesterday_close = safe_float(arr[2])
    current_price = safe_float(arr[3])

    if yesterday_close == 0:
        pct = 0
    else:
        pct = (
            (current_price - yesterday_close)
            / yesterday_close
            * 100
        )

    return {
        "name": name,
        "price": round(current_price, 2),
        "pct": round(pct, 2)
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

            "今日涨幅": {
                "number": pct
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
        timeout=20
    )

    if response.status_code != 200:
        print(response.text)
        raise Exception("更新失败")


def get_code(page):

    props = page["properties"]

    code_prop = props["股票代码"]

    if code_prop["type"] == "rich_text":

        texts = code_prop["rich_text"]

        if not texts:
            return None

        return texts[0]["plain_text"].zfill(6)

    return None


def main():

    print("开始同步")

    pages = query_database()

    print(f"股票数量：{len(pages)}")

    for page in pages:

        code = get_code(page)

        if not code:
            continue

        try:

            stock = get_stock_data(code)

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

            print(f"{code} 更新失败")

            print(str(e))

    print("同步完成")


if __name__ == "__main__":
    main()
