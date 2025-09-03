import os
import re
from pathlib import Path

from pydub import AudioSegment

silence_duration = 500  # 静默时长，单位为毫秒


def parse_srt_time(time_str):
    """将 SRT 时间字符串（如 '00:01:23,456'）转换为毫秒"""
    match = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", time_str)
    if not match:
        raise ValueError(f"Invalid time format: {time_str}")

    hours, minutes, seconds, milliseconds = map(int, match.groups())
    return hours * 3600 * 1000 + minutes * 60 * 1000 + seconds * 1000 + milliseconds


def read_srt_file(file_path):
    """读取 SRT 文件并返回字幕块列表（包含编号、时间戳和文本）"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = [block.strip() for block in content.split("\n\n") if block.strip()]
    subtitles = []

    for block in blocks:
        lines = block.split("\n")
        if len(lines) < 3:
            continue

        idx_line = lines[0]
        time_line = lines[1]
        text_line = lines[2]

        # 提取编号
        idx_match = re.match(r"^\d+", idx_line)
        if not idx_match:
            continue
        idx = int(idx_match.group())

        start_time, end_time = time_line.split(" --> ")
        start = parse_srt_time(start_time)
        end = parse_srt_time(end_time)
        text = text_line

        subtitles.append({"idx": idx, "start": start, "end": end, "text": text})

    return subtitles


def format_time(milliseconds):
    """将毫秒转换为 SRT 格式的时间字符串（如 00:01:23,456）"""
    total_seconds = milliseconds / 1000
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    ms = int((total_seconds - int(total_seconds)) * 1000)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def add_silence(audio, silence_duration):
    """在音频前后添加静默（默认0.5秒）"""
    silence = AudioSegment.silent(duration=silence_duration)
    return silence + audio + silence


def generate_files(srt_file, audio_file, output_dir, silence_duration):
    # 读取 SRT
    subtitles = read_srt_file(srt_file)

    # 读取音频
    audio = AudioSegment.from_file(audio_file)

    # 去掉原文件扩展名，提取主名称
    base_name = Path(srt_file).stem

    for sub in subtitles:
        idx = sub["idx"]
        text = sub["text"]
        start = sub["start"]
        end = sub["end"]

        # 截取音频片段（按原始时间戳）
        chunk = audio[start:end]

        # 添加静默
        chunk_with_silence = add_silence(chunk, silence_duration)

        # 生成音频文件名
        audio_filename = f"{base_name}_{idx:03d}.wav"
        audio_path = os.path.join(output_dir, audio_filename)
        chunk_with_silence.export(audio_path, format="wav")

        # 新音频的起始时间是 0ms（即从新音频开始）
        duration = len(chunk_with_silence)  # 新音频的总长度（包括静默）

        start_time_new = silence_duration
        end_time_new = duration - silence_duration

        # 格式化时间戳
        srt_content = f"1\n{format_time(start_time_new)} --> {format_time(end_time_new)}\n{text}\n"

        # 生成字幕文件名
        srt_filename = f"{base_name}_{idx:03d}.srt"
        srt_path = os.path.join(output_dir, srt_filename)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        print(f"Generated {audio_filename} and {srt_filename}")


def srt2clip(srt_file, audio_file, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    generate_files(srt_file, audio_file, output_dir, silence_duration)


# 使用示例

if __name__ == "__main__":
    srt_file = "example.srt"  # 替换为你的 SRT 文件路径
    audio_file = "example.mp3"  # 替换为你的音频文件路径
    output_dir = "output_clips"  # 输出目录

    srt2clip(srt_file, audio_file, output_dir)
