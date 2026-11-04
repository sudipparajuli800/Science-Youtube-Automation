"""Compatibility entry point for old callers; HF tokens do not grant video credits.

New code uses video_generation.VideoGenerator with explicitly configured hosted
providers or reviewed cloud-notebook clips. No legacy api-inference endpoint or
invented monthly free-request allowance is used.
"""
from .video_generation import VideoGenerator


def generate_hf_video(prompt, output_dir, scene_idx, hf_token=None):
    result = VideoGenerator().generate({'ai_video_prompt': prompt, 'narration': prompt}, prompt)
    if result:
        return {'asset_type': 'ai_video', **result}
    return {'asset_type': 'none', 'asset_path': None}
