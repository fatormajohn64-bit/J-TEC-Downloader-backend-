"""
J TEC Downloader
Core media downloader service.
"""

import zipfile
from pathlib import Path
from typing import Any, Callable, Optional

import yt_dlp

from app.config import settings


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".heic",
}


class DownloaderError(Exception):
    """Raised when a media operation fails."""


class DownloaderService:
    """Handles media information and downloads."""

    def __init__(self) -> None:
        self.download_dir = Path(settings.temp_download_dir)
        self.download_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    # -----------------------------------------------------
    # MEDIA INFORMATION
    # -----------------------------------------------------

    def get_info(self, url: str) -> dict[str, Any]:
        """
        Retrieve metadata and available media information.
        """

        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(
                    url,
                    download=False,
                )

            if not info:
                raise DownloaderError(
                    "No media information was returned."
                )

            image_count = self._count_images(url)

            return {
                "id": info.get("id"),
                "title": info.get("title"),
                "uploader": info.get("uploader"),
                "duration": info.get("duration"),
                "thumbnail": info.get("thumbnail"),
                "webpage_url": info.get("webpage_url"),
                "extractor": info.get("extractor_key"),
                "formats": self._get_formats(info),
                # Lets the frontend decide whether to offer an
                # "Image" download option for this specific link.
                "is_image_post": image_count > 0,
                "image_count": image_count,
            }

        except DownloaderError:
            raise

        except Exception as exc:
            raise DownloaderError(
                f"Unable to retrieve media information: {exc}"
            ) from exc

    def _count_images(self, url: str) -> int:
        """
        Best-effort check for how many downloadable images a
        post contains (e.g. an Instagram carousel). Never raises;
        an unknown/zero count just means the "image" option may
        not apply to this link.
        """

        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            # Multi-photo posts (Instagram carousels, TikTok photo
            # posts) are represented by yt-dlp as a small playlist
            # of image entries, so this must stay False here to see
            # all of them -- unlike the main info/download options,
            # which keep noplaylist True to avoid pulling in real
            # video playlists.
            "noplaylist": False,
            "extract_flat": True,
        }

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception:
            return 0

        if not info:
            return 0

        entries = info.get("entries")

        if entries:
            return len(list(entries))

        ext = str(info.get("ext") or "").lower()

        if f".{ext}" in IMAGE_EXTENSIONS:
            return 1

        return 0

    # -----------------------------------------------------
    # DOWNLOAD
    # -----------------------------------------------------

    def download(
        self,
        url: str,
        download_type: str = "video",
        quality: str = "best",
        progress_callback: Optional[
            Callable[[dict[str, Any]], None]
        ] = None,
    ) -> Path:
        """
        Download media in video, audio, or image mode.

        progress_callback receives yt-dlp progress updates.
        """

        if download_type not in {
            "video",
            "audio",
            "image",
        }:
            raise DownloaderError(
                "Download type must be 'video', 'audio', or 'image'."
            )

        output_template = str(
            self.download_dir /
            "%(id)s_%(title)s.%(ext)s"
        )

        options = {
            "quiet": True,
            "no_warnings": True,
            "outtmpl": output_template,
            "restrictfilenames": True,
            "continuedl": True,
        }

        # -------------------------------------------------
        # PROGRESS HOOK
        # -------------------------------------------------

        if progress_callback is not None:
            options["progress_hooks"] = [
                progress_callback
            ]

        # -------------------------------------------------
        # VIDEO
        # -------------------------------------------------

        if download_type == "video":
            options.update(
                {
                    "noplaylist": True,
                    "format": self._video_format(
                        quality
                    ),
                    "merge_output_format": "mp4",
                }
            )

        # -------------------------------------------------
        # AUDIO
        # -------------------------------------------------

        elif download_type == "audio":
            options.update(
                {
                    "noplaylist": True,
                    "format": "bestaudio/best",
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "320",
                        }
                    ],
                }
            )

        # -------------------------------------------------
        # IMAGE
        # -------------------------------------------------

        elif download_type == "image":
            options.update(
                {
                    # Photo carousels (Instagram) are represented
                    # as a small playlist of images -- allow all
                    # of them through instead of just the first.
                    "noplaylist": False,
                    # No "format" filter: image posts don't use
                    # yt-dlp's video quality ladder, this just
                    # grabs the original image(s) as-is.
                    "writethumbnail": True,
                    "skip_download": False,
                }
            )

        before = self._snapshot_dir()

        try:
            with yt_dlp.YoutubeDL(options) as ydl:

                info = ydl.extract_info(
                    url,
                    download=True,
                )

                if not info:
                    raise DownloaderError(
                        "Download returned no media information."
                    )

                if download_type == "image":
                    return self._finalize_image_download(
                        info,
                        before,
                    )

                files = self._find_downloaded_files(
                    info.get("id")
                )

                if not files:
                    raise DownloaderError(
                        "The media file could not be located."
                    )

                # Send a final 100% update.
                if progress_callback is not None:
                    self._send_progress(
                        progress_callback,
                        {
                            "status": "finished",
                            "progress": 100.0,
                            "downloaded_bytes": None,
                            "total_bytes": None,
                            "speed": None,
                            "eta": 0,
                        },
                    )

                return files[-1]

        except DownloaderError:
            raise

        except Exception as exc:
            raise DownloaderError(
                f"Media download failed: {exc}"
            ) from exc

    # -----------------------------------------------------
    # IMAGE DOWNLOAD FINALIZATION
    # -----------------------------------------------------

    def _finalize_image_download(
        self,
        info: dict[str, Any],
        before: set[str],
    ) -> Path:
        """
        Collect whatever image file(s) this download produced.

        A single photo becomes one file. A carousel (multiple
        photos) is zipped into one archive so the rest of the
        API -- which expects exactly one file per job -- doesn't
        need to change.
        """

        new_files = self._snapshot_dir() - before

        image_paths = sorted(
            (
                self.download_dir / name
                for name in new_files
                if (self.download_dir / name).suffix.lower()
                in IMAGE_EXTENSIONS
            ),
            key=lambda path: path.stat().st_mtime,
        )

        if not image_paths:
            raise DownloaderError(
                "No downloadable image was found for this link."
            )

        if len(image_paths) == 1:
            return image_paths[0]

        title = str(
            info.get("title")
            or info.get("id")
            or "images"
        )

        safe_title = "".join(
            char if char.isalnum() or char in (" ", "-", "_")
            else "_"
            for char in title
        ).strip() or "images"

        zip_path = (
            self.download_dir /
            f"{safe_title}.zip"
        )

        with zipfile.ZipFile(
            zip_path,
            "w",
            zipfile.ZIP_DEFLATED,
        ) as archive:
            for index, image_path in enumerate(
                image_paths,
                start=1,
            ):
                archive.write(
                    image_path,
                    arcname=f"{index:02d}{image_path.suffix}",
                )

        # The individual images are now inside the zip; remove
        # the loose copies so they don't linger in temp storage.
        for image_path in image_paths:
            image_path.unlink(missing_ok=True)

        return zip_path

    def _snapshot_dir(self) -> set[str]:
        """
        Filenames currently in the download directory. Used to
        work out exactly which files one download call produced,
        which is more reliable than id-matching for multi-file
        image posts.
        """

        return {
            path.name
            for path in self.download_dir.iterdir()
            if path.is_file()
        }

    # -----------------------------------------------------
    # PROGRESS
    # -----------------------------------------------------

    @staticmethod
    def _send_progress(
        callback: Callable[
            [dict[str, Any]],
            None,
        ],
        data: dict[str, Any],
    ) -> None:
        """
        Safely send progress information.

        A progress callback must never be allowed to
        break the actual download.
        """

        try:
            callback(data)

        except Exception:
            # Progress reporting is secondary.
            # Never fail a download because the UI
            # progress system encounters an error.
            pass

    # -----------------------------------------------------
    # FORMAT SELECTION
    # -----------------------------------------------------

    @staticmethod
    def _video_format(
        quality: str,
    ) -> str:
        """
        Select the highest appropriate video quality.
        """

        quality_map = {
            "best": (
                "bestvideo+bestaudio/"
                "best"
            ),
            "1080": (
                "bestvideo[height<=1080]+"
                "bestaudio/"
                "best[height<=1080]"
            ),
            "720": (
                "bestvideo[height<=720]+"
                "bestaudio/"
                "best[height<=720]"
            ),
            "480": (
                "bestvideo[height<=480]+"
                "bestaudio/"
                "best[height<=480]"
            ),
        }

        return quality_map.get(
            quality,
            quality_map["best"],
        )

    # -----------------------------------------------------
    # FORMAT INFORMATION
    # -----------------------------------------------------

    @staticmethod
    def _get_formats(
        info: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Return useful available formats without exposing
        unnecessary yt-dlp internals to the API.
        """

        formats = []

        for media_format in info.get(
            "formats",
            [],
        ):
            formats.append(
                {
                    "format_id":
                        media_format.get(
                            "format_id"
                        ),

                    "ext":
                        media_format.get(
                            "ext"
                        ),

                    "resolution":
                        media_format.get(
                            "resolution"
                        ),

                    "width":
                        media_format.get(
                            "width"
                        ),

                    "height":
                        media_format.get(
                            "height"
                        ),

                    "fps":
                        media_format.get(
                            "fps"
                        ),

                    "filesize":
                        media_format.get(
                            "filesize"
                        ),

                    "vcodec":
                        media_format.get(
                            "vcodec"
                        ),

                    "acodec":
                        media_format.get(
                            "acodec"
                        ),
                }
            )

        return formats

    # -----------------------------------------------------
    # FILE DISCOVERY
    # -----------------------------------------------------

    def _find_downloaded_files(
        self,
        media_id: str | None,
    ) -> list[Path]:
        """
        Locate files generated for a particular media ID.
        """

        if not media_id:
            return []

        files = []

        for path in self.download_dir.iterdir():

            if not path.is_file():
                continue

            if path.name.startswith(
                f"{media_id}_"
            ):
                files.append(path)

        return sorted(
            files,
            key=lambda path:
                path.stat().st_mtime,
        )


# ---------------------------------------------------------
# SHARED SERVICE INSTANCE
# ---------------------------------------------------------

downloader_service = DownloaderService()
