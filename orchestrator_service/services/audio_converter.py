"""
Audio conversion utilities for ClinicForge.

Used as a fallback when YCloud/WhatsApp rejects WebM audio:
  WebM/Opus → OGG/Opus via ffmpeg (server-side, subprocess-based).
"""

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


async def convert_webm_to_ogg(input_path: str) -> str | None:
    """
    Convert a WebM audio file to OGG/Opus using ffmpeg.

    Args:
        input_path: Absolute path to the .webm source file.

    Returns:
        Absolute path to the generated .ogg file on success,
        or None if ffmpeg is not available or conversion fails.
    """
    if not os.path.isfile(input_path):
        logger.warning(f"⚠️ audio_converter: source file not found: {input_path}")
        return None

    output_path = os.path.splitext(input_path)[0] + ".ogg"

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",                  # overwrite output without asking
            "-i", input_path,
            "-c:a", "libopus",     # re-encode as Opus inside OGG container
            "-vn",                 # drop any video stream
            output_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            logger.error(
                f"❌ audio_converter: ffmpeg timed out converting {input_path}"
            )
            return None

        if proc.returncode != 0:
            err_text = stderr.decode(errors="replace").strip()
            logger.error(
                f"❌ audio_converter: ffmpeg failed (rc={proc.returncode}) "
                f"for {input_path}: {err_text[-300:]}"
            )
            return None

        logger.info(
            f"✅ audio_converter: converted {os.path.basename(input_path)} → "
            f"{os.path.basename(output_path)}"
        )
        return output_path

    except FileNotFoundError:
        # ffmpeg binary not present on this host
        logger.warning(
            "⚠️ audio_converter: ffmpeg not found — WebM→OGG conversion unavailable"
        )
        return None
    except Exception as exc:
        logger.error(f"❌ audio_converter: unexpected error: {exc}")
        return None
