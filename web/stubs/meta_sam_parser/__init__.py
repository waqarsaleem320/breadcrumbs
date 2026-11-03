"""Browser-demo stand-in for meta_sam_parser: SAM runs only in the full app."""

MESSAGE = "SAM 3.1 needs the full app with a Meta Model API key. See 'Run it' in the README."


def _unavailable(*args, **kwargs):
    raise RuntimeError(MESSAGE)


FramePrompt = PromptBox = PromptObject = _unavailable
build_object_prompt = decode_mask_to_raster = image_segmentation_format = parse_responses_stream = _unavailable
