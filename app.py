import os
import logging
from urllib.parse import quote

import chainlit as cl
import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pollinations-image-gen")

POLLINATIONS_MODEL = os.getenv("POLLINATIONS_MODEL", "flux")
POLLINATIONS_API_TOKEN = os.getenv("POLLINATIONS_API_TOKEN")
POLLINATIONS_WIDTH = int(os.getenv("POLLINATIONS_WIDTH", "1024"))
POLLINATIONS_HEIGHT = int(os.getenv("POLLINATIONS_HEIGHT", "1024"))

IMAGE_ENDPOINT = "https://image.pollinations.ai/prompt/{prompt}"


async def generate_image_bytes(prompt: str) -> bytes:
    url = IMAGE_ENDPOINT.format(prompt=quote(prompt))

    params = {
        "model": POLLINATIONS_MODEL,
        "width": POLLINATIONS_WIDTH,
        "height": POLLINATIONS_HEIGHT,
        "nologo": "true" if POLLINATIONS_API_TOKEN else "false",
    }
    headers = {}
    if POLLINATIONS_API_TOKEN:
        headers["Authorization"] = f"Bearer {POLLINATIONS_API_TOKEN}"

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.get(url, params=params, headers=headers)

    if response.status_code == 429:
        raise ValueError(
            "Rate limited by Pollinations (anonymous tier allows ~1 request per 15s). "
            "Wait a few seconds and try again, or set POLLINATIONS_API_TOKEN for higher limits."
        )
    if response.status_code != 200:
        raise ValueError(f"Pollinations returned HTTP {response.status_code}: {response.text[:200]}")

    content_type = response.headers.get("content-type", "")
    if "image" not in content_type:
        raise ValueError(f"Pollinations did not return an image (content-type: {content_type}).")

    return response.content


@cl.on_chat_start
async def start():
    cl.user_session.set("image_count", 0)

    await cl.Message(
        content=(
            "## AI Image Generator\n\n"
            "Describe an image and I'll generate it with **Pollinations AI** "
            f"(`{POLLINATIONS_MODEL}` model).\n\n"
            "**Try something like:**\n"
            "- *a watercolor fox reading a book in a forest library*\n"
            "- *a neon-lit cyberpunk street market at night, rain, reflections*\n"
            "- *a minimalist logo for a coffee brand called 'Ember'*"
        )
    ).send()


@cl.on_message
async def main(message: cl.Message):
    prompt = message.content.strip()

    if not prompt:
        await cl.Message(content="Please enter a text prompt describing the image you want.").send()
        return

    async with cl.Step(name="Generating your image", type="tool") as step:
        step.input = prompt
        try:
            image_bytes = await generate_image_bytes(prompt)
            step.output = "Image generated successfully."
        except httpx.TimeoutException:
            step.output = "Timed out."
            await cl.Message(
                content="**Timed out** waiting for Pollinations. Try again, or simplify the prompt."
            ).send()
            return
        except Exception as e:
            logger.exception("Pollinations image generation failed")
            step.output = f"Error: {e}"
            await cl.Message(
                content=(
                    "**Couldn't generate that image.**\n\n"
                    f"Reason: `{e}`\n\n"
                    "Try rephrasing your prompt, or wait a few seconds if you're being rate limited."
                )
            ).send()
            return

    count = cl.user_session.get("image_count", 0) + 1
    cl.user_session.set("image_count", count)

    image_element = cl.Image(
        content=image_bytes,
        name=f"generated_{count}.png",
        display="inline",
        size="large",
    )

    await cl.Message(
        content=f"**Prompt:** {prompt}",
        elements=[image_element],
    ).send()
