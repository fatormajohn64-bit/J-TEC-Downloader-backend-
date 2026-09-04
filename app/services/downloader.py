"""
J TEC Downloader
Core media downloader service.
"""

from pathlib import Path
from typing import Any, Callable, Optional

import yt_dlp

from app.config import settings


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

            return {
                "id": info.get("id"),
                "title": info.get("title"),
                "uploader": info.get("uploader"),
                "duration": info.get("duration"),
                "thumbnail": info.get("thumbnail"),
                "webpage_url": info.get("webpage_url"),
                "extractor": info.get("extractor_key"),
                "formats": self._get_formats(info),
            }

        except DownloaderError:
            raise

        except Exception as exc:
            raise DownloaderError(
                f"Unable to retrieve media information: {exc}"
            ) from exc

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
        Download media in video or audio mode.

        progress_callback receives yt-dlp progress updates.
        """

        if download_type not in {
            "video",
            "audio",
        }:
            raise DownloaderError(
                "Download type must be 'video' or 'audio'."
            )

        output_template = str(
            self.download_dir /
            "%(id)s_%(title)s.%(ext)s"
        )

        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
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
