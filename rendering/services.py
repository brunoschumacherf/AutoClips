from statistics import median

from core.media import materialize, run_media

FONTS = ("DejaVu Sans", "DejaVu Serif", "DejaVu Sans Mono")
FORMATS = {"9:16": (9, 16), "16:9": (16, 9), "1:1": (1, 1)}


def timestamp(seconds, separator, digits):
    scale = 10 ** digits
    total = max(0, round(seconds * scale))
    hours, rest = divmod(total, 3600 * scale)
    minutes, rest = divmod(rest, 60 * scale)
    whole, fractional = divmod(rest, scale)
    return f"{hours:02}:{minutes:02}:{whole:02}{separator}{fractional:0{digits}}"


def ass_text(text):
    return text.replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", r"\N").replace("\r", "")


def caption_files(version, folder, width, height):
    srt = folder / "clip.srt"
    vtt = folder / "clip.vtt"
    ass = folder / "clip.ass"
    color = version.style.get("color", "#FFFFFF")[1:]
    primary = "&H00" + color[4:6] + color[2:4] + color[:2]
    font = version.style.get("font", FONTS[0])
    outline = version.style.get("outline", 3)
    shadow = version.style.get("shadow", 1)
    vertical_margin = round(height * (1 - version.style.get("position", 74) / 100))
    size = round(min(width, height) * 0.057)
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font},{size},{primary},&H0000DFFF,&H00000000,&H88000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,28,28,{vertical_margin},1",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    srt_lines, vtt_lines = [], ["WEBVTT\n"]
    for index, caption in enumerate(version.captions, 1):
        start, end = caption["start"] - version.start, caption["end"] - version.start
        body = caption["text"].replace("\r", "").replace("\n", " ")
        srt_lines.append(f"{index}\n{timestamp(start, ',', 3)} --> {timestamp(end, ',', 3)}\n{body}\n")
        vtt_lines.append(f"{timestamp(start, '.', 3)} --> {timestamp(end, '.', 3)}\n{body.replace('&', '&amp;').replace('<', '&lt;')}\n")
        words = caption.get("words", [])
        groups = [words[offset:offset + 7] for offset in range(0, len(words), 7)]
        if not groups:
            lines.append(f"Dialogue: 0,{timestamp(start, '.', 2)},{timestamp(end, '.', 2)},Default,,0,0,0,,{ass_text(body)}")
        for group in groups:
            for active, word in enumerate(group):
                begin = word["start"] - version.start
                tail = group[active + 1]["start"] - version.start if active + 1 < len(group) else word["end"] - version.start
                text = " ".join(
                    r"{\c&H00DFFF&}" + ass_text(item["text"]) + r"{\r}" if index == active else ass_text(item["text"])
                    for index, item in enumerate(group)
                )
                if tail > begin:
                    lines.append(f"Dialogue: 0,{timestamp(begin, '.', 2)},{timestamp(tail, '.', 2)},Default,,0,0,0,,{text}")
    srt.write_text("\n".join(srt_lines), encoding="utf-8")
    vtt.write_text("\n".join(vtt_lines), encoding="utf-8")
    ass.write_text("\n".join(lines), encoding="utf-8")
    return srt, vtt, ass


def crop_center(version, signals):
    manual = version.style.get("center")
    if manual is not None:
        return f"{manual:.4f}"
    samples = [(second - version.start, center) for second, center in signals.get("faces", [])
               if version.start <= second <= version.end]
    if not samples:
        return "0.5"
    if len(samples) == 1:
        return f"{samples[0][1]:.4f}"
    # A median window suppresses single-frame jumps to another face.
    samples = [(time, median(center for _, center in samples[max(0, index - 1):index + 2]))
               for index, (time, _) in enumerate(samples)]
    expression = f"{samples[-1][1]:.4f}"
    for (start, left), (end, right) in reversed(list(zip(samples, samples[1:]))):
        transition = f"{left:.4f}+({right - left:.4f})*clip((t-{start:.4f})/{end - start:.4f},0,1)"
        expression = f"if(lt(t,{end:.4f}),{transition},{expression})"
    return expression.replace(",", r"\,")


def fit_panel(width, height):
    return (f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1")


def render(version, folder, plan):
    video = version.clip.video
    source = materialize(video.source, folder / "source")
    ratio_width, ratio_height = FORMATS[version.aspect]
    quality = min(int(video.options["quality"]), plan.max_height)
    base = quality if quality % 2 == 0 else quality - 1
    width, height = base * ratio_width // ratio_height // 2 * 2, base
    srt, vtt, ass = caption_files(version, folder, width, height)
    output = folder / "clip.mp4"
    thumbnail = folder / "thumbnail.jpg"
    if webcam := version.style.get("webcam"):
        x, y, crop_width, crop_height = (value / 100 for value in webcam)
        top = height // 6 * 2
        bottom = height - top
        filters = (
            "[0:v:0]split=2[camera][game];"
            f"[camera]crop=iw*{crop_width}:ih*{crop_height}:iw*{x}:ih*{y},"
            f"{fit_panel(width, top)}[face];"
            f"[game]{fit_panel(width, bottom)}[play];"
            f"[face][play]vstack=inputs=2,ass={ass}[video]"
        )
    else:
        analysis = getattr(video, "aianalysis", None)
        center = crop_center(version, analysis.signals if analysis else {})
        filters = (f"[0:v:0]scale={width}:{height}:force_original_aspect_ratio=increase:force_divisible_by=2,"
                   f"crop={width}:{height}:max(0\\,min(iw-ow\\,iw*({center})-ow/2)):(ih-oh)/2,"
                   f"setsar=1,ass={ass}[video]")
    run_media("ffmpeg", "-nostdin", "-v", "error", "-ss", version.start,
              "-protocol_whitelist", "file", "-format_whitelist", "mov,matroska", "-i", source,
              "-t", version.end - version.start, "-filter_complex_threads", "1",
              "-filter_complex", filters, "-map", "[video]", "-map", "0:a:0?", "-threads", "2",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
              "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", output)
    run_media("ffmpeg", "-nostdin", "-v", "error", "-i", output, "-frames:v", "1", "-threads", "1", thumbnail)
    return {"output": output, "thumbnail": thumbnail, "srt": srt, "vtt": vtt}
