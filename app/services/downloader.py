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
        Retrieve just enough metadata to show a preview --
        title, thumbnail, duration. One extraction call only,
        no format list, no second lookup.
        """

        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": 12,
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
            }

        except DownloaderError:
            raise

        except Exception as exc:
            raise DownloaderError(
                self._friendly_error(exc)
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
            # Speed: pull multiple video/audio fragments at once
            # instead of one at a time, and fail fast instead of
            # hanging on a slow/unresponsive host.
            "concurrent_fragment_downloads": 4,
            "socket_timeout": 15,
            "retries": 3,
            "fragment_retries": 3,
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
                self._friendly_error(exc)
            ) from exc

    # -----------------------------------------------------
    # FRIENDLY ERROR MESSAGES
    # -----------------------------------------------------

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        """
        Turn yt-dlp's raw (often technical) error text into one
        plain sentence the user can actually understand.
        """

        message = str(exc).lower()

        privacy_markers = (
            "private",
            "login",
            "log in",
            "sign in",
            "cookies",
            "authentication",
            "age-restricted",
            "age restricted",
            "permission",
            "subscriber",
            "followers",
        )

        removed_markers = (
            "unavailable",
            "not available",
            "removed",
            "does not exist",
            "not found",
            "deleted",
            "no longer",
        )

        geo_markers = (
            "geo",
            "not available in your country",
            "blocked in",
            "region",
        )

        unsupported_markers = (
            "unsupported url",
            "no extractor",
            "unable to extract",
        )

        if any(marker in message for marker in privacy_markers):
            return (
                "This content is private or restricted, "
                "so it can't be downloaded."
            )

        if any(marker in message for marker in removed_markers):
            return (
                "This content is unavailable -- it may "
                "have been deleted or taken down."
            )

        if any(marker in message for marker in geo_markers):
            return (
                "This content isn't available in the "
                "server's region."
            )

        if any(marker in message for marker in unsupported_markers):
            return "This link isn't from a supported site."

        return (
            "Unable to download this media. Please check "
            "the link and try again."
        )

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
