import yt_dlp

video_url = ""

ydl_opts = {}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(video_url, download=False)

    formats = info.get("formats", [])

    for f in formats:
        print(
            f"id={f.get('format_id')}",
            f"ext={f.get('ext')}",
            f"resolution={f.get('resolution')}",
            f"fps={f.get('fps')}",
            f"vcodec={f.get('vcodec')}",
            f"acodec={f.get('acodec')}",
            f"filesize={f.get('filesize')}"
        )
