import re
import shutil
from pathlib import Path

import gradio as gr
from pydub import AudioSegment
from srt2clip_b import srt2clip


def parse_srt(srt_path):
    # Read the file content using standard Python file reading
    with open(srt_path, encoding="utf-8") as f:
        content = f.read()

    # Split the content into lines
    lines = content.splitlines()
    result = []
    for i in range(0, len(lines), 4):
        if i + 3 >= len(lines):
            break
        idx = lines[i]
        start_time = lines[i + 1].split(" --> ")[0]
        end_time = lines[i + 1].split(" --> ")[1]
        text = lines[i + 2]
        result.append([idx, start_time, end_time, text])

    # Return the parsed result
    return result


# When a file is uploaded, parse it and store the original data
def update_table(file):
    original_data = parse_srt(file)
    return original_data


def save_edits(srt_input, data):
    # 将表格数据转换回 .srt 格式
    with open(srt_input, "w", encoding="utf-8") as f:
        for i, row in enumerate(data.values):
            # 检查 row 是否包含 4 个元素
            if len(row) == 4:
                idx, start_time, end_time, text = row
                f.write(f"{idx}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
            else:
                print(f"Skipping invalid row: {row}")  # 调试信息


# 将时间字符串转换为毫秒（用于音频剪辑）
def parse_srt_time(time_str):
    match = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", time_str)
    if not match:
        raise ValueError(f"Invalid time format: {time_str}")

    hours, minutes, seconds, milliseconds = map(int, match.groups())
    return hours * 3600 * 1000 + minutes * 60 * 1000 + seconds * 1000 + milliseconds


def add_silence(audio, silence_duration):
    """在音频前后添加静默（默认0.5秒）."""
    silence = AudioSegment.silent(duration=silence_duration)
    return silence + audio + silence


def format_time(milliseconds):
    """将毫秒转换为 SRT 格式的时间字符串（如 00:01:23,456）."""
    total_seconds = milliseconds / 1000
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    ms = int((total_seconds - int(total_seconds)) * 1000)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def extract_audio_clips(audio_input, data, evt: gr.SelectData):
    # 加载音频文件
    audio = AudioSegment.from_file(audio_input)

    # 只处理选中的行
    id_no, start_time, end_time, text = evt.row_value

    start_ms = parse_srt_time(start_time)
    end_ms = parse_srt_time(end_time)

    # 提取音频片段
    clip = audio[start_ms:end_ms]
    clip_with_silence = add_silence(clip, 500)

    # 保存为临时文件
    temp_dir = Path(audio_input).parent
    temp_name = Path(audio_input).stem
    wav_path = temp_dir.joinpath(f"{temp_name}_{id_no}.wav")
    clip_with_silence.export(str(wav_path), format="wav")

    # 生成对应的 SRT 文件
    srt_path = wav_path.with_suffix(".srt")

    start_time_new = 500
    end_time_new = len(clip_with_silence) - 500
    srt_content = (
        f"1\n{format_time(start_time_new)} --> {format_time(end_time_new)}\n{text}\n"
    )
    with Path.open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
    result = [str(wav_path), str(srt_path)]
    return result


def save_clip(text_clip, save_path):
    if not Path(save_path).is_dir() or save_path.strip() == "":
        gr.Warning("请输入有效路径！")
    else:
        try:
            audio_clip = text_clip.replace(".srt", ".wav")
            shutil.move(audio_clip, save_path)
            shutil.move(text_clip, save_path)
            gr.Info(f"文件{Path(text_clip).name}已保存。")
            gr.Info(f"文件{Path(audio_clip).name}已保存。")
        except Exception as e:
            gr.Warning(f"保存文件时出错: {e}")


with gr.Blocks(theme=gr.themes.Soft(), title="按字幕切分音频段") as demo:
    gr.Markdown(
        "**本程序仅提供有限的字幕文本编辑功能，本程序可以通过选择单元格以播放对应音频段，并保存此段音频和字幕（默认以字幕文件名称作为保存时的名称前缀）**",
    )
    with gr.Tab(label="单选保存"), gr.Column():
        with gr.Row():
            srt_input = gr.File(
                label="上传字幕文件",
                file_types=[".srt"],
                type="filepath",
            )
            audio_input = gr.File(
                label="上传音频文件",
                file_types=[".mp3", ".wav"],
                type="filepath",
            )
        output_table = gr.Dataframe(
            headers=["序号", "开始时间", "结束时间", "字幕内容"],
            label="SRT文件内容展示",
            interactive=True,
            static_columns=[
                0,
                1,
                2,
            ],  # Make first three columns static (non-editable)
        )
        audio_select = gr.Audio(
            label="音频片段",
        )
        text_select = gr.File(label="字幕片段", visible=False)
        save_path = gr.Textbox(
            label="保存路径",
            placeholder="请输入正确的目标文件夹",
        )
        save_btn = gr.Button("保存选中片段")
        # Update the table when a file is uploaded
        srt_input.change(fn=update_table, inputs=srt_input, outputs=output_table)
        # Save edits back to the .srt file when the table is edited
        output_table.change(fn=save_edits, inputs=[srt_input, output_table], outputs=[])

        output_table.select(
            fn=extract_audio_clips,
            inputs=[audio_input, output_table],
            outputs=[audio_select, text_select],
        )

        save_btn.click(
            fn=save_clip,
            inputs=[text_select, save_path],
            outputs=[],
        )

    with gr.Tab(label="多选保存"), gr.Column():
        with gr.Row():
            srt_input = gr.File(
                label="上传字幕文件",
                file_types=[".srt"],
                type="filepath",
            )
            audio_input = gr.File(
                label="上传音频文件",
                file_types=[".mp3", ".wav"],
                type="filepath",
            )
        save_path = gr.Textbox(
            label="保存路径",
            placeholder="请输入正确的目标文件夹",
        )
        save_btn = gr.Button("保存全部音频片段其及字幕")

        save_btn.click(
            fn=srt2clip,
            inputs=[srt_input, audio_input, save_path],
            outputs=[],
        )


demo.launch()
