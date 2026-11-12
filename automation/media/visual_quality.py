"""Check visual readiness before rendering and publication."""
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
    cards = sum(s.get('visual_type') == 'explainer_card' for s in scenes)
    contextual = sum(
        s.get('asset_type') in ('video', 'ai_video') or
        (s.get('asset_type') == 'image' and s.get('visual_type') != 'explainer_card') or
        bool(s.get('context_path')) or
        (s.get('asset_type') == 'animation' and
         (s.get('animation') or {}).get('template') == 'photo' and bool(s.get('asset_path')))
        for s in scenes)
    enough_context = len(scenes) < 4 or contextual >= len(scenes) / 3
    ready = bool(moving) and cards <= len(scenes) * .25 and enough_context
    report = {'status': 'ready' if ready else 'held', 'scenes': len(scenes),
              'moving_scenes': moving, 'footage_scenes': footage, 'animation_scenes': animated,
              'cards': cards, 'contextual_scenes': contextual,
              'kie_key_configured': bool(os.getenv('KIE_API_KEY', '').strip()),
              'fal_key_configured': bool(os.getenv('FAL_KEY', '').strip()),
              'local_relevance_enabled': os.getenv('LOCAL_VISUAL_RELEVANCE', '').lower() == 'true'}
    path = Path('automation/storage/visual_quality_report.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'[VisualQuality] {moving}/{len(scenes)} scenes contain footage or explanatory animation; {report["cards"]} cards.')
    if not ready and not is_test:
        if not enough_context:
            raise VisualQualityHold(
                f'Only {contextual}/{len(scenes)} scenes contain contextual photos or video. '
                'At least one third of multi-scene videos must show a subject image or clip, '
                'either directly or behind a diagram.')
        if moving:
            raise VisualQualityHold(
                f'{cards}/{len(scenes)} scenes are fallback text cards. At most 25% are allowed. '
                'Improve contextual media or the explanatory scene plan before publishing.')
        raise VisualQualityHold(
            'No footage or validated explanatory animation found. Stopped before rendering/upload. '
            f'Kie key configured: {report["kie_key_configured"]}; '
            f'fal key configured: {report["fal_key_configured"]}. '
            'Inspect visual_quality_report.json and the scene manifest. '
            'Prepare the Remotion renderer, enable CPU stock matching, or configure a video provider with available credits, '
            'or import reviewed visual-bank clips.')


def report_hold(message):
    print(f'::error title=Video held for visual quality::{message}')
    summary = os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as output:
            output.write('### Video held for visual quality\n\n' + message +
                         '\n\nRendering and publication were skipped.\n')
