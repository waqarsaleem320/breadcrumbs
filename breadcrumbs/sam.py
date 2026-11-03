"""Pixel masks from SAM 3.1, and blurring with them."""
import asyncio
import base64
import io

import numpy as np
from meta_sam_parser import (
    FramePrompt,
    PromptBox,
    PromptObject,
    build_object_prompt,
    decode_mask_to_raster,
    image_segmentation_format,
    parse_responses_stream,
)
from openai import AsyncOpenAI
from PIL import Image, ImageFilter

from breadcrumbs.config import BASE_URL, SAM_MODEL, load_key

BLUR_RADIUS = 24
Box = tuple[int, int, int, int]  # left, top, right, bottom in pixels


def _data_url(image: Image.Image) -> str:
    """Encode a PIL image as a JPEG data URL."""
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


async def _records(image: Image.Image, prompt: str) -> list:
    """Return SAM box and mask records for one image and one prompt."""
    client = AsyncOpenAI(api_key=load_key(), base_url=BASE_URL)
    events = await client.responses.create(
        model=SAM_MODEL,
        stream=True,
        input=[
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": _data_url(image)},
                ],
            }
        ],
    )
    parsed = parse_responses_stream(events, image_segmentation_format())
    result = await parsed.final_result()
    return list(result.records)


def clue_boxes(image: Image.Image, nouns: list[str]) -> list[Box]:
    """Return every box SAM finds for any noun, without exact repeats."""
    async def all_records() -> list:
        return await asyncio.gather(*(_records(image, noun) for noun in nouns))

    found: dict[Box, None] = {}
    for records in asyncio.run(all_records()):
        for r in records:
            if r.kind == "box":
                found[(r.left, r.top, r.right, r.bottom)] = None
    return list(found)


def clue_mask(image: Image.Image, boxes: list[Box]) -> np.ndarray:
    """Return a boolean image-sized mask covering every boxed clue."""
    full = np.zeros((image.height, image.width), dtype=bool)
    prompt = build_object_prompt(
        size=image.size,
        objects=[
            PromptObject(id=i + 1, prompts=[FramePrompt(frame=0, box=PromptBox(*box))])
            for i, box in enumerate(boxes)
        ],
    )
    records = asyncio.run(_records(image, prompt))
    for record in (r for r in records if r.kind == "mask"):
        mask, area = record.mask, record.bounds
        raster = np.frombuffer(decode_mask_to_raster(mask), dtype=np.uint8)
        raster = (raster.reshape(mask.height, mask.width) > 0).astype(np.uint8) * 255
        # Large masks arrive at lower resolution than their bounds.
        size = (area.right - area.left, area.bottom - area.top)
        scaled = Image.fromarray(raster).resize(size, Image.NEAREST)
        full[area.top : area.bottom, area.left : area.right] |= np.array(scaled) > 0
    return full


def blur_where(image: Image.Image, mask: np.ndarray) -> Image.Image:
    """Return a copy of image with masked pixels replaced by a heavy blur."""
    blurred = image.convert("RGB").filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
    alpha = Image.fromarray(mask.astype(np.uint8) * 255)
    return Image.composite(blurred, image.convert("RGB"), alpha)
