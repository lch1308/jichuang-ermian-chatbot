"""语音观测的中文展示。生成要求、模型采样参数和声音测量分别呈现。"""
from typing import Any, Dict, List
import math


def _numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def render_speech_observation(data: Dict[str, Any]) -> List[str]:
    lines = []
    if data.get("voice_model"):
        lines.append("语音模型：" + str(data["voice_model"])[:100])
    runs = data.get("voice_generation_runs") or []
    valid_runs = [run for run in runs if isinstance(run, dict)]
    if valid_runs:
        params = valid_runs[0]
        names = (("temperature", "采样温度"), ("top_k", "候选数"), ("top_p", "概率覆盖"),
                 ("repetition_penalty", "重复惩罚"), ("audio_code_limit", "音频编码上限"))
        settings = [f"{name}{params[key]}" for key, name in names if _numeric(params.get(key))]
        if settings:
            lines.append("生成参数：" + "｜".join(settings))
        if _numeric(params.get("subtalker_temperature")):
            lines.append(f"子声码采样温度：{params['subtalker_temperature']}；分段合成：{len(valid_runs)}段")
        if any(run != params for run in valid_runs[1:]):
            lines.append("参数说明：以上为首段设置，后续分段设置有变化；各段原值已保存到结构化事件。")
        lines.append("参数含义：温度控制生成随机性，不是心情值、语速或声音温度。")
    if data.get("voice_parameter_status"):
        lines.append("参数观察：" + str(data["voice_parameter_status"])[:120])
    observed = data.get("voice_acoustics")
    if not isinstance(observed, dict):
        return lines  # 旧日志没有测量数据，不能编造。
    if observed.get("status") != "已测量":
        lines.append("音频观察：" + str(observed.get("status", "未提供"))[:120])
        return lines
    duration = observed.get("audio_seconds")
    rate = observed.get("sample_rate_hz")
    if _numeric(duration) and _numeric(rate):
        lines.append(f"实际音频：{duration:.2f}秒｜采样率{rate}Hz｜{observed.get('channels', 1)}声道")
    speed = observed.get("chars_per_second")
    if _numeric(speed):
        lines.append(f"文本语速粗估：{speed:.2f}有效字符/秒（含停顿）｜{observed.get('speed_description', '不分类')}")
    else:
        lines.append("文本语速粗估：" + str(observed.get("speed_description", "不足以估计")))
    thresholds = observed.get("speed_thresholds") or {}
    if _numeric(thresholds.get("slow")) and _numeric(thresholds.get("fast")):
        lines.append(f"语速判读：项目参考阈值{thresholds['slow']:g}～{thresholds['fast']:g}字符/秒；非专业标准、非音节测量。")
    pitch = observed.get("pitch_median_hz")
    pitch_range = observed.get("pitch_range_hz")
    if _numeric(pitch):
        description = f"音高粗估：基频中位数{pitch:.1f}Hz"
        if isinstance(pitch_range, list) and len(pitch_range) == 2 and all(_numeric(value) for value in pitch_range):
            description += f"｜主要范围{pitch_range[0]:.1f}～{pitch_range[1]:.1f}Hz"
        if _numeric(observed.get("pitch_span_semitones")):
            description += f"｜起伏约{observed['pitch_span_semitones']:.1f}半音"
        lines.append(description)
    else:
        lines.append("音高粗估：没有足够可靠的有声片段，不输出音高数字。")
    if _numeric(observed.get("low_energy_percent")):
        lines.append(f"低能量间隙：约{observed['low_energy_percent']:.1f}%｜≥0.15秒的间隙{observed.get('low_energy_gap_count', 0)}处｜最长{observed.get('longest_low_energy_gap_seconds', 0):.2f}秒（含首尾静音，不等于语义停顿）")
    if _numeric(observed.get("rms_dbfs")):
        lines.append(f"数字音量：RMS {observed['rms_dbfs']:.1f}dBFS（不是扬声器现实分贝）")
    if _numeric(duration) and duration > 0 and _numeric(data.get("duration_seconds")):
        lines.append(f"合成时间/音频时长：{data['duration_seconds']/duration:.2f}（越小生成越快，不代表说话语速）")
    if _numeric(observed.get("analysis_ms")):
        lines.append(f"观察额外耗时：{observed['analysis_ms']:.1f}毫秒；不调用额外AI，不改变原音频。")
    lines.append("测量边界：语速为文本/时长比值，未验证实际读音；音高和间隙为估计，不能据此断言真实情绪。")
    return lines


def render_voice_compact(data: Dict[str, Any], repeated: bool = False) -> List[str]:
    """日常日志保留因果链，不复制台词、不把模型采样温度当语速。"""
    from .readable import plain

    labels = {'neutral':'平静','joy':'开心','sadness':'难过','anger':'生气','confusion':'疑惑',
              'surprise':'惊讶','blush':'害羞','distressed':'委屈','comfort':'安慰',
              'thinking':'思考','sleepy':'困倦','playful':'调皮','curiosity':'好奇','listening':'倾听'}
    duration = data.get('duration_seconds')
    timing = f"｜合成耗时{duration:.2f}秒" if _numeric(duration) else ''
    lines = ['语音合成：'+plain(data.get('status','未记录'),120)+timing]
    if not repeated:
        mood = data.get('mood') or {}
        emotion = data.get('emotion') or {}
        label = emotion.get('label') if emotion.get('active') else '无额外情绪'
        value = mood.get('value')
        lines.append('心情→声音：心情'+(str(value) if _numeric(value) else '未记录')+
                     '｜情绪'+plain(label or '未记录',40)+' → '+labels.get(data.get('style'),'风格未记录'))
        if data.get('reason'):
            lines.append('选用原因：'+plain(data['reason'],350))
        lines.append('语音模型：'+plain(data.get('voice_model') or '后端未提供',100)+
                     ('｜声线 '+plain(data['voice_name'],80) if data.get('voice_name') else ''))
        lines.append('传给语音模型的语速/语调要求：'+plain(data.get('voice_instruction') or '后端未提供；不推测',600))
        observations = render_speech_observation(data)
        lines.extend(line for line in observations if line.startswith(('生成参数：','参数观察：')))
        if not data.get('voice_generation_runs'):
            lines.append('合成参数：后端未提供实际参数；不推测语速倍率')
        if data.get('assessment_pending'):
            lines.append('状态来源：本轮情绪尚未确认，采用合成开始时最近已确认状态')
        lines.append('含义：语调要求是给模型的指令；采样温度不是语速；下面是音频粗估，非模型内部思考')
    else:
        lines.append('说话风格与上一段相同，要求和参数已合并；本段声音观察如下')
    observed = data.get('voice_acoustics')
    if not isinstance(observed, dict):
        lines.append('实际声音观察：此记录未采集音频测量，不能补造语速/音高')
    elif observed.get('status') != '已测量':
        lines.append('实际声音观察：'+plain(observed.get('status','未提供'),150))
    else:
        parts=[]
        if _numeric(observed.get('audio_seconds')):
            parts.append(f"音频{observed['audio_seconds']:.2f}秒")
        if _numeric(observed.get('chars_per_second')):
            parts.append(f"语速约{observed['chars_per_second']:.2f}有效字符/秒（含停顿）")
        else:
            parts.append('语速不可可靠估计')
        if _numeric(observed.get('pitch_median_hz')):
            parts.append(f"音高中位数约{observed['pitch_median_hz']:.1f}Hz")
            if _numeric(observed.get('pitch_span_semitones')):
                parts.append(f"起伏约{observed['pitch_span_semitones']:.1f}半音")
        else:
            parts.append('无可靠音高估计')
        lines.append('实际声音粗估：'+'｜'.join(parts))
    return lines
