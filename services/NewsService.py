import json
from dotenv import dotenv_values
from flask import jsonify
from huggingface_hub import InferenceClient

from models.NewsModel import CybernewsDB


env_vars = dotenv_values(".env")
HUGGINGFACEHUB_API_TOKEN = env_vars.get("HUGGINGFACE_TOKEN")


class NewsService:
    def __init__(self, model_name) -> None:
        self.db = CybernewsDB()

        # Load LLM configuration
        with open("config/llm_config.json") as f:
            llm_config = json.load(f)

        model_config = llm_config.get(model_name)
        if not model_config:
            raise ValueError(f"Model '{model_name}' not found in llm_config.json")

        self.repo_id = model_config["repo_id"]
        self.model_type = model_config["type"]

        self.client = InferenceClient(
            token=HUGGINGFACEHUB_API_TOKEN
        )

        self.news_number = 10

    # -----------------------------
    # Prompt Builder
    # -----------------------------
    def build_prompt_from_messages(self, messages):
        prompt = ""
        for msg in messages:
            role = msg["role"].upper()
            content = msg["content"]
            prompt += f"{role}: {content}\n"
        prompt += "ASSISTANT:"
        return prompt

    # -----------------------------
    # Main News Method
    # -----------------------------
    def getNews(self, user_keywords=None):

        news_data = self.db.get_news_collections()[:50]

        # Trim large fields
        compact_news = [
            {
                "title": item.get("headlines"),
                "source": item.get("newsURL"),
                "date": item.get("newsDate"),
            }
            for item in news_data
        ]

        if user_keywords:
            messages_template_path = "prompts/withkey.json"
        else:
            messages_template_path = "prompts/withoutkey.json"

        messages = self.load_json_file(messages_template_path)

        for message in messages:
            if (
                message["role"] == "user"
                and "<news_data_placeholder>" in message["content"]
            ):
                message["content"] = message["content"].replace(
                    "<news_data_placeholder>",
                    json.dumps(compact_news),
                )

        try:
            if self.model_type == "chat":
                response = self.client.chat.completions.create(
                    model=self.repo_id,
                    messages=messages,
                    max_tokens=512,
                    temperature=0.5,
                )
                generated_text = response.choices[0].message.content

            elif self.model_type == "text":
                prompt = self.build_prompt_from_messages(messages)

                generated_text = self.client.text_generation(
                    model=self.repo_id,
                    prompt=prompt,
                    max_new_tokens=512,
                    temperature=0.5,
                    return_full_text=False,
                )

            else:
                raise ValueError(f"Unsupported model type: {self.model_type}")

        except Exception as e:
            return {"error": f"Model inference failed: {str(e)}"}

        return self.toJSON(generated_text)

    # -----------------------------
    # 404 Handler
    # -----------------------------
    def notFound(self, error):
        return jsonify({"error": error}), 404

    # -----------------------------
    # Load JSON File
    # -----------------------------
    def load_json_file(self, file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)

    # -----------------------------
    # Robust JSON Parsing
    # -----------------------------
    def toJSON(self, data: str):
        if len(data) == 0:
            return {}

        news_list = data.split("\n")
        news_list_json = []

        if news_list and not news_list[0].strip().startswith("["):
            news_list.pop(0)

        for item in news_list:
            if len(item) == 0:
                continue

            data_list = [
                item.strip().strip('"')
                for item in item.strip('[').strip(']').split(',')
           ]
            data_list = [val.strip() for val in data_list]

            start_index = data_list[0].find('[') if len(data_list) > 0 else -1
            end_index = data_list[3].find(']') if len(data_list) > 3 else -1

            title = (
                data_list[0][start_index + 1:]
                if len(data_list) > 0
                else "No title provided"
            )
            source = data_list[1] if len(data_list) > 1 else "No source provided"
            date = data_list[2] if len(data_list) > 2 else "No date provided"
            url = (
                data_list[3][: end_index - 1]
                if len(data_list) > 3
                else "No URL provided"
           )

            news_item = {
                "title": title,
                "source": source,
                "date": date,
                "url": url,
            }

            news_list_json.append(news_item)
  
        if news_list_json:
            news_list_json.pop()

        return news_list_json