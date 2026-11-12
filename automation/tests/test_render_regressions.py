import json
import unittest
from unittest.mock import AsyncMock, Mock, patch
from automation.media.timing_utils import match_scenes_to_timestamps


class TimingRegressionTests(unittest.TestCase):
    def test_missing_word_does_not_consume_later_repeated_word(self):
        scenes = [{'narration': 'Water moves through the roots.'},
                  {'narration': 'Light warms the water.'},
                  {'narration': 'The roots absorb nutrients.'}]
        words = 'Water moves through roots Light warms the water The roots absorb nutrients'.split()
        offsets = [{'word': word, 'start': i*.4, 'duration': .3} for i, word in enumerate(words)]
        times = match_scenes_to_timestamps(scenes, offsets, 5)
        self.assertAlmostEqual(times[0]['end'], 1.6)
        self.assertAlmostEqual(times[1]['end'], 3.2)
        self.assertAlmostEqual(sum(t['duration'] for t in times), 5)

    def test_no_timestamps_use_narration_lengths(self):
        scenes = [{'narration': 'One two'}, {'narration': 'Three four five six seven eight'}]
        times = match_scenes_to_timestamps(scenes, [], 8)
        self.assertEqual([t['duration'] for t in times], [2, 6])

    def test_bad_legacy_offsets_still_cover_audio_once(self):
        scenes = [{'narration': 'alpha'}, {'narration': 'beta'}, {'narration': 'gamma'}]
        words = [{'word': 'alpha', 'start': 8, 'duration': 1},
                 {'word': 'beta', 'start': 2, 'duration': 1}]
        times = match_scenes_to_timestamps(scenes, words, 4)
        self.assertEqual(times[0]['start'], 0)
        self.assertEqual(times[-1]['end'], 4)
        self.assertTrue(all(t['duration'] > 0 for t in times))
        self.assertTrue(all(a['end'] == b['start'] for a,b in zip(times, times[1:])))


class NarrationPreflightTests(unittest.TestCase):
    def pipeline(self):
        from automation.pipelines.science_pipeline import SciencePipeline
        pipeline = SciencePipeline.__new__(SciencePipeline)
        pipeline.config = {}
        pipeline.tts = AsyncMock()
        pipeline.tts.generate_audio.return_value = ('audio.mp3', [])
        pipeline.script_writer = Mock()
        pipeline.script_writer.generate_science_facts.return_value = ' '.join(['original'] * 100)
        pipeline.script_writer.shorten_science_script.return_value = 'Water absorbs heat and changes into vapor.'
        pipeline.script_writer.generate_shorts_visual_scenes.return_value = [{'narration': 'Water absorbs heat and changes into vapor.'}]
        return pipeline

    def test_rewrite_and_remeasure_before_assets(self):
        pipeline = self.pipeline()
        with patch('automation.media.hume_tts.get_audio_duration', side_effect=[70, 12]), patch(
                'automation.media.asset_orchestrator.AssetOrchestrator.fetch_all',
                side_effect=RuntimeError('asset boundary')) as fetch:
            coroutine = pipeline._run_shorts('Water', False)
            with self.assertRaisesRegex(RuntimeError, 'asset boundary'):
                coroutine.send(None)
            coroutine.close()
        self.assertEqual(pipeline.tts.generate_audio.await_count, 2)
        pipeline.script_writer.shorten_science_script.assert_called_once()
        self.assertEqual(pipeline.script_writer.generate_shorts_visual_scenes.call_args.args[1],
                         'Water absorbs heat and changes into vapor.')
        fetch.assert_called_once()

    def test_overlong_narration_stops_before_assets_after_three_attempts(self):
        pipeline = self.pipeline()
        with patch('automation.media.hume_tts.get_audio_duration', return_value=70), patch(
                'automation.media.asset_orchestrator.AssetOrchestrator.fetch_all') as fetch:
            coroutine = pipeline._run_shorts('Water', False)
            with self.assertRaisesRegex(RuntimeError, 'bounded rewrites'):
                coroutine.send(None)
            coroutine.close()
        self.assertEqual(pipeline.tts.generate_audio.await_count, 3)
        fetch.assert_not_called()


class LongDirectorTests(unittest.TestCase):
    def test_batch_planning_preserves_entire_narration(self):
        from automation.content.script_writer import ScriptWriter
        writer = ScriptWriter.__new__(ScriptWriter)
        script = ' '.join(f'Water moves through channel {i} and carries heat away.' for i in range(45))
        def response(prompt, **kwargs):
            shots = json.loads(prompt.rsplit('Narration shots JSON: ', 1)[1].strip())
            return json.dumps({'scenes': [{'scene_id': shot['scene_id'], 'visual_type': 'image'}
                                          for shot in shots]})
        writer._call_with_retry = Mock(side_effect=response)
        scenes = writer.generate_visual_scenes('Heat', script)
        self.assertEqual(' '.join(s['narration'] for s in scenes), script)
        self.assertGreater(writer._call_with_retry.call_count, 1)


if __name__ == '__main__':
    unittest.main()
