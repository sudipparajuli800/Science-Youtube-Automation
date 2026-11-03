import os
import requests
import random
import re
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

class ThumbnailGenerator:
    def __init__(self, size=(1280, 720)):
        self.size = size
        self.output_dir = "automation/storage/thumbnails"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate_thumbnail(self, info: dict, output_path: str = None, first_asset_path: str = None) -> str:
        """
        Generates a thumbnail image, routing to the premium science design if data is present.
        """
        if 'thumbnail_data' in info or 'hook_phrase' in info:
            return self.generate_science_thumbnail(info, output_path, first_asset_path)
            
        text = info.get('text', 'Amazing Science').upper()
        image_prompt = info.get('image_prompt', 'cinematic science background')
        
        if not output_path:
            clean_text = re.sub(r'[^a-zA-Z0-9]', '_', text)[:20]
            output_path = os.path.join(self.output_dir, f"thumb_{clean_text}.jpg")

        # 1. Generate/Fetch Background
        bg_file = None
        if first_asset_path and os.path.exists(first_asset_path):
            if first_asset_path.endswith('.mp4'):
                import moviepy.editor as mp
                try:
                    clip = mp.VideoFileClip(first_asset_path)
                    bg_file = os.path.join(self.output_dir, "temp_thumb_bg.jpg")
                    clip.save_frame(bg_file, t=0.5)
                    clip.close()
                except Exception as e:
                    print(f"[Thumbnail] Error extracting frame: {e}")
            else:
                bg_file = first_asset_path

        if not bg_file:
            bg_file = self._fetch_ai_background(image_prompt)

        if not bg_file:
            img = Image.new('RGB', self.size, color=(15, 25, 45))
        else:
            img = Image.open(bg_file).resize(self.size, Image.Resampling.LANCZOS)

        draw = ImageDraw.Draw(img)
        font = self._load_font(fsize=120)
        self._draw_dynamic_text(draw, text, font)

        img.save(output_path, "JPEG", quality=90)
        print(f"Thumbnail saved at: {output_path}")
        return output_path

    def _fetch_best_photo(self, query: str, filename: str, portrait: bool = False) -> str:
        """Tries Pexels/Pixabay (reliable official APIs, no rate-limit risk) first, then
        falls back to the DDG search below. Returns a local file path, or None."""
        from . import stock_media
        if stock_media.has_stock_api_keys():
            base = filename.rsplit('.', 1)[0]
            paths = stock_media.fetch_real_photos(query, 1, self.output_dir, base, portrait=portrait)
            if paths:
                return paths[0]
        url = self._search_image_url(query)
        if url:
            return self._download_url(url, filename)
        return None

    def _search_image_url(self, query: str) -> str:
        """Searches DuckDuckGo and returns the first valid image URL."""
        from duckduckgo_search import DDGS
        import time
        q = query[:60]
        forbidden = ["cartoon", "illustration", "vector", "drawing", "logo", "diagram"]
        for attempt in range(3):
            try:
                with DDGS() as ddgs:
                    results = ddgs.images(
                        keywords=q,
                        region="wt-wt",
                        safesearch="on",
                        size="large"
                    )
                    if results:
                        for r in results:
                            url = r.get("image", "")
                            if not url:
                                continue
                            if any(f in url.lower() for f in forbidden):
                                continue
                            return url
            except Exception as e:
                err_str = str(e)
                clean_q = query.encode('ascii', 'ignore').decode('ascii')
                clean_err = err_str.encode('ascii', 'ignore').decode('ascii')
                print(f"DDG Search error in ThumbnailGenerator for '{clean_q}': {clean_err[:200]}")
                if "403" in err_str or "429" in err_str or "forbidden" in err_str.lower() or "ratelimit" in err_str.lower():
                    print("[Thumbnail] DDG search rate limited. Skipping retries.")
                    break
                time.sleep(1)
        return None

    def _download_url(self, url: str, filename: str) -> str:
        """Downloads an image from a URL and saves it to storage."""
        save_path = os.path.join(self.output_dir, filename)
        try:
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/124.0.0.0 Safari/537.36'
                )
            }
            resp = requests.get(url, timeout=20, headers=headers)
            if resp.status_code != 200:
                print(f"[Thumbnail] Download HTTP {resp.status_code} for: {url[:80]}")
                return None
            if len(resp.content) > 500:
                with open(save_path, 'wb') as f:
                    f.write(resp.content)
                return save_path
        except Exception as e:
            print(f"[Thumbnail] Download error {url[:80]}: {e}")
        return None

    def generate_science_thumbnail(self, info: dict, output_path: str = None, first_asset_path: str = None) -> str:
        """
        Generates a premium science channel YouTube thumbnail (supports both landscape and portrait).
        """
        tdata = info.get('thumbnail_data', {})
        if not tdata:
            tdata = info
            
        hook_phrase = str(tdata.get('hook_phrase', 'AMAZING DISCOVERY')).upper()
        supporting_fact = str(tdata.get('supporting_fact', 'Scientists have uncovered a groundbreaking mystery.'))
        bg_query = str(tdata.get('thumbnail_bg_query', 'cinematic cosmic science background'))
        subject_query = str(tdata.get('thumbnail_subject_query', 'bismuth crystal structure closeup'))
        
        if not output_path:
            clean_text = re.sub(r'[^a-zA-Z0-9]', '_', hook_phrase)[:20]
            output_path = os.path.join(self.output_dir, f"thumb_{clean_text}.jpg")
            
        print(f"[Thumbnail] Generating premium science thumbnail. Hook: '{hook_phrase}'")
        
        width, height = self.size
        is_portrait = width < height

        # 1. Fetch Background Image via DDG or use first_asset_path
        bg_file = None
        if first_asset_path and os.path.exists(first_asset_path):
            if first_asset_path.endswith('.mp4'):
                import moviepy.editor as mp
                try:
                    clip = mp.VideoFileClip(first_asset_path)
                    bg_file = os.path.join(self.output_dir, "temp_thumb_bg.jpg")
                    clip.save_frame(bg_file, t=0.5)
                    clip.close()
                except Exception as e:
                    print(f"[Thumbnail] Error extracting frame: {e}")
            else:
                bg_file = first_asset_path
                
        if not bg_file:
            bg_file = self._fetch_best_photo(bg_query, "temp_thumb_bg.jpg", portrait=is_portrait)


        if bg_file and os.path.exists(bg_file):
            canvas = Image.open(bg_file).resize(self.size, Image.Resampling.LANCZOS)
        else:
            print("[Thumbnail] Background search failed, using Pollinations.ai fallback.")
            fallback_bg = self._fetch_ai_background(bg_query)
            if fallback_bg and os.path.exists(fallback_bg):
                canvas = Image.open(fallback_bg).resize(self.size, Image.Resampling.LANCZOS)
            else:
                canvas = Image.new('RGB', self.size, color=(10, 18, 30))
                
        # 2. Fetch Subject Image (Pexels/Pixabay first, DDG fallback)
        sub_file = self._fetch_best_photo(subject_query, "temp_thumb_subject.jpg", portrait=is_portrait)


        if not sub_file or not os.path.exists(sub_file):
            print("[Thumbnail] Subject search failed, using Pollinations.ai fallback for subject.")
            fallback_sub = self._fetch_ai_subject(subject_query)
            if fallback_sub and os.path.exists(fallback_sub):
                sub_file = fallback_sub
                
        if sub_file and os.path.exists(sub_file):
            try:
                sub_img = Image.open(sub_file)
                if is_portrait:
                    sub_size = (650, 650)
                else:
                    sub_size = (550, 550)
                sub_img = sub_img.resize(sub_size, Image.Resampling.LANCZOS)
                
                # Create radial gradient alpha mask using numpy
                sw, sh = sub_size
                x = np.linspace(-1, 1, sw)
                y = np.linspace(-1, 1, sh)
                xx, yy = np.meshgrid(x, y)
                r = np.sqrt(xx**2 + yy**2)
                
                mask = np.zeros((sh, sw), dtype=np.uint8)
                mask[r <= 0.6] = 255
                fade_mask = (r > 0.6) & (r <= 1.0)
                mask[fade_mask] = (255 * (1.0 - (r[fade_mask] - 0.6) / 0.4)).astype(np.uint8)
                mask[r > 1.0] = 0
                
                mask_img = Image.fromarray(mask, mode="L")
                
                # Apply mask to alpha channel
                sub_rgba = sub_img.convert("RGBA")
                sub_rgba.putalpha(mask_img)
                
                # Paste floating subject onto right side of canvas (landscape) or center-lower (portrait)
                canvas_rgba = canvas.convert("RGBA")
                if is_portrait:
                    paste_x = (width - 650) // 2
                    paste_y = height // 2 - 50
                else:
                    paste_x = 1280 - 580
                    paste_y = (720 - 550) // 2
                canvas_rgba.paste(sub_rgba, (paste_x, paste_y), sub_rgba)
                canvas = canvas_rgba.convert("RGB")
                print("[Thumbnail] Successfully composited floating subject image.")
            except Exception as e:
                print(f"[Thumbnail] Subject composting failed: {e}")
                
        # 3. Draw Dark left-third gradient overlay (landscape) or top dark gradient (portrait)
        overlay = Image.new("RGBA", self.size, (0, 0, 0, 0))
        o_draw = ImageDraw.Draw(overlay)
        if is_portrait:
            gradient_height = 800
            for y_coord in range(gradient_height):
                alpha = int(240 * (1.0 - y_coord / float(gradient_height)))
                o_draw.line([(0, y_coord), (width, y_coord)], fill=(5, 11, 20, alpha))
        else:
            for x_coord in range(600):
                alpha = int(230 * (1.0 - x_coord / 600.0))
                o_draw.line([(x_coord, 0), (x_coord, 720)], fill=(5, 11, 20, alpha))
            
        canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(canvas)
        
        # 4. Draw Left-Side Cyber Cyan Accent Bar
        if is_portrait:
            accent_x = 70
            accent_y1 = 200
            accent_y2 = 700
            bar_thickness = 10
        else:
            accent_x = 55
            accent_y1 = 150
            accent_y2 = 480
            bar_thickness = 8
        draw.rectangle([(accent_x, accent_y1), (accent_x + bar_thickness, accent_y2)], fill=(142, 218, 224))
        
        # 5. Draw Hook Phrase Text (large, bold, left-aligned)
        font_path = "automation/fonts/Barlow-Bold.ttf"
        if is_portrait:
            hook_font_size = 95
            line_spacing = 130
            text_x = 110
            text_y = 230
        else:
            hook_font_size = 80
            line_spacing = 110
            text_x = 85
            text_y = 170
            
        if not os.path.exists(font_path):
            font = self._load_font(hook_font_size)
        else:
            font = ImageFont.truetype(font_path, hook_font_size)
        
        words = hook_phrase.split()
        if len(words) >= 3:
            mid = len(words) // 2
            line1 = " ".join(words[:mid])
            line2 = " ".join(words[mid:])
        else:
            line1 = hook_phrase
            line2 = ""
            
        def draw_stroke_text(d, t, pos, fn, text_color):
            tx, ty = pos
            stroke = 1
            for dx in range(-stroke, stroke+1):
                for dy in range(-stroke, stroke+1):
                    if dx == 0 and dy == 0: continue
                    d.text((tx+dx, ty+dy), t, font=fn, fill=(0, 0, 0, 255))
            d.text((tx, ty), t, font=fn, fill=text_color)
            
        draw_stroke_text(draw, line1, (text_x, text_y), font, (255, 255, 255))
        if line2:
            draw_stroke_text(draw, line2, (text_x, text_y + line_spacing), font, (142, 218, 224))
            
        # 6. Draw Bottom Supporting Fact Strip
        if is_portrait:
            strip_h = 110
            strip_y = height - strip_h
            fact_font_size = 32
        else:
            strip_h = 75
            strip_y = 720 - strip_h
            fact_font_size = 22
        
        strip_overlay = Image.new("RGBA", self.size, (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(strip_overlay)
        s_draw.rectangle([(0, strip_y), (width, height)], fill=(10, 22, 40, 255))
        s_draw.rectangle([(0, strip_y), (width, strip_y + (5 if is_portrait else 4))], fill=(0, 240, 255, 255))
        
        canvas = Image.alpha_composite(canvas.convert("RGBA"), strip_overlay).convert("RGB")
        draw = ImageDraw.Draw(canvas)
        
        reg_font_path = "automation/fonts/Barlow-Regular.ttf"
        if not os.path.exists(reg_font_path):
            reg_font = self._load_font(fact_font_size)
        else:
            reg_font = ImageFont.truetype(reg_font_path, fact_font_size)
            
        fact_text = supporting_fact
        max_len = 65 if is_portrait else 95
        if len(fact_text) > max_len:
            fact_text = fact_text[:max_len-3] + "..."
            
        try:
            fw = reg_font.getbbox(fact_text)[2] - reg_font.getbbox(fact_text)[0]
        except AttributeError:
            fw = reg_font.getsize(fact_text)[0]
            
        fx = (width - fw) // 2
        fy = strip_y + (strip_h - fact_font_size) // 2
        
        draw.text((fx + 1, fy + 1), fact_text, font=reg_font, fill=(0, 0, 0, 200))
        draw.text((fx, fy), fact_text, font=reg_font, fill=(230, 245, 255))
        
        canvas.save(output_path, "JPEG", quality=95)
        print(f"[Thumbnail] Premium science thumbnail successfully written to {output_path}")
        return output_path

    def _fetch_ai_background(self, prompt: str) -> str:
        """Fetches a high-quality background from Pollinations.ai.
        Tries flux-schnell first, then bare default if that fails.
        """
        clean_prompt = re.sub(r'[^a-zA-Z0-9 ]', ' ', prompt).strip()
        full_prompt = f"cinematic 4k high contrast {clean_prompt}, vibrant colors, photorealistic, no people, no text"
        encoded = requests.utils.quote(full_prompt)
        seed = random.randint(1000, 999999)
        save_path = os.path.join(self.output_dir, "temp_bg.jpg")
        candidate_urls = [
            f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&seed={seed}&nologo=true&model=flux-schnell",
            f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&seed={seed}&nologo=true",
        ]
        for url in candidate_urls:
            try:
                response = requests.get(url, timeout=60)
                if response.status_code == 200 and len(response.content) > 1000:
                    with open(save_path, 'wb') as f:
                        f.write(response.content)
                    return save_path
                else:
                    print(f"[Thumbnail] Pollinations bg HTTP {response.status_code}.")
            except Exception as e:
                print(f"[Thumbnail] Pollinations bg error: {e}")
        return None

    def _fetch_ai_subject(self, prompt: str) -> str:
        """Fetches a subject image from Pollinations.ai centered on a black background.
        Tries flux-schnell first, then bare default if that fails.
        """
        clean_prompt = re.sub(r'[^a-zA-Z0-9 ]', ' ', prompt).strip()
        full_prompt = f"cinematic 4k macro shot of {clean_prompt}, deep black background, centered, photorealistic, no watermark, no text"
        encoded = requests.utils.quote(full_prompt)
        seed = random.randint(1000, 999999)
        save_path = os.path.join(self.output_dir, "temp_thumb_subject.jpg")
        candidate_urls = [
            f"https://image.pollinations.ai/prompt/{encoded}?width=512&height=512&seed={seed}&nologo=true&model=flux-schnell",
            f"https://image.pollinations.ai/prompt/{encoded}?width=512&height=512&seed={seed}&nologo=true",
        ]
        for url in candidate_urls:
            try:
                response = requests.get(url, timeout=60)
                if response.status_code == 200 and len(response.content) > 1000:
                    with open(save_path, 'wb') as f:
                        f.write(response.content)
                    return save_path
                else:
                    print(f"[Thumbnail] Pollinations subject HTTP {response.status_code}.")
            except Exception as e:
                print(f"[Thumbnail] Pollinations subject error: {e}")
        return None

    def _load_font(self, fsize=120):
        # Cross-platform robust font list
        font_paths = []
        if os.name == 'nt':
            windir = os.environ.get('WINDIR', 'C:\\Windows')
            font_paths += [
                os.path.join(windir, 'Fonts', 'ariblk.ttf'), # Arial Black
                os.path.join(windir, 'Fonts', 'impact.ttf'), # Impact
                os.path.join(windir, 'Fonts', 'arialbd.ttf'), # Arial Bold
                os.path.join(windir, 'Fonts', 'segoeuib.ttf'), # Segoe UI Bold
            ]
        else:
            font_paths += [
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ]
        
        # Then custom assets
        font_paths += [
            "automation/media/assets/Montserrat-Black.ttf",
            "automation/media/assets/NotoSansDevanagari-Regular.ttf"
        ]

        for path in font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, fsize)
                except: continue
        
        # Ultimate fallback for Windows
        if os.name == 'nt':
             return ImageFont.truetype("arial.ttf", fsize)
             
        return ImageFont.load_default()

    def _draw_dynamic_text(self, draw, text, font):
        """Draws large, high-contrast text with shadow and border."""
        W, H = self.size
        # Split text into lines if too long
        words = text.split()
        lines = []
        if len(words) > 3:
            lines.append(" ".join(words[:2]))
            lines.append(" ".join(words[2:]))
        else:
            lines.append(text)

        total_h = sum([draw.textbbox((0,0), line, font=font)[3] for line in lines]) + (len(lines)-1)*20
        y = (H - total_h) // 2

        for line in lines:
            bbox = draw.textbbox((0,0), line, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            x = (W - w) // 2
            
            # Draw Shadow
            draw.text((x+8, y+8), line, font=font, fill=(0,0,0,180))
            
            # Draw Thick Border (Stroke)
            stroke_width = 6
            for dx in range(-stroke_width, stroke_width+1):
                for dy in range(-stroke_width, stroke_width+1):
                    draw.text((x+dx, y+dy), line, font=font, fill='black')
            
            # Draw Main Text (Vibrant Yellow or White)
            draw.text((x, y), line, font=font, fill='#FFD700')
            y += h + 30

    def _add_branding(self, img):
        logo_path = "automation/media/assets/nepal_now_logo.png"
        if os.path.exists(logo_path):
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((150, 150))
            img.paste(logo, (50, 50), logo)
