from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from PIL import Image

from automation.content.public_text import plain_public_text, overlay_headline
from automation.media.social_cover import create_social_cover


class PublicPostTests(unittest.TestCase):
    def test_emphasis_removed_without_losing_paragraphs_or_hashtags(self):
        text = '**The Sun** powers life.\n\nRead about *photosynthesis*.\n#Science #DailyDeepSpace'
        self.assertEqual(plain_public_text(text), 'The Sun powers life.\n\nRead about photosynthesis.\n#Science #DailyDeepSpace')

    def test_mathematical_stars_keep_their_meaning(self):
        self.assertEqual(plain_public_text('3 * 4 = 12; 2**3 = 8'), '3 × 4 = 12; 2^3 = 8')

    def test_unsubstantiated_number_in_headline_falls_back_to_topic(self):
        self.assertEqual(overlay_headline('99 planets vanished', 'Distant planets', 'A planet has been discovered.'), 'Distant planets')
        self.assertEqual(overlay_headline('**Why does Earth look blue?**', 'Earth', 'Earth looks blue.'), 'Why does Earth look blue?')

    def test_cover_is_feed_sized_and_preserves_source_file(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            source = Path(directory) / 'source.png'
            Image.new('RGB', (1600, 900), '#345678').save(source)
            original = source.read_bytes()
            cover = create_social_cover(source, 'Why does Earth look blue?')
            self.assertEqual(source.read_bytes(), original)
            with Image.open(cover) as image:
                self.assertEqual(image.size, (1080, 1350))
                self.assertEqual(image.mode, 'RGB')

    def test_one_generation_call_supplies_caption_and_overlay(self):
        from automation.content.script_writer import ScriptWriter
        writer = ScriptWriter.__new__(ScriptWriter)
        writer._call_with_retry = Mock(return_value='{"topic":"Earth ocean color","caption":"The **oceans** reflect blue light. #Science","overlay_headline":"**Why is Earth blue?**","image_query":"Earth from space"}')
        result = writer.generate_social_post('fun_fact')
        self.assertEqual(result['caption'], 'The oceans reflect blue light. #Science')
        self.assertEqual(result['overlay_headline'], 'Why is Earth blue?')
        writer._call_with_retry.assert_called_once()
        writer._call_with_retry.return_value = '{"caption":"broken JSON'
        self.assertEqual(writer.generate_social_post('fun_fact')['caption'], '')

    def test_youtube_upload_payload_is_plain_text(self):
        from automation.youtube.uploader import YouTubeUploader
        youtube = Mock()
        youtube.videos.return_value.insert.return_value.next_chunk.return_value = (None, {'id': 'mock-video'})
        with patch('automation.youtube.uploader.MediaFileUpload'):
            YouTubeUploader(youtube).upload_video('mock.mp4', '**A title**', 'A **clean** description', ['*Science*'])
        snippet = youtube.videos.return_value.insert.call_args.kwargs['body']['snippet']
        self.assertEqual(snippet['title'], 'A title')
        self.assertEqual(snippet['description'], 'A clean description')
        self.assertEqual(snippet['tags'], ['Science'])

    def test_meta_photo_upload_cleans_both_platform_captions(self):
        from automation.meta.uploader import MetaUploader
        uploader = MetaUploader.__new__(MetaUploader)
        uploader.access_token, uploader.page_id = 'mock-token', 'mock-page'
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            image = Path(directory) / 'image.jpg'
            Image.new('RGB', (20, 20)).save(image)
            with patch.object(uploader, '_upload_facebook_photo', return_value=('mock-photo', 'https://example.com/mock.jpg')) as facebook, \
                 patch.object(uploader, '_publish_photo_to_instagram') as instagram:
                uploader.upload_photo_post(str(image), 'A **bright** world. #Science')
            self.assertEqual(facebook.call_args.args[1], 'A bright world. #Science')
            self.assertEqual(instagram.call_args.args[1], 'A bright world. #Science')

    def test_youtube_reply_payload_is_plain_text(self):
        from automation.youtube.comment_handler import CommentHandler
        handler = CommentHandler.__new__(CommentHandler)
        handler.youtube = Mock()
        handler._post_reply('mock-parent', 'Thanks for asking about **gravity**!')
        snippet = handler.youtube.comments.return_value.insert.call_args.kwargs['body']['snippet']
        self.assertEqual(snippet['textOriginal'], 'Thanks for asking about gravity!')

    def test_meta_direct_photo_request_also_cleans_stars(self):
        from automation.meta.uploader import MetaUploader
        uploader = MetaUploader.__new__(MetaUploader)
        uploader.access_token, uploader.page_id, uploader.api_version = 'mock-token', 'mock-page', 'v19.0'
        response = Mock()
        response.json.return_value = {'id': 'mock-photo'}
        metadata = Mock()
        metadata.json.return_value = {'images': []}
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            image = Path(directory) / 'image.jpg'
            Image.new('RGB', (20, 20)).save(image)
            with patch('automation.meta.uploader.requests.post', return_value=response) as post, \
                 patch('automation.meta.uploader.requests.get', return_value=metadata):
                uploader._upload_facebook_photo(str(image), '**Earth** is blue.')
            self.assertEqual(post.call_args.kwargs['data']['caption'], 'Earth is blue.')


if __name__ == '__main__':
    unittest.main()
