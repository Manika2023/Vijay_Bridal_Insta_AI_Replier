import os
import json
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from instagram_service import (
    get_media_by_url,
    get_comments,
    reply_to_comment,
)
from grok_service import generate_customer_reply


# =========================================================
# 1. Configuration
# =========================================================

load_dotenv()

BUSINESS_FILE = Path("business_info.txt")
PROCESSED_FILE = Path("replied_comments.json")

IG_USERNAME = (
    os.getenv("INSTAGRAM_USERNAME", "")
    .strip()
    .lower()
    .lstrip("@")
)

AUTO_REPLY_ENABLED = (
    os.getenv("AUTO_REPLY_ENABLED", "false").lower() == "true"
)


# =========================================================
# 2. Streamlit page settings
# =========================================================

st.set_page_config(
    page_title="Instagram AI Customer Replier",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Instagram AI Customer Replier")
st.write(
    "Fetch Instagram Reel comments, generate customer replies "
    "with AI, filter negative comments, and publish replies."
)


# =========================================================
# 3. Session state initialization
# =========================================================

DEFAULT_STATE = {
    "results": [],
    "negative_comments": [],
    "auto_reply": False,
    "publish_message": "",
    "negative_publish_message": "",
    "active_reel_url": "",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# 4. Helper functions
# =========================================================

def load_business_info():
    """Read business information from business_info.txt."""
    if BUSINESS_FILE.exists():
        return BUSINESS_FILE.read_text(encoding="utf-8")
    return ""


def load_processed_comments():
    """Load comment IDs successfully replied to."""
    if not PROCESSED_FILE.exists():
        return set()

    try:
        with open(PROCESSED_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        return {str(comment_id) for comment_id in data}

    except (json.JSONDecodeError, OSError):
        return set()


def save_processed_comments(processed_comments):
    """Save successfully replied comment IDs."""
    with open(PROCESSED_FILE, "w", encoding="utf-8") as file:
        json.dump(sorted(processed_comments), file, indent=4)


def get_comment_image_url(comment):
    """Try to find an image URL in the comment data."""
    for field in ("image_url", "media_url", "attachment_url"):
        value = comment.get(field)
        if value:
            return value

    attachments = comment.get("attachments", {})

    if isinstance(attachments, dict):
        attachment_data = attachments.get("data", [])

        if isinstance(attachment_data, list):
            for attachment in attachment_data:
                if not isinstance(attachment, dict):
                    continue

                if attachment.get("media_type") == "IMAGE":
                    image_url = attachment.get("media_url")
                    if image_url:
                        return image_url

                media = attachment.get("media", {})
                if isinstance(media, dict):
                    image_url = media.get("image_url")
                    if image_url:
                        return image_url

    return None


def publish_reply(comment_id, reply_text):
    """Publish one reply to Instagram."""
    return reply_to_comment(
        comment_id=comment_id,
        message=reply_text,
    )


def reply_widget_key(comment_id):
    """Stable widget key for an AI reply."""
    return f"ai_reply_{comment_id}"


def negative_reply_widget_key(comment_id):
    """Stable widget key for a manually written negative reply."""
    return f"manual_negative_reply_{comment_id}"


def publish_ai_replies(results):
    """
    Publish positive/customer replies using the current text-area
    values from session state, not stale values in results.
    """
    processed_comments = load_processed_comments()
    success_count = 0
    failed_count = 0

    for item in results:
        comment_id = str(item["comment_id"])
        widget_key = reply_widget_key(comment_id)

        # Read the latest edited text directly from widget state.
        reply_text = st.session_state.get(
            widget_key,
            item.get("reply", ""),
        ).strip()

        if not reply_text or comment_id in processed_comments:
            continue

        try:
            publish_reply(comment_id, reply_text)
            processed_comments.add(comment_id)
            success_count += 1

        except Exception as error:
            failed_count += 1
            st.warning(
                f"Could not reply to @{item.get('username', 'user')}: "
                f"{error}"
            )

    save_processed_comments(processed_comments)
    return success_count, failed_count


def publish_manual_negative_replies(negative_comments):
    """
    Publish only manually typed negative-comment replies.
    No LLM is called here.
    """
    processed_comments = load_processed_comments()
    success_count = 0
    failed_count = 0
    skipped_count = 0

    for item in negative_comments:
        comment_id = str(item["comment_id"])
        widget_key = negative_reply_widget_key(comment_id)

        reply_text = st.session_state.get(widget_key, "").strip()

        if not reply_text:
            skipped_count += 1
            continue

        if comment_id in processed_comments:
            skipped_count += 1
            continue

        try:
            publish_reply(comment_id, reply_text)
            processed_comments.add(comment_id)
            success_count += 1

        except Exception as error:
            failed_count += 1
            st.warning(
                f"Could not reply to @{item.get('username', 'user')}: "
                f"{error}"
            )

    save_processed_comments(processed_comments)
    return success_count, failed_count, skipped_count


def reset_reply_widgets_for_new_results(old_results, old_negative):
    """
    Remove old widget values only when replacing the comments with
    a newly fetched Reel. Publishing does not call this function.
    """
    for item in old_results:
        st.session_state.pop(
            reply_widget_key(str(item["comment_id"])),
            None,
        )

    for item in old_negative:
        st.session_state.pop(
            negative_reply_widget_key(str(item["comment_id"])),
            None,
        )


# =========================================================
# 5. Load business information
# =========================================================

business_info = load_business_info()

if not business_info.strip():
    st.warning(
        "Your business_info.txt file is empty or missing. "
        "Please add your business details before generating replies."
    )


# =========================================================
# 6. Reel URL and settings
# =========================================================

reel_url = st.text_input(
    "Instagram Reel URL",
    placeholder="Paste your Instagram Reel URL here",
)

auto_reply = st.checkbox(
    "Automatically publish replies after generation",
    value=AUTO_REPLY_ENABLED,
)

if auto_reply:
    st.warning(
        "Auto-publishing is enabled. Positive/customer replies may be "
        "published without manual review. Negative comments are never "
        "automatically published."
    )


# =========================================================
# 7. Fetch comments and generate replies
# =========================================================

if st.button("Fetch Comments and Generate Replies", type="primary"):

    if not reel_url.strip():
        st.error("Please enter an Instagram Reel URL.")

    elif not business_info.strip():
        st.error("Please add your business information first.")

    else:
        try:
            with st.spinner("Fetching Instagram Reel..."):
                media = get_media_by_url(reel_url.strip())

            if not media or not media.get("id"):
                st.error(
                    "Could not find the Instagram Reel. "
                    "Please check the URL."
                )

            else:
                media_id = media["id"]

                with st.spinner("Fetching comments..."):
                    comments = get_comments(media_id)

                if not comments:
                    st.info("No comments were found on this Reel.")

                else:
                    new_results = []
                    new_negative_comments = []
                    processed_comments = load_processed_comments()

                    progress = st.progress(0)
                    total_comments = len(comments)

                    for index, comment in enumerate(comments):
                        comment_id = str(comment.get("id", ""))

                        username = comment.get(
                            "username",
                            "Unknown user",
                        )

                        comment_text = comment.get("text", "").strip()

                        if not comment_id:
                            continue

                        if comment_id in processed_comments:
                            continue

                        if (
                            IG_USERNAME
                            and username.lower().lstrip("@") == IG_USERNAME
                        ):
                            continue

                        if not comment_text:
                            continue

                        image_url = get_comment_image_url(comment)

                        # The LLM classifies and generates replies for
                        # ordinary comments. For negative comments, the
                        # prompt must return is_negative=True and reply="".
                        ai_result = generate_customer_reply(
                            comment=comment_text,
                            business_info=business_info,
                            image_url=image_url,
                        )

                        if ai_result.get("is_negative", False):
                            new_negative_comments.append({
                                "comment_id": comment_id,
                                "username": username,
                                "comment": comment_text,
                            })
                            continue

                        if not ai_result.get("is_customer_query", False):
                            continue

                        reply_text = ai_result.get("reply", "").strip()

                        if not reply_text:
                            continue

                        new_results.append({
                            "comment_id": comment_id,
                            "username": username,
                            "comment": comment_text,
                            "reply": reply_text,
                        })

                        progress.progress(
                            min((index + 1) / total_comments, 1.0)
                        )

                    progress.empty()

                    # Clear previous widget values only for a new fetch.
                    reset_reply_widgets_for_new_results(
                        st.session_state["results"],
                        st.session_state["negative_comments"],
                    )

                    # Store fresh results.
                    st.session_state["results"] = new_results
                    st.session_state["negative_comments"] = (
                        new_negative_comments
                    )
                    st.session_state["auto_reply"] = auto_reply
                    st.session_state["active_reel_url"] = reel_url.strip()
                    st.session_state["publish_message"] = ""
                    st.session_state["negative_publish_message"] = ""

                    # Initialize widget state for each fresh AI reply.
                    for item in new_results:
                        st.session_state[
                            reply_widget_key(str(item["comment_id"]))
                        ] = item["reply"]

                    # Initialize manual negative reply boxes as blank.
                    for item in new_negative_comments:
                        st.session_state[
                            negative_reply_widget_key(
                                str(item["comment_id"])
                            )
                        ] = ""

                    # Auto-publish only positive/customer replies.
                    # Negative comments are never passed here.
                    if auto_reply and new_results:
                        with st.spinner("Publishing AI replies..."):
                            success_count, failed_count = (
                                publish_ai_replies(new_results)
                            )

                        st.session_state["publish_message"] = (
                            f"Auto-published {success_count} AI replies. "
                            f"Failed: {failed_count}."
                        )

                    st.success(
                        f"Finished processing {total_comments} comments."
                    )

        except Exception as error:
            st.error(f"An error occurred: {error}")


# =========================================================
# 8. Negative comments: red section + manual editable replies
# =========================================================

negative_comments = st.session_state["negative_comments"]

if negative_comments:
    st.error(
        f"🚨 Negative Comments Detected: {len(negative_comments)}"
    )

    st.write(
        "These comments did not receive AI-generated replies. "
        "Write your own reply if you want to respond."
    )

    for item in negative_comments:
        username = item.get("username", "Unknown user")
        comment_text = item.get("comment", "")
        comment_id = str(item["comment_id"])

        with st.expander(f"🔴 **@{username}: {comment_text}**",expanded=False):
          st.text_input(
            "Write your own reply",
            placeholder="Type your reply manually...",
            key=negative_reply_widget_key(comment_id)
        )
    st.caption(
        "Negative comments are never auto-published. "
        "Only the text you write above will be sent."
    )

    if st.button(
        "Publish Manual Replies to Negative Comments",
        type="secondary",
    ):
        with st.spinner("Publishing your manual replies..."):
            success_count, failed_count, skipped_count = (
                publish_manual_negative_replies(negative_comments)
            )

        st.session_state["negative_publish_message"] = (
            f"Published {success_count} manual replies. "
            f"Failed: {failed_count}. "
            f"Skipped empty/already replied: {skipped_count}."
        )

        # Do NOT clear text-area keys or results here.
        st.rerun()


# =========================================================
# 9. Publishing status
# =========================================================

if st.session_state.get("publish_message"):
    st.success(st.session_state["publish_message"])

if st.session_state.get("negative_publish_message"):
    st.success(st.session_state["negative_publish_message"])


# =========================================================
# 10. Display AI-generated replies with persistent edits
# =========================================================

results = st.session_state["results"]

st.subheader(f"Generated AI Replies: {len(results)}")

if not results:
    st.info(
        "No customer questions or positive comments "
        "requiring a reply were found."
    )

else:
    for item in results:
        comment_id = str(item["comment_id"])
        username = item.get("username", "Unknown user")
        comment_text = item.get("comment", "")

        with st.expander(
            f"Comment from @{username}: {comment_text}",
            expanded=False,
        ):
            st.markdown("**AI Reply:**")

            # Stable key and session state preserve edits on reruns.
            st.text_input(
                "Edit reply before publishing",
                key=reply_widget_key(comment_id)
            )


# =========================================================
# 11. Manual publishing for AI replies
# =========================================================

if results and not st.session_state["auto_reply"]:
    st.divider()
    st.subheader("Publish AI Replies")

    st.write(
        "Review and edit the replies above, then publish them. "
        "Your edits will remain in the input boxes after publishing."
    )

    if st.button("Publish All AI Replies", type="primary"):
        with st.spinner("Publishing replies to Instagram..."):
            success_count, failed_count = publish_ai_replies(results)

        st.session_state["publish_message"] = (
            f"Published {success_count} AI replies. "
            f"Failed: {failed_count}."
        )

        # Keep results and widget state. Rerun only to refresh status.
        st.rerun()
