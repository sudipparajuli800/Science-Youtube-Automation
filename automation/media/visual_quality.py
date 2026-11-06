"""Check visual readiness before spending narration/render resources."""
import json
import os
from pathlib import Path


class VisualQualityHold(RuntimeError):
    pass


def check_visual_quality(manifest, is_test=False):
    scenes = manifest.get('scenes', [])
    from .motion_graphics import engine_ready, validate_animation
    footage = sum(s.get('asset_type') in ('video', 'ai_video') for s in scenes)
    animated = sum(s.get('asset_type') == 'animation' and engine_ready() and
                   bool(validate_animation(s.get('animation'), s.get('narration', ''), manifest.get('topic', '')))
                   for s in scenes)
    moving = footage + animated
    report = {'status': 'ready' if moving else 'held', 'scenes': len(scenes),
              'moving_scenes': moving, 'footage_scenes': footage, 'animation_scenes': animated,
              'cards': sum(s.get('visual_type') == 'explainer_card' for s in scenes),
              'kie_key_configured': bool(os.getenv('KIE_API_KEY', '').strip()),
              'fal_key_configured': bool(os.getenv('FAL_KEY', '').strip()),
              'local_relevance_enabled': os.getenv('LOCAL_VISUAL_RELEVANCE', '').lower() == 'true'}
    path = Path('automation/storage/visual_quality_report.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'[VisualQuality] {moving}/{len(scenes)} scenes contain footage or explanatory animation; {report["cards"]} cards.')
    if not moving and not is_test:
        raise VisualQualityHold(
            'No footage or validated explanatory animation found. Stopped before TTS/render/upload. '
            f'Kie key configured: {report["kie_key_configured"]}; '
            f'fal key configured: {report["fal_key_configured"]}. '
            'Inspect visual_quality_report.json and the scene manifest. '
            'Prepare the Remotion renderer, enable CPU stock matching, or configure a video provider with available credits, '
            'or import reviewed visual-bank clips.')


def report_hold(message):
    print(f'::notice title=Video held for visual quality::{message}')
    summary = os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as output:
            output.write('### Video held: no explanatory visuals\n\n' + message +
                         '\n\nNo narration was purchased and nothing was published.\n')
