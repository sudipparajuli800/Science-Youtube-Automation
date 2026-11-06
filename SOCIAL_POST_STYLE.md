# Social image headlines and plain public text

New Facebook/Instagram image posts include a short headline over the image to invite
readers into the full caption. The headline is generated in the same call as the
caption, so it does not add another model request. The brief asks for 3–7 specific,
accurate words, avoiding exaggerated claims, emojis, hashtags and generic shock copy.
An invalid/missing headline falls back to the post's actual topic. Numbers absent
from the caption are not accepted in the proposed headline.

The cover is a 1080 × 1350 RGB JPEG with Barlow type, a lower readability gradient,
a small channel label and a short invitation to read the caption. The main source
image retains its full frame instead of being stretched or hard-cropped. A separate
`_cover.jpg` file is created, preserving the original download. Both Facebook and
Instagram receive the finished cover. The full caption remains separate.

Public text passes through shared cleanup at generation and publishing boundaries:

- Emphasis asterisks are removed from captions, descriptions, titles and replies.
- Paragraphs, hashtags, emoji and ordinary punctuation remain intact.
- Mathematical `3 * 4` and `2**3` become `3 × 4` and `2^3`, preserving their meaning.
- Translated subtitle text is cleaned as well; SRT timestamps remain unchanged.
- Malformed JSON is not posted as a raw social caption.

Cleanup covers photo posts, Facebook videos/Reels, Instagram photos/Reels, YouTube
metadata and both platforms' comment-reply payloads. These changes apply to newly
generated/published content; they do not edit existing live posts.

The cover renderer and text cleanup need no additional external service. Posting
still uses the existing account credentials and workflow schedule. Testing uses
mocked publishing clients; no test post or reply is sent to a live account.
