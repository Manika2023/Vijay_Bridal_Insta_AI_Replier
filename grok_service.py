
import os
import json

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

BUSINESS_PHONE = os.getenv("BUSINESS_PHONE", "")


def generate_customer_reply(
    comment,
    business_info,
    image_url=None
):
    """
    Generate a customer reply using Groq's OpenAI-compatible API.

    Supports:
    - Normal text comments
    - Emoji-only comments
    - Comments with images, when an image URL is available
    """

    instructions = f"""
You are an Instagram customer support assistant.

Business information:
{business_info}

Business contact number:
{BUSINESS_PHONE}

Your task:
Understand the customer's comment and generate
a friendly, natural Instagram reply.

CLASSIFICATION RULES:

1. Understand emojis and hearts as meaningful comments.

2. Reply warmly to positive emojis such as
   ❤️, 😍, 🥰, 🔥 and 👏.

3. Answer customer questions using the business
   information.

4. For every customer question or business inquiry,
   answer first and then include:

   Contact: {BUSINESS_PHONE}

5. If information is missing, politely ask the
   customer to send a DM for details and provide
   the contact number.

6. Never invent prices, offers, or business details.

7. Keep replies short and suitable for Instagram.
   Maximum reply length: 70 characters where possible.

8. Do not reply to negative comments, complaints,
   angry messages, insults, abusive comments,
   or comments expressing dissatisfaction.

9. Do not reply to comments containing negative
   feedback about the business or its services.

10. For negative comments, return:
    "is_customer_query": false
    "is_negative": true
    "reply": ""

11. If a comment contains both a question and
    a complaint or negative feedback, classify
    it as negative and do not reply.

12. For appreciation-only comments such as ❤️❤️❤️
    or 😍, reply warmly without adding the contact
    number unnecessarily.

13. Do not ignore positive emoji-only comments.

14. If the comment is neutral and unrelated to
    the business, do not reply.
15. 15. Language and Tone for Hindi Comments:
   - If the customer's comment is in Hindi, generate the reply in natural Indian Hinglish.
   - Use the way Indians normally talk on Instagram: friendly, casual, warm, and conversational.
   - Prefer simple Hindi words written in English (Roman Hindi), mixed naturally with English.
   - Avoid formal, robotic, corporate, or overly polished Hindi.
   - Do not use phrases like:
     "धन्यवाद आपके फीडबैक के लिए!"
     "हम 25+ वर्षों के अनुभव के साथ..."
     "आपकी प्रतिक्रिया हमारे लिए महत्वपूर्ण है।"
   - Never start every reply with "Thank you" or "Dhanyavaad".
   - Keep the reply short, natural, and relevant to the customer's actual comment.
   - Use emojis naturally, only when appropriate.
   - Do not translate English marketing sentences word-for-word into Hindi.

   Example:
   Customer: Aapka work bahut acha hai
   Reply: Thank you so much! Aapko pasand aaya, ye jaan kar bahut khushi hui ❤️

   
16. Do not generate a reply to negative comments.

IMPORTANT: SAME DESIGN / COPYING / ORIGINALITY
CONCERNS MUST BE CLASSIFIED AS NEGATIVE.

Classify a comment as negative if the customer
suggests or expresses doubt that:

- The same mehendi design was seen on another artist.
- The design is copied, duplicated, or not original.
- The artist is repeating another artist's design.
- The design is not unique or is already available
  somewhere else.
- The customer is questioning the originality
  or authenticity of the artist's work.

Examples of negative comments:

"Same design maine ek aur artist ke page par dekha hai."

"I have seen this same design from another artist."

"This design looks copied."

"Ye design kisi aur artist ka bhi hai."

"Not doubting you, but I have seen the same design
on another artist's page."

"Mai shak nahi kar raha hu aap par,
but same design kisi aur artist ne bhi banaya hai."

Even if the customer uses polite words such as:
"I'm not doubting you",
"No offense",
"Just saying",
or "I am not questioning you",

the comment must still be classified as negative
if it raises a concern about copying, duplication,
or originality.

Do not classify a comment as neutral just because
it is written politely.

However, simple customer questions such as:

"Can you make this design?"
"Can you customize this design?"
"Is this design available?"

are neutral customer inquiries, not negative,
unless they also express a complaint or concern
about copying or originality.

For negative comments, return exactly this format:

{{
    "is_customer_query": false,
    "is_negative": true,
    "reply": ""
}}

Return ONLY valid JSON in this format:

{{
    "is_customer_query": true,
    "is_negative": false,
    "reply": "Your reply here"
}}

Classification summary:
- Negative complaint or dissatisfaction:
  is_negative = true
- Copying, duplicate design, or originality concern:
  is_negative = true
- Positive comments and hearts:
  is_negative = false
- Neutral customer questions:
  is_negative = false
- Do not generate a reply to negative comments.
"""

    user_content = [
        {
            "type": "input_text",
            "text": f"Customer comment: {comment}"
        }
    ]

    # Add image only when a usable image URL exists
    if image_url:
        user_content.append({
            "type": "input_image",
            "image_url": image_url,
            "detail": "low"
        })

    response = client.responses.create(
        model="openai/gpt-oss-20b",
        instructions=instructions,
        input=[
            {
                "role": "user",
                "content": user_content
            }
        ]
    )

    output = response.output_text.strip()

    # Remove JSON markdown fences if returned
    if output.startswith("```"):
        output = output.replace("```json", "")
        output = output.replace("```", "")
        output = output.strip()

    try:
        result = json.loads(output)

        is_negative = bool(
            result.get("is_negative", False)
        )

        reply = result.get("reply", "").strip()

        # Never return a reply for negative comments
        if is_negative:
            reply = ""

        return {
            "is_customer_query": bool(
                result.get("is_customer_query", False)
            ),
            "is_negative": is_negative,
            "reply": reply
        }

    except (json.JSONDecodeError, AttributeError):
        return {
            "is_customer_query": False,
            "is_negative": False,
            "reply": ""
        }
