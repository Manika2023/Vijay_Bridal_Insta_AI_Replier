
import os
import requests

from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
IG_USER_ID = os.getenv("INSTAGRAM_USER_ID")
API_VERSION = os.getenv("GRAPH_API_VERSION", "v26.0")

BASE_URL = f"https://graph.facebook.com/{API_VERSION}"


def api_get(endpoint, params=None):

    params = params or {}
    params["access_token"] = TOKEN

    response = requests.get(
        f"{BASE_URL}/{endpoint}",
        params=params,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


def normalize_url(url):

    parsed = urlparse(url.strip())

    return parsed.path.rstrip("/")


def get_media_by_url(reel_url):

    target_path = normalize_url(reel_url)

    result = api_get(
        f"{IG_USER_ID}/media",
        {
            "fields": "id,caption,media_type,permalink",
            "limit": 100
        }
    )

    media_list = result.get("data", [])

    while True:

        for media in media_list:

            permalink = media.get("permalink", "")

            if normalize_url(permalink) == target_path:
                return media

        next_url = result.get("paging", {}).get("next")

        if not next_url:
            break

        response = requests.get(
            next_url,
            timeout=30
        )

        response.raise_for_status()
        result = response.json()

        media_list = result.get("data", [])

    raise ValueError(
        "Reel/Post not found in your connected Instagram account."
    )


def get_comments(media_id):

    result = api_get(
        f"{media_id}/comments",
        {
            "fields": "id,text,timestamp,username",
            "limit": 100
        }
    )

    comments = result.get("data", [])

    while result.get("paging", {}).get("next"):

        next_url = result["paging"]["next"]

        response = requests.get(
            next_url,
            timeout=30
        )

        response.raise_for_status()

        result = response.json()

        comments.extend(result.get("data", []))

    return comments


# def reply_to_comment(comment_id, message):
#     print("comment id: ",comment_id)

#     response = requests.post(
#         f"{BASE_URL}/{comment_id}/replies",
#         data={
#             "message": message,
#             "access_token": TOKEN
#         },
#         timeout=30
#     )

#     response.raise_for_status()

#     return response.json()
import requests

def reply_to_comment(comment_id, message):
    print("Comment ID:", comment_id)

    response = requests.post(
        f"{BASE_URL}/{comment_id}/replies",
        data={
            "message": message,
            "access_token": TOKEN
        },
        timeout=30
    )

    response.raise_for_status()

    return response.json()