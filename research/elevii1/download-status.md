# elevii1 Download Status

Last updated: 2026-06-12

## Current Snapshot

- Indexed TikTok posts: 391
- Downloaded media IDs: 368
- MP4 video posts: 347
- Audio-only/photo-mode posts detected by yt-dlp: 21
- Recovered slideshow/photo-mode posts with gallery-dl: 21
- Recovered slideshow images: 120
- Recovered slideshow audio files: 21
- Missing after cookie retry: 23
- Slideshows still needing recovery: 0

## Notes

- The `content/` folder contains downloaded TikTok videos and yt-dlp sidecars. It is ignored by git.
- The `slideshows/` folder contains recovered TikTok photo-mode images/audio from gallery-dl. It is ignored by git.
- `missing-after-retry-urls.txt` lists normal posts still not downloadable from the current extractor/page responses.
- `slideshow-audio-only-urls.txt` lists photo-mode posts detected by yt-dlp as audio-only.
- `slideshow-needs-recovery-urls.txt` is empty when every detected photo-mode post has recovered images.
- No research analysis has been started yet.
