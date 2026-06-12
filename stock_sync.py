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
            print("查询 Notion 数据库失败：", response.status_code)
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
        value = str(value).replace(",", "").replace("%", "").strip()
        if value in ["", "-", "nan", "None"]:
            return 0
        return float(value)
    except Exception:
        return 0


def get_stock_market_prefix(code):
    code = str(code).zfill(6)

    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith(("0", "2", "3")):
        return "sz"
    elif code.startswith(("4", "8")):
        return "bj"
    else:
        return "sh"


def get_stock_data_from_sina(code):
    """
    用新浪接口获取单只A股数据。
    优点：只查Notion里已有股票，不拉全市场，速度更快。
    """
    code = str(code).zfill(6)
    market = get_stock_market_prefix(code)
    symbol = f"{market}{code}"

    url = f"https://hq.sinajs.cn/list={symbol}"

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
    text = response.text.strip()

    if '="' not in text:
        raise Exception(f"新浪接口返回异常：{text}")

    content = text.split('="')[1].rstrip('";')
    fields = content.split(",")

    if len(fields) < 32 or fields[0] == "":
        raise Exception(f"未获取到股票数据：{code}")

    name = fields[0]
    open_price = safe_float(fields[1])
    yesterday_close = safe_float(fields[2])
    current_price = safe_float(fields[3])

    if yesterday_close == 0:
        pct = 0
    else:
        pct = (current_price - yesterday_close) / yesterday_close * 100

    return {
        "name": name,
        "price": round(current_price, 2),
        "pct": round(pct, 2),
        "open": round(open_price, 2),
        "yesterday_close": round(yesterday_close, 2),
    }


def get_stock_data(code):
    """
    增加重试，避免偶发网络超时导致整个任务失败。
    """
    last_error = None

    for attempt in range(3):
        try:
            return get_stock_data_from_sina(code)
        except Exception as e:
            last_error = e
            print(f"第 {attempt + 1} 次获取失败：{code}，原因：{e}")
            time.sleep(2)

    print(f"最终获取失败：{code}，原因：{last_error}")
    return None


def make_pct_text(pct):
    if pct > 0:
        return f"🔴 +{pct:.2f}%"
    elif pct < 0:
        return f"🟢 {pct:.2f}%"
    else:
        return f"⚪ {pct:.2f}%"


def update_page(page_id, price, pct):
    url = f"https://api.notion.com/v1/pages/{page_id}"

    pct_text = make_pct_text(pct)

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
                            "content": pct_text
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
        print("更新 Notion 页面失败：", response.status_code)
        print(response.text)
        raise Exception("Notion page update failed")


def get_code_from_page(page):
    props = page["properties"]

    code_prop = props.get("股票代码")

    if not code_prop:
        return None

    if code_prop["type"] == "rich_text":
        text_list = code_prop["rich_text"]
        if not text_list:
            return None
        return text_list[0]["plain_text"].strip().zfill(6)

    if code_prop["type"] == "title":
        title_list = code_prop["title"]
        if not title_list:
            return None
        return title_list[0]["plain_text"].strip().zfill(6)

    if code_prop["type"] == "number":
        value = code_prop["number"]
        if value is None:
            return None
        return str(int(value)).zfill(6)

    return None


def main():
    print("开始同步 A股数据")

    pages = query_database()
    print(f"Notion 股票数量：{len(pages)}")

    for page in pages:
        props = page["properties"]

        code = get_code_from_page(page)

        if not code:
            print("跳过：股票代码为空")
            continue

        stock_data = get_stock_data(code)

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

        print(
            f"已更新：{code} {stock_data['name']} "
            f"当前价：{price} 涨幅：{make_pct_text(pct)}"
        )

    print("同步完成")


if __name__ == "__main__":
    main()
