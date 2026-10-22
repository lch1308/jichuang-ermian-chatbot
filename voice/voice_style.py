"""把已有心情翻译成语音风格；不额外调用聊天模型，不改写台词或心情。"""

ALIASES = {
    "平静": "neutral", "无": "neutral", "正常": "neutral", "中性": "neutral",
    "开心": "joy", "高兴": "joy", "兴奋": "joy", "happy": "joy",
    "开心兴奋": "joy", "难过": "sadness", "低落": "sadness", "悲伤": "sadness", "sad": "sadness",
    "生气": "anger", "愤怒": "anger", "angry": "anger", "疑惑": "confusion", "困惑": "confusion",
    "问号": "confusion", "confused": "confusion", "惊讶": "surprise", "感叹号": "surprise",
    "surprised": "surprise", "害羞": "blush", "脸红": "blush", "shy": "blush",
    "委屈": "distressed", "难受": "distressed", "好奇": "curiosity", "curious": "curiosity",
    "思考": "thinking", "安慰": "comfort", "困倦": "sleepy", "调皮": "playful", "倾听": "listening",
}
LABELS = {"neutral": "平静", "joy": "开心", "sadness": "难过", "anger": "生气", "confusion": "疑惑",
          "surprise": "惊讶", "blush": "害羞", "distressed": "委屈", "curiosity": "好奇", "thinking": "思考",
          "comfort": "安慰", "sleepy": "困倦", "playful": "调皮", "listening": "倾听"}


def select_style(context, config):
    """临时情绪优先；否则用已确认的心情风格。手动表情不冒充真实情绪。"""
    context = context or {}
    emotion = context.get("emotion") or {}
    mood = context.get("mood") or {}
    if emotion.get("active"):
        candidate = str(emotion.get("label", "neutral"))
        reason = "当前会话临时情绪"
    else:
        candidate = str(mood.get("expression") or mood.get("band") or "neutral")
        reason = "当前会话已确认心情"
    key = ALIASES.get(candidate, candidate.lower())
    if key not in config["styles"]:
        key = "neutral"
        reason += "（未配置对应语音风格，使用平静）"
    return {"key": key, "label": LABELS.get(key, key), "reason": reason,
            "instruct": config["base_style"] + config["styles"][key]}
