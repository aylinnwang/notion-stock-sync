import os

print("Notion同步启动")

notion_token = os.getenv("NOTION_TOKEN")
database_id = os.getenv("NOTION_DATABASE_ID")

print("Database:", database_id)
