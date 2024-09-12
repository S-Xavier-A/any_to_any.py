import os
import io
import fitz
import PyPDF2
import argparse
import subprocess
import numpy as np
from PIL import Image
from enum import Enum
from moviepy.editor import (
    AudioFileClip,
    VideoFileClip,
    VideoClip,
    ImageSequenceClip,
    ImageClip,
    concatenate_videoclips,
    concatenate_audioclips,
    clips_array,
)


class Category(Enum):
    AUDIO = "audio"
    IMAGE = "image"
    MOVIE = "movie"
    DOCUMENT = "document"
    MOVIE_CODECS = "movie_codecs"


class AnyToAny:
    """
    Taking an input directory of mp4 files, convert them to a multitude of formats using moviepy.
    Interact with the script using the command line arguments defined at the bottom of this file.
    """

    def __init__(self):
        # Setting up a dictionary of supported formats and respective information
        self._supported_formats = {
            Category.AUDIO: {
                "mp3": "libmp3lame",
                "flac": "flac",
                "aac": "aac",
                "ac3": "ac3",
                "dts": "dts",
                "ogg": "libvorbis",
                "wma": "wmav2",
                "wav": "pcm_s16le",
                "m4a": "aac",
                "aiff": "pcm_s16le",
                "weba": "libopus",
                "mka": "libvorbis",
                "wv": "wavpack",
                "tta": "tta",
                "m4b": "aac",
                "eac3": "eac3",
                "spx": "libvorbis",
                "mp2": "mp2",
                "caf": "pcm_s16be",
                "au": "pcm_s16be",
                "oga": "libvorbis",
                "opus": "libopus",
                "m3u8": "pcm_s16le",
                "w64": "pcm_s16le",
                "mlp": "mlp",
                "adts": "aac",
                "sbc": "sbc",
                "thd": "truehd",
            },
            Category.IMAGE: {
                "gif": self.to_gif,
                "png": self.to_frames,
                "jpg": self.to_frames,
                "bmp": self.to_bmp,
                "webp": self.to_webp,
                "tiff": self.to_frames,
                "tga": self.to_frames,
                "ps": self.to_frames,
                "ico": self.to_frames,
                "eps": self.to_frames,
                "jpeg2000": self.to_frames,
                "im": self.to_frames,
            },
            Category.DOCUMENT: {
                "pdf": self.to_frames,
            },
            Category.MOVIE: {
                "webm": "libvpx",
                "mov": "libx264",
                "mkv": "libx264",
                "avi": "libx264",
                "mp4": "libx264",
                "wmv": "wmv2",
                "flv": "libx264",
                "mjpeg": "mjpeg",
                "m2ts": "mpeg2video",
                "3gp": "libx264",
                "3g2": "libx264",
                "asf": "wmv2",
                "vob": "mpeg2video",
                "ts": "hevc",
                "raw": "rawvideo",
                "mpg": "mpeg2video",
                "mxf": "mpeg2video",
                "drc": "libx265",
                "swf": "flv",
                "f4v": "libx264",
                "m4v": "libx264",
                "mts": "mpeg2video",
                "m2v": "mpeg2video",
                "yuv": "rawvideo",
            },
            Category.MOVIE_CODECS: {
                "av1": {"lib": "libaom-av1", "fallback": "mkv"},
                "avc": {"lib": "libx264", "fallback": "mp4"},
                "vp9": {"lib": "libvpx-vp9", "fallback": "mp4"},
                "h265": {"lib": "libx265", "fallback": "mkv"},
                "h264": {"lib": "libx264", "fallback": "mkv"},
                "h263p": {"lib": "h263p", "fallback": "mkv"},
                "xvid": {"lib": "libxvid", "fallback": "mp4"},
                "mpeg4": {"lib": "mpeg4", "fallback": "mp4"},
                "theora": {"lib": "libtheora", "fallback": "ogv"},
                "mpeg2": {"lib": "mpeg2video", "fallback": "mp4"},
                "mpeg1": {"lib": "mpeg1video", "fallback": "mp4"},
                "hevc": {"lib": "libx265", "fallback": "mkv"},
                "prores": {"lib": "prores", "fallback": "mkv"},
                "vp8": {"lib": "libvpx", "fallback": "webm"},
                "huffyuv": {"lib": "huffyuv", "fallback": "mkv"},
                "ffv1": {"lib": "ffv1", "fallback": "mkv"},
                "ffvhuff": {"lib": "ffvhuff", "fallback": "mkv"},
                "v210": {"lib": "v210", "fallback": "mkv"},
                "v410": {"lib": "v410", "fallback": "mkv"},
                "v308": {"lib": "v308", "fallback": "mkv"},
                "v408": {"lib": "v408", "fallback": "mkv"},
                "zlib": {"lib": "zlib", "fallback": "mkv"},
                "qtrle": {"lib": "qtrle", "fallback": "mkv"},
                "snow": {"lib": "snow", "fallback": "mkv"},
                "svq1": {"lib": "svq1", "fallback": "mkv"},
                "utvideo": {"lib": "utvideo", "fallback": "mkv"},
                "cinepak": {"lib": "cinepak", "fallback": "mkv"},
                "msmpeg4": {"lib": "msmpeg4", "fallback": "mkv"},
                "h264_nvenc": {"lib": "h264_nvenc", "fallback": "mp4"},
                "vpx": {"lib": "libvpx", "fallback": "webm"},
                "h264_rgb": {"lib": "libx264rgb", "fallback": "mkv"},
                "mpeg2video": {"lib": "mpeg2video", "fallback": "mpg"},
                "prores_ks": {"lib": "prores_ks", "fallback": "mkv"},
                "vc2": {"lib": "vc2", "fallback": "mkv"},
                "flv1": {"lib": "flv", "fallback": "flv"},
            },
        }

        # Used in CLI information output
        self.supported_formats = [
            format
            for formats in self._supported_formats.values()
            for format in formats.keys()
        ]

    def _end_with_msg(self, exception: Exception, msg: str) -> None:
        # Single point of exit for the script
        if exception is not None:
            print(msg, "\n")
            raise exception(msg)
        else:
            print(msg)
            exit(1)

    def _audio_bitrate(self, format: str, quality: str) -> str:
        # Return bitrate for audio conversion
        # If formats allow for a higher bitrate, we shift our scale accordingly
        if format in [
            "flac",
            "wav",
            "aac",
            "aiff",
            "eac3",
            "dts",
            "au",
            "wv",
            "tta",
            "mlp",
        ]:
            return {
                "high": "500k",
                "medium": "320k",
                "low": "192k",
            }.get(quality, None)
        else:
            return {
                "high": "320k",
                "medium": "192k",
                "low": "128k",
            }.get(quality, None)

    def run(
        self,
        input_path_args: list,
        format: str,
        output: str,
        framerate: int,
        quality: str,
        merge: bool,
        concat: bool,
        delete: bool,
        across: bool,
    ) -> None:
        # Main function, convert media files to defined formats
        # or merge or concatenate, according to the arguments
        input_paths = []
        input_path_args = (
            input_path_args
            if input_path_args is not None
            else [os.path.dirname(os.getcwd())]
        )

        for _, arg in enumerate(input_path_args):
            # Custom handling of multiple input paths
            # (e.g. "-1 path1 -2 path2 -n pathn")
            if arg.startswith("-") and arg[1:].isdigit():
                input_paths.append(arg[2:])
            else:
                try:
                    input_paths[-1] = (input_paths[-1] + f" {arg}").strip()
                except IndexError:
                    input_paths.append(arg)

        if len(input_paths) == 1:
            self.output = output if output is not None else input_paths[0]
        else:
            # len(input_paths) > 1
            if not across:
                self.output = output if output is not None else None
            else:
                self.output = (
                    output if output is not None else os.path.dirname(os.getcwd())
                )

        # Check if the output dir exists - Create it otherwise
        if self.output is not None and not os.path.exists(self.output):
            os.makedirs(self.output)

        self.format = (
            format.lower() if format is not None else None
        )  # No format means no conversion (but maybe merge || concat)
        self.framerate = framerate  # Possibly no framerate means same as input
        self.delete = delete  # Delete mp4 files after conversion
        # Check if quality is set, if not, set it to None
        self.quality = (
            (quality.lower() if quality.lower() in ["high", "medium", "low"] else None)
            if quality is not None
            else None
        )

        # Merge movie files with equally named audio files
        self.merging = merge
        # Concatenate files of same type (img/movie/audio) back to back
        self.concatenating = concat

        file_paths = {}
        was_none = False

        for input in input_paths:
            # No input means working directory
            if os.path.isfile(str(input)):
                self.input = os.path.dirname(input)
            else:
                self.input = input

            file_paths = self._get_file_paths(self.input, file_paths)

            if not across:
                if self.output is None or was_none:
                    self.output = input
                    was_none = True
                self.process_file_paths(file_paths)
                file_paths = {}

        if across:
            if self.output is None:
                self.output = os.path.dirname(input_paths[0])
            self.process_file_paths(file_paths)

        print("[+] Job Finished")

    def process_file_paths(self, file_paths: dict) -> None:
        # Check if value associated to format is tuple/string or function to call specific conversion
        if self.format in self._supported_formats[Category.MOVIE].keys():
            self.to_movie(
                file_paths=file_paths,
                format=self.format,
                codec=self._supported_formats[Category.MOVIE][self.format],
            )
        elif self.format in self._supported_formats[Category.AUDIO].keys():
            self.to_audio(
                file_paths=file_paths,
                format=self.format,
                codec=self._supported_formats[Category.AUDIO][self.format],
            )
        elif self.format in self._supported_formats[Category.MOVIE_CODECS].keys():
            self.to_codec(
                file_paths=file_paths,
                codec=self._supported_formats[Category.MOVIE_CODECS][self.format],
            )
        elif self.format in self._supported_formats[Category.IMAGE].keys():
            self._supported_formats[Category.IMAGE][self.format](
                file_paths, self.format
            )
        elif self.format in self._supported_formats[Category.DOCUMENT].keys():
            self._supported_formats[Category.DOCUMENT][self.format](
                file_paths, self.format
            )
        elif self.merging:
            self.merge(file_paths)
        elif self.concatenating:
            self.concat(file_paths, self.format)
        else:
            # Handle unsupported formats here
            self._end_with_msg(
                ValueError,
                f"[!] Error: Output format must be one of {list(self.supported_formats)}",
            )

    def _get_file_paths(self, input: str, file_paths: dict = {}) -> dict:
        # Get media files from input directory
        def process_file(file_path: str) -> tuple:
            # Dissect "path/to/file.txt" into [path/to, file, txt]
            file_type = file_path.split(".")[-1].lower()
            file_name = os.path.basename(file_path).split(".")[0]
            path_to_file = os.path.dirname(file_path) + os.sep
            return path_to_file, file_name, file_type

        def schedule_file(file_info: tuple) -> None:
            # If supported, add file to respective category schedule
            for category in self._supported_formats.keys():
                if file_info[2] in self._supported_formats[category]:
                    file_paths[category].append(file_info)
                    print(f"\t[+] Scheduling: {file_info[1]}.{file_info[2]}")
                    break

        for directory in [input]:
            if not os.path.exists(directory):
                self._end_with_msg(
                    FileNotFoundError,
                    f"[!] Error: Directory {directory} does not exist.",
                )

        print(f"[>] Scheduling: {input}")

        # Check if file_paths is an empty dict
        if len(file_paths) == 0:
            file_paths = {category: [] for category in self._supported_formats}

        if input is not None and os.path.isfile(input):
            file_info = process_file(os.path.abspath(input))
            schedule_file(file_info)
        else:
            for file_name in os.listdir(input):
                file_path = os.path.abspath(os.path.join(input, file_name))
                file_info = process_file(file_path)
                schedule_file(file_info)

        if not any(file_paths.values()):
            self._end_with_msg(
                None, f"[!] Error: No convertible media files found in {input}"
            )
        return file_paths

    def _has_visuals(self, file_path_set: tuple) -> bool:
        try:
            VideoFileClip(self._join_back(file_path_set)).iter_frames()
            return True
        except Exception as _:
            pass
        return False

    def to_audio(self, file_paths: dict, format: str, codec: str) -> None:
        # Convert to audio
        # Audio to audio conversion
        for audio_path_set in file_paths[Category.AUDIO]:
            if audio_path_set[2] == format:
                continue
            audio = AudioFileClip(self._join_back(audio_path_set))
            out_path = os.path.abspath(
                os.path.join(self.output, f"{audio_path_set[1]}.{format}")
            )
            # Write audio to file
            try:
                audio.write_audiofile(
                    out_path,
                    codec=codec,
                    bitrate=self._audio_bitrate(format, self.quality),
                    fps=audio.fps,
                )
            except Exception as _:
                print(
                    "\n\n[!] Error: Source Sample Rate Incompatible With {format}: Trying Compatible Rate Instead...\n"
                )
                audio.write_audiofile(
                    out_path,
                    codec=codec,
                    bitrate=self._audio_bitrate(format, self.quality),
                    fps=48000,
                )
            audio.close()
            self._post_process(audio_path_set, out_path, self.delete)

        # Movie to audio conversion
        for movie_path_set in file_paths[Category.MOVIE]:
            out_path = os.path.abspath(
                os.path.join(self.output, f"{movie_path_set[1]}.{format}")
            )

            if self._has_visuals(movie_path_set):
                video = VideoFileClip(
                    self._join_back(movie_path_set), audio=True, fps_source="tbr"
                )
                audio = video.audio
                # Check if audio was found
                if audio is None:
                    print(
                        f'[!] No audio found in "{self._join_back(movie_path_set)}" - Skipping\n'
                    )
                    video.close()
                    continue

                audio.write_audiofile(
                    out_path,
                    codec=codec,
                    bitrate=self._audio_bitrate(format, self.quality),
                )

                audio.close()
                video.close()
            else:
                try:
                    # AudioFileClip works for audio-only video files
                    audio = AudioFileClip(self._join_back(movie_path_set))
                    audio.write_audiofile(
                        out_path,
                        codec=codec,
                        bitrate=self._audio_bitrate(format, self.quality),
                    )
                    audio.close()
                except Exception as _:
                    print(
                        f'[!] Failed to extract audio from audio-only file "{self._join_back(movie_path_set)}" - Skipping\n'
                    )
                    continue

            # Post process (delete mp4, print success)
            self._post_process(movie_path_set, out_path, self.delete)

    def to_codec(self, file_paths: dict, codec: dict) -> None:
        # Convert movie to same movie with different codec
        for codec_path_set in file_paths[Category.MOVIE]:
            out_path = os.path.abspath(
                os.path.join(
                    self.output,
                    f'{codec_path_set[1]}_{self.format}.{codec["fallback"]}',
                )
            )

            if self._has_visuals(codec_path_set):
                video = VideoFileClip(
                    self._join_back(codec_path_set), audio=True, fps_source="tbr"
                )

                try:
                    video.write_videofile(
                        out_path,
                        codec=codec["lib"],
                        fps=video.fps if self.framerate is None else self.framerate,
                        audio=True,
                    )
                except Exception as _:
                    if os.path.exists(out_path):
                        # There might be some residue left, remove it
                        os.remove(out_path)
                    print(
                        f'\n\n[!] Codec Incompatible with {codec_path_set[2]}: Trying Compatible Format {codec["fallback"]} Instead...\n'
                    )

                    video.write_videofile(
                        out_path,
                        codec=codec["lib"],
                        fps=video.fps if self.framerate is None else self.framerate,
                        audio=True,
                    )
                video.close()
            else:
                # Audio-only video file
                audio = AudioFileClip(self._join_back(codec_path_set))

                # Create new VideoClip with audio only
                clip = VideoClip(
                    lambda t: np.zeros(
                        (16, 16, 3), dtype=np.uint8
                    ),  # 16 black pixels required by moviepy
                    duration=audio.duration,
                )
                clip = clip.set_audio(audio)
                clip.write_videofile(
                    out_path,
                    codec=codec["lib"],
                    fps=24 if self.framerate is None else self.framerate,
                    audio=True,
                )

                clip.close()
                audio.close()

            self._post_process(codec_path_set, out_path, self.delete)

    def to_movie(self, file_paths: dict, format: str, codec: str) -> None:
        # Convert to movie with specified format
        pngs = bmps = jpgs = []
        for image_path_set in file_paths[Category.IMAGE]:
            # Depending on the format, different fragmentation is required
            if image_path_set[2] == "gif":
                clip = ImageSequenceClip(self._join_back(image_path_set), fps=24)
                out_path = os.path.abspath(
                    os.path.join(self.output, f"{image_path_set[1]}.{format}")
                )
                clip.write_videofile(
                    out_path,
                    codec=codec,
                    fps=clip.fps if self.framerate is None else self.framerate,
                    audio=True,
                )
                clip.close()
                self._post_process(image_path_set, out_path, self.delete)
            elif image_path_set[2] == "png":
                pngs.append(ImageClip(self._join_back(image_path_set)).set_duration(1))
            elif image_path_set[2] == "jpg":
                jpgs.append(ImageClip(self._join_back(image_path_set)).set_duration(1))
            elif image_path_set[2] == "bmp":
                bmps.append(ImageClip(self._join_back(image_path_set)).set_duration(1))

        # Pics to movie
        for pics in [pngs, jpgs, bmps]:
            if len(pics) > 0:
                final_clip = concatenate_videoclips(pics, method="compose")
                out_path = os.path.abspath(
                    os.path.join(self.output, f"merged.{format}")
                )
                final_clip.write_videofile(
                    out_path,
                    fps=24 if self.framerate is None else self.framerate,
                    codec=codec,
                )
                final_clip.close()

        # Movie to different movie
        for movie_path_set in file_paths[Category.MOVIE]:
            if not movie_path_set[2] == format:
                out_path = os.path.abspath(
                    os.path.join(self.output, f"{movie_path_set[1]}.{format}")
                )
                if self._has_visuals(movie_path_set):
                    video = VideoFileClip(
                        self._join_back(movie_path_set), audio=True, fps_source="tbr"
                    )
                    video.write_videofile(
                        out_path,
                        codec=codec,
                        fps=video.fps if self.framerate is None else self.framerate,
                        audio=True,
                    )
                    video.close()
                else:
                    # Audio-only video file
                    audio = AudioFileClip(self._join_back(movie_path_set))

                    # Create new VideoClip with audio only
                    clip = VideoClip(
                        lambda t: np.zeros(
                            (16, 16, 3), dtype=np.uint8
                        ),  # 16 black pixels required by moviepy
                        duration=audio.duration,
                    )

                    clip = clip.set_audio(audio)

                    clip.write_videofile(
                        out_path,
                        codec=codec,
                        fps=24 if self.framerate is None else self.framerate,
                        audio=True,
                    )

                    clip.close()
                    audio.close()

                self._post_process(movie_path_set, out_path, self.delete)

    def to_frames(self, file_paths: dict, format: str) -> None:
        # Converting to image frame sets
        # This works for images and movies only
        for image_path_set in file_paths[Category.IMAGE]:
            if image_path_set[2] == format:
                continue
            if image_path_set[2] == "gif":
                clip = ImageSequenceClip(self._join_back(image_path_set), fps=24)
                for _, frame in enumerate(
                    clip.iter_frames(fps=clip.fps, dtype="uint8")
                ):
                    frame_path = os.path.abspath(
                        os.path.join(
                            self.output,
                            f"{image_path_set[1]}-%{len(str(int(clip.duration * clip.fps)))}d.{format}",
                        )
                    )
                    Image.fromarray(frame).save(frame_path, format=format)
                clip.close()
                self._post_process(image_path_set, self.output, self.delete)
            else:
                if not os.path.exists(os.path.join(self.output, image_path_set[1])):
                    self.output = self.input
                img_path = os.path.abspath(
                    os.path.join(self.output, f"{image_path_set[1]}.{format}")
                )
                with Image.open(self._join_back(image_path_set)) as img:
                    img.convert("RGB").save(img_path, format=format)
                self._post_process(image_path_set, img_path, self.delete)

        for doc_path_set in file_paths[Category.DOCUMENT]:
            if doc_path_set[2] == format:
                continue
            if not os.path.exists(os.path.join(self.output, doc_path_set[1])):
                try:
                    os.makedirs(os.path.join(self.output, doc_path_set[1]))
                except OSError as e:
                    print(f"[!] Error: {e} - Setting output directory to {self.input}")
                    self.output = self.input

            if doc_path_set[2] == "pdf":
                # Per page, convert pdf to image
                pdf_path = self._join_back(doc_path_set)
                pdf = PyPDF2.PdfReader(pdf_path)
                img_path = os.path.abspath(
                    os.path.join(
                        os.path.join(self.output, doc_path_set[1]),
                        f"{doc_path_set[1]}-%{len(str(len(pdf.pages)))}d.{format}",
                    )
                )

                try:
                    os.makedirs(os.path.dirname(img_path), exist_ok=True)
                    self.output = os.path.dirname(img_path)
                except OSError as e:
                    print(f"[!] Error: {e} - Setting output directory to {self.input}")
                    self.output = self.input

                pdf_document = fitz.open(pdf_path)

                for page_num in range(len(pdf_document)):
                    pix = pdf_document[page_num].get_pixmap()
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    img_file = img_path % (page_num + 1)
                    img.save(img_file, format.upper())

                pdf_document.close()
                self._post_process(doc_path_set, img_path, self.delete)

        # Audio cant be image-framed, movies certrainly can
        for movie_path_set in file_paths[Category.MOVIE]:
            if self._has_visuals(movie_path_set):
                video = VideoFileClip(
                    self._join_back(movie_path_set), audio=False, fps_source="tbr"
                )
                if not os.path.exists(os.path.join(self.output, movie_path_set[1])):
                    try:
                        os.makedirs(os.path.join(self.output, movie_path_set[1]))
                    except OSError as e:
                        print(
                            f"[!] Error: {e} - Setting output directory to {self.input}"
                        )
                        self.output = self.input
                img_path = os.path.abspath(
                    os.path.join(
                        os.path.join(self.output, movie_path_set[1]),
                        f"{movie_path_set[1]}-%{len(str(int(video.duration * video.fps)))}d.{format}",
                    )
                )

                video.write_images_sequence(img_path, fps=video.fps)
                video.close()
                self._post_process(movie_path_set, img_path, self.delete)
            else:
                print(
                    f'[!] Skipping "{self._join_back(movie_path_set)}" - Audio-only video file'
                )

            if format == "pdf":
                # Merge all freshly created 1-page pdfs into one big pdf
                pdf_out_path = os.path.join(
                    self.output, movie_path_set[1], "merged.pdf"
                )
                pdfs = [
                    os.path.join(self.output, movie_path_set[1], file)
                    for file in os.listdir(os.path.join(self.output, movie_path_set[1]))
                    if file.endswith("pdf")
                ]
                print(f"\t[+] Merging {len(pdfs)} PDFs into {pdf_out_path}")
                pdfs.sort()
                pdf_merger = PyPDF2.PdfMerger()
                for pdf in pdfs:
                    pdf_merger.append(pdf)
                pdf_merger.write(pdf_out_path)
                pdf_merger.close()
                for pdf in pdfs:
                    os.remove(pdf)
                self._post_process(movie_path_set, pdf_out_path, self.delete)
            else:
                self._post_process(movie_path_set, img_path, self.delete)

    def to_gif(self, file_paths: dict, format: str) -> None:
        # All images in the input directory are merged into one gif
        if len(file_paths[Category.IMAGE]) > 0:
            images = []
            for image_path_set in file_paths[Category.IMAGE]:
                if image_path_set[2] == format:
                    continue
                with Image.open(self._join_back(image_path_set)) as image:
                    images.append(image.convert("RGB"))
            images[0].save(
                os.path.join(self.output, f"merged.{format}"),
                save_all=True,
                append_images=images[1:],
            )

        # Movies are converted to gifs as well, incorporating 1/3 of the frames
        for movie_path_set in file_paths[Category.MOVIE]:
            if self._has_visuals(movie_path_set):
                video = VideoFileClip(
                    self._join_back(movie_path_set), audio=False, fps_source="tbr"
                )
                gif_path = os.path.join(self.output, f"{movie_path_set[1]}.{format}")
                video.write_gif(gif_path, fps=video.fps // 3)
                video.close()
                self._post_process(movie_path_set, gif_path, self.delete)
            else:
                print(
                    f'[!] Skipping "{self._join_back(movie_path_set)}" - Audio-only video file'
                )

    def to_bmp(self, file_paths: dict, format: str) -> None:
        # Movies are converted to bmps, frame by frame
        for movie_path_set in file_paths[Category.MOVIE]:
            if self._has_visuals(movie_path_set):
                video = VideoFileClip(
                    self._join_back(movie_path_set), audio=False, fps_source="tbr"
                )
                bmp_path = os.path.join(self.output, f"{movie_path_set[1]}.{format}")
                # Split video into individual bmp frame images at original framerate
                for _, frame in enumerate(
                    video.iter_frames(fps=video.fps, dtype="uint8")
                ):
                    frame.save(
                        f"{bmp_path}-%{len(str(int(video.duration * video.fps)))}d.{format}",
                        format=format,
                    )
                self._post_process(movie_path_set, bmp_path, self.delete)
            else:
                print(
                    f'[!] Skipping "{self._join_back(movie_path_set)}" - Audio-only video file'
                )

        # Pngs and gifs are converted to bmps as well
        for image_path_set in file_paths[Category.IMAGE]:
            if image_path_set[2] == format:
                continue
            if image_path_set[2] in ["png", "jpg", "tiff", "tga", "eps"]:
                bmp_path = os.path.join(self.output, f"{image_path_set[1]}.{format}")
                with Image.open(self._join_back(image_path_set)) as img:
                    img.convert("RGB").save(bmp_path, format=format)
            elif image_path_set[2] == "gif":
                clip = VideoFileClip(self._join_back(image_path_set))
                for _, frame in enumerate(
                    clip.iter_frames(fps=clip.fps, dtype="uint8")
                ):
                    frame_path = os.path.join(
                        self.output,
                        f"{image_path_set[1]}-%{len(str(int(clip.duration * clip.fps)))}d.{format}",
                    )
                    Image.fromarray(frame).convert("RGB").save(
                        frame_path, format=format
                    )
            else:
                # Handle unsupported file types here
                print(
                    f"[!] Skipping {self._join_back(image_path_set)} - Unsupported format"
                )

    def to_webp(self, file_paths: dict, format: str) -> None:
        # Convert frames in webp format
        # Movies are converted to webps, frame by frame
        for movie_path_set in file_paths[Category.MOVIE]:
            if self._has_visuals(movie_path_set):
                video = VideoFileClip(
                    self._join_back(movie_path_set), audio=False, fps_source="tbr"
                )
                if not os.path.exists(os.path.join(self.output, movie_path_set[1])):
                    try:
                        os.makedirs(os.path.join(self.output, movie_path_set[1]))
                    except OSError as e:
                        print(
                            f"[!] Error: {e} - Setting output directory to {self.input}"
                        )
                        self.output = self.input
                img_path = os.path.abspath(
                    os.path.join(
                        os.path.join(self.output, movie_path_set[1]),
                        f"{movie_path_set[1]}-%{len(str(int(video.duration * video.fps)))}d.{format}",
                    )
                )
                video.write_images_sequence(img_path, fps=video.fps)
                video.close()
                self._post_process(movie_path_set, img_path, self.delete)
            else:
                print(
                    f'[!] Skipping "{self._join_back(movie_path_set)}" - Audio-only video file'
                )

        # Pngs and gifs are converted to webps as well
        for image_path_set in file_paths[Category.IMAGE]:
            if image_path_set[2] == format:
                continue
            if image_path_set[2] in ["png", "jpg", "tiff", "tga", "eps"]:
                webp_path = os.path.join(self.output, f"{image_path_set[1]}.{format}")
                with Image.open(self._join_back(image_path_set)) as img:
                    img.convert("RGB").save(webp_path, format=format)
            elif image_path_set[2] == "gif":
                clip = VideoFileClip(self._join_back(image_path_set))
                for _, frame in enumerate(
                    clip.iter_frames(fps=clip.fps, dtype="uint8")
                ):
                    frame_path = os.path.join(
                        self.output,
                        f"{image_path_set[1]}-%{len(str(int(clip.duration * clip.fps)))}d.{format}",
                    )
                    Image.fromarray(frame).convert("RGB").save(
                        frame_path, format=format
                    )
            else:
                # Handle unsupported file types here
                print(
                    f"[!] Skipping {self._join_back(image_path_set)} - Unsupported format"
                )

    def concat(self, file_paths: dict, format: str) -> None:
        # Concatenate files of same type (img/movie/audio) back to back
        # Concatenate audio files
        if file_paths[Category.AUDIO] and (
            format is None or format in self._supported_formats[Category.AUDIO]
        ):
            concat_audio = concatenate_audioclips(
                [
                    AudioFileClip(self._join_back(audio_path_set))
                    for audio_path_set in file_paths[Category.AUDIO]
                ]
            )
            format = "mp3" if format is None else format
            audio_out_path = os.path.join(self.output, f"concatenated_audio.{format}")
            concat_audio.write_audiofile(
                audio_out_path,
                codec=self._supported_formats[Category.AUDIO][format],
                bitrate=self._audio_bitrate(format, self.quality)
                if self.quality is not None
                else concat_audio.bitrate,
            )
            concat_audio.close()
        # Concatenate movie files
        if file_paths[Category.MOVIE] and (
            format is None or format in self._supported_formats[Category.MOVIE]
        ):
            concat_vid = concatenate_videoclips(
                [
                    VideoFileClip(
                        self._join_back(movie_path_set), audio=True, fps_source="tbr"
                    )
                    for movie_path_set in file_paths[Category.MOVIE]
                ],
                method="compose",
            )
            format = "mp4" if format is None else format
            video_out_path = os.path.join(self.output, f"concatenated_video.{format}")
            concat_vid.write_videofile(
                video_out_path,
                fps=concat_vid.fps if self.framerate is None else concat_vid.fps,
                codec=self._supported_formats[Category.MOVIE][format],
            )
            concat_vid.close()
        # Concatenate image files (make a gif out of them)
        if file_paths[Category.IMAGE] and (
            format is None or format in self._supported_formats[Category.IMAGE]
        ):
            gif_out_path = os.path.join(self.output, "concatenated_image.gif")
            concatenated_image = clips_array(
                [
                    [ImageClip(self._join_back(image_path_set)).set_duration(1)]
                    for image_path_set in file_paths[Category.IMAGE]
                ]
            )
            concatenated_image.write_gif(gif_out_path, fps=self.framerate)

        for category in file_paths.keys():
            for i, file_path in enumerate(file_paths[category]):
                self._post_process(
                    file_path, self.output, self.delete, show_status=(i == 0)
                )
        print("\t[+] Concatenation completed")

    def merge(self, file_paths: dict) -> None:
        # For movie files and equally named audio file, merge them together under same name
        # (movie with audio with '_merged' addition to name)
        # Iterate over all movie file path sets
        found_audio = False
        for movie_path_set in file_paths[Category.MOVIE]:
            # Check if there is a corresponding audio file
            audio_fit = next(
                (
                    audio_set
                    for audio_set in file_paths[Category.AUDIO]
                    if audio_set[1] == movie_path_set[1]
                ),
                None,
            )
            if audio_fit is not None:
                found_audio = True
                # Merge movie and audio file
                video, audio = (
                    VideoFileClip(
                        self._join_back(movie_path_set), audio=False, fps_source="tbr"
                    ),
                    AudioFileClip(self._join_back(audio_fit)),
                )
                video.audio = audio
                merged_out_path = os.path.join(
                    self.output, f"{movie_path_set[1]}_merged.{movie_path_set[2]}"
                )
                video.write_videofile(
                    merged_out_path,
                    fps=video.fps if self.framerate is None else self.framerate,
                    codec=self._supported_formats[Category.MOVIE][movie_path_set[2]],
                )
                audio.close()
                video.close()
                # Post process (delete mp4+audio, print success)
                self._post_process(movie_path_set, merged_out_path, self.delete)
                self._post_process(
                    audio_fit, merged_out_path, self.delete, show_status=False
                )

        if not found_audio:
            print("[!] No audio files found to merge with movie files")

    def _post_process(
        self,
        file_path_set: tuple,
        out_path: str,
        delete: bool,
        show_status: bool = True,
    ) -> None:
        # Post process after conversion, print, delete source file if desired
        if show_status:
            print(
                f'\t[+] Converted "{self._join_back(file_path_set)}" to "{out_path}"\n'
            )
        if delete:
            os.remove(self._join_back(file_path_set))
            print(f'\t[-] Removed "{self._join_back(file_path_set)}"')

    def _join_back(self, file_path_set: tuple) -> str:
        # Join back the file path set to a concurrent path
        return os.path.abspath(
            f"{file_path_set[0]}{file_path_set[1]}.{file_path_set[2]}"
        )


if __name__ == "__main__":
    # An object is interacted with through a CLI-interface
    # Check if required libraries are installed
    for lib in ["moviepy", "PIL"]:
        try:
            __import__(lib)
        except ImportError as ie:
            print(f"Please install {lib}: {ie}")
            exit(1)

    any_to_any = AnyToAny()

    parser = argparse.ArgumentParser(
        description="Convert media files to different media formats"
    )
    parser.add_argument(
        "-i",
        "--input",
        nargs="+",
        help="Directory containing media files to be converted, Working Directory if none provided",
        type=str,
        required=False,
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Directory to save files, writing to mp4 path if not provided",
        type=str,
        required=False,
    )
    parser.add_argument(
        "-f",
        "--format",
        help=f'Set the output format ({", ".join(any_to_any.supported_formats)})',
        type=str,
        required=False,
    )
    parser.add_argument(
        "-m",
        "--merge",
        help="Per movie file, merge to movie with equally named audio file",
        action="store_true",
        required=False,
    )
    parser.add_argument(
        "-c",
        "--concat",
        help="Concatenate files of same type (img/movie/audio) back to back",
        action="store_true",
        required=False,
    )
    parser.add_argument(
        "-fps",
        "--framerate",
        help="Set the output framerate (default: same as input)",
        type=int,
        required=False,
    )
    parser.add_argument(
        "-q",
        "--quality",
        help="Set the output quality (high, medium, low)",
        type=str,
        required=False,
    )
    parser.add_argument(
        "-d",
        "--delete",
        help="Delete mp4 files after conversion",
        action="store_true",
        required=False,
    )
    parser.add_argument(
        "-w",
        "--web",
        help="Ignores all other arguments, starts web server + frontend",
        action="store_true",
        required=False,
    )
    parser.add_argument(
        "-a",
        "--across",
        help="Execute merging or concatenation across all input directories, not per each individually",
        action="store_true",
        required=False,
    )

    args = vars(parser.parse_args())

    if args["web"]:
        # Check for web frontend request
        if os.name in ["nt"]:
            subprocess.run("python ./web_to_any.py", shell=True)
        else:
            subprocess.run("python3 ./web_to_any.py", shell=True)
    else:
        # Run main function with parsed arguments
        any_to_any.run(
            input_path_args=args["input"],
            format=args["format"],
            output=args["output"],
            framerate=args["framerate"],
            quality=args["quality"],
            merge=args["merge"],
            concat=args["concat"],
            delete=args["delete"],
            across=args["across"],
        )
