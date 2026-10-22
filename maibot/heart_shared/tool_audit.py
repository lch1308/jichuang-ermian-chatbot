"""只记录已执行的工具和公开参数，不记录LLM隐藏思考，不凭最近消息猜归属。"""

from pathlib import Path
from typing import Any, Sequence
import tomllib

from .storage import AuditStore, clean


FORBIDDEN = {'reasoning', 'thought', 'thinking', 'chain_of_thought', 'system_prompt', 'prompt',
             'reply_reference', 'base64_data', 'data', 'binary', 'audio', 'image', 'extra_content'}
TITLES = {'query_weather': '天气查询', 'tool_search': '寻找可用工具', 'query_memory': '长期记忆查询',
          'query_person_profile': '人物画像查询', 'reply': '生成回复', 'wait': '等待',
          'send_emoji': '发送表情包', 'send_image': '发送图片', 'fetch_history': '读取聊天历史'}


def safe(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return '[深层详情已省略]'
    if isinstance(value, dict):
        return {str(k): safe(v, depth + 1) for k, v in list(value.items())[:35]
                if str(k).lower() not in FORBIDDEN}
    if isinstance(value, (tuple, list)):
        return [safe(v, depth + 1) for v in value[:15]]
    if isinstance(value, str):
        return value[:4096] + ('…[已截断]' if len(value) > 4096 else '')
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return '[非文本详情已省略]'


def payload(tool: str, arguments: dict, result: dict, duration_ms: float, source: str,
            error: str = '') -> dict:
    args = safe(clean(arguments))
    result = safe(clean(result))
    ok = result.get('success') is True if isinstance(result, dict) else False
    status = '成功' if ok else '失败'
    if error:
        status = '取消/结果未确认' if error.startswith('取消') else '失败'
    found = None
    if tool == 'tool_search' and isinstance(result, dict):
        matched = result.get('matched_tool_names')
        if isinstance(matched, list):
            found = bool(matched)
            status = '已找到可用工具' if found else '未找到匹配工具（寻找过程正常完成）'
    purpose = args.get('purpose') if isinstance(args, dict) else ''
    return {'tool_name': tool, 'tool_title': TITLES.get(tool, tool), 'arguments': args,
            'status': status, 'success': ok, 'found': found, 'source': source,
            'purpose': purpose or ('用户明确发送天气指令' if source == '用户天气指令'
                                   else '模型未提供独立简短说明；不记录内部思考'),
            'duration_ms': round(duration_ms, 2), 'result': result,
            'error': error or (result.get('error', '') if isinstance(result, dict) else ''),
            'note': '工具结果已返回；不等于回复模型最终采用。'}


def record_tool(session: str, tool: str, arguments: dict, result: dict, *, evidence_ids: Sequence[str] = (),
                duration_ms: float = 0, source: str = '规划器选择工具', error: str = '',
                event_id: str | None = None, store: AuditStore | None = None) -> None:
    if store is None:
        config = Path(__file__).resolve().parents[1] / 'plugins/heart_memory_audit/config.toml'
        if not tomllib.loads(config.read_text(encoding='utf-8-sig')).get('plugin', {}).get('enabled', True):
            return
    store = store if store is not None else AuditStore()
    data = payload(tool, arguments, result, duration_ms, source, error)
    store.append('工具调用', session, evidence_message_ids=list(dict.fromkeys(str(x) for x in evidence_ids if x)),
                 event_id=event_id, **data)


def render_tool(data: dict) -> list[str]:
    from .readable import plain
    lines = [f"功能：{plain(data.get('tool_title', ''), 100)}｜{plain(data.get('status', ''), 150)}",
             f"调用来源：{plain(data.get('source', ''), 100)}",
             '调用理由：' + plain(data.get('purpose', ''), 300)]
    args = data.get('arguments') or {}
    labels = {'city': '城市', 'days': '预报天数（0为当前）', 'query': '查询内容', 'person_name': '人物', 'mode': '查询模式'}
    selected = [f"{title}={args[key]}" for key, title in labels.items() if key in args]
    lines.append('查询参数：' + ('；'.join(selected) if selected else '详细参数保留审计数据库'))
    if isinstance(data.get('duration_ms'), (int, float)):
        lines.append(f"耗时：{data['duration_ms'] / 1000:.2f}秒")
    result = data.get('result') or {}
    text = result.get('content') if isinstance(result, dict) else ''
    if text:
        lines.append('查询/执行结果：' + plain(text, 1800))
    if data.get('error'):
        lines.append('失败原因：' + plain(data['error'], 500))
    lines.append('说明：结果返回不代表最终回答采用；检索资料不等于新增记忆。')
    return lines
