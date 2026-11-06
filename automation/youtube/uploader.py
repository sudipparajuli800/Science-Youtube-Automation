from googleapiclient.http import MediaFileUpload
from .auth import YouTubeAuth
from ..content.public_text import plain_public_text

class YouTubeUploader:
    def __init__(self, youtube_service=None):
        self.youtube = youtube_service

    def upload_video(self, file_path, title, description, tags, category_id="25", privacy_status="public"):
        """
        Uploads a video to YouTube.
        """
        if not self.youtube:
            print("YouTube service not initialized.")
            return None

        title = plain_public_text(title)
        description = plain_public_text(description)
        tags = [plain_public_text(tag) for tag in (tags or [])]

        # Sanitize description
        if description:
            # YouTube API errors on < and > in descriptions
            description = description.replace("<", "").replace(">", "")
            # Truncate if too long (5000 is limit, keep safety margin)
            if len(description) > 4900:
                description = description[:4900] + "..."

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': category_id
            },
            'status': {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False
            }
        }

        media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
        request = self.youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")
        
        print(f"Video uploaded successfully! ID: {response.get('id')}")
        return response.get('id')
    def upload_caption(self, video_id, srt_path, language="en", name="English"):
        """
        Uploads a caption file for a specific video.
        """
        if not self.youtube:
            print("YouTube service not initialized.")
            return None

        print(f"Uploading captions for video {video_id}...")
        body = {
            'snippet': {
                'videoId': video_id,
                'language': language,
                'name': name,
                'isDefault': True
            }
        }

        media = MediaFileUpload(srt_path, chunksize=-1, resumable=True)
        request = self.youtube.captions().insert(
            part="snippet",
            body=body,
            media_body=media
        )

        response = request.execute()
        print(f"Captions uploaded successfully! ID: {response.get('id')}")
        return response.get('id')

    def upload_thumbnail(self, video_id, image_path):
        """
        Uploads a custom thumbnail for a specific video.
        """
        if not self.youtube:
            print("YouTube service not initialized.")
            return False

        try:
            print(f"Uploading thumbnail for video {video_id} from {image_path}...")
            request = self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(image_path)
            )
            response = request.execute()
            print("Thumbnail uploaded successfully!")
            return True
        except Exception as e:
            print(f"Thumbnail upload failed: {e}")
            return False
