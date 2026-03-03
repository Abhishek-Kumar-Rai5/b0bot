import sys
import os
import json
import hashlib
from dotenv import dotenv_values
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

from utils.rss_fetcher import RSSFetcher

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cybernews.CyberNews import CyberNews


PINECONE_API = dotenv_values(".env").get("PINECONE_API_KEY")

pc = Pinecone(api_key=PINECONE_API)
index_name = "cybernews-index"

# Create index ONLY if not exists
if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=384,
        metric='cosine',
        spec=ServerlessSpec(
            cloud='aws',
            region='us-east-1'
        )
    )

index = pc.Index(index_name)
namespace = "c2si"

model = SentenceTransformer('all-MiniLM-L6-v2')

news = CyberNews()
newsBox = dict()

newsBox["general_news"] = news.get_news("general")
newsBox["cyber_attack_news"] = news.get_news("cyberAttack")
newsBox["vulnerability_news"] = news.get_news("vulnerability")
newsBox["malware_news"] = news.get_news("malware")
newsBox["security_news"] = news.get_news("security")
newsBox["data_breach_news"] = news.get_news("dataBreach")

# ---- RSS Integration ----
try:
    with open("config/rss_sources.json") as f:
        rss_sources = json.load(f)

    rss_articles = []

    for name, url in rss_sources.items():
        fetcher = RSSFetcher(url)
        fetched = fetcher.fetch(limit=10)

        for item in fetched:
            url_hash = hashlib.md5(item["url"].encode()).hexdigest()

            rss_articles.append({
                "id": f"rss_{name}_{url_hash}",
                "headlines": item["title"],
                "author": name,
                "fullNews": item["title"],
                "newsURL": item["url"],
                "newsImgURL": "",
                "newsDate": item["date"]
            })

    newsBox["rss_news"] = rss_articles
    print(f"Added {len(rss_articles)} RSS articles")

except Exception as e:
    print("RSS loading failed:", e)

# ---- Upsert ----
existing_ids = set()

for news_type, articles in newsBox.items():
    for article in articles:

        document_id = str(article["id"])

        if document_id in existing_ids:
            continue

        existing_ids.add(document_id)

        text = article["headlines"] + " " + article["fullNews"]
        vector = model.encode(text).tolist()

        metadata = {
            "headlines": article["headlines"],
            "author": article["author"],
            "fullNews": article["fullNews"],
            "newsURL": article["newsURL"],
            "newsImgURL": article["newsImgURL"],
            "newsDate": article["newsDate"]
        }

        index.upsert([(document_id, vector, metadata)], namespace=namespace)

        print(f"Inserted article ID: {document_id}")