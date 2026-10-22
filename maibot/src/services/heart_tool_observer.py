"""工具调用的只读接口：异常原样传播，日志失败不修改工具返回值。"""

from time import perf_counter
from typing import Any, Sequence
import asyncio
import logging

from heart_shared.tool_audit import record_tool


async def observe_result(invocation: Any, context: Any, result: Any,
                         evidence_ids: Sequence[str], duration_ms: float, error: str = '') -> None:
    try:
        # 日志总开关由共享记录接口统一检查，不加载/调用记忆算法。
        data = {'success': result.success, 'content': result.content, 'error': result.error_message}
        if isinstance(result.structured_content, dict):
            # 只传工具公开结果，绝不传invocation.reasoning / metadata中的完整请求。
            data.update({k: v for k, v in result.structured_content.items() if k not in data})
        await asyncio.to_thread(record_tool, context.session_id, invocation.tool_name, invocation.arguments, data,
                                evidence_ids=evidence_ids, duration_ms=duration_ms, error=error)
        # 每次真实执行生成独立审计编号，避免模型复用call_id导致日志被误去重。
    except Exception:
        logging.getLogger(__name__).exception('工具已执行，但中文日志写入失败；不会重新执行工具')


async def invoke_observed_tool(registry: Any, invocation: Any, context: Any,
                               evidence_ids: Sequence[str]) -> Any:
    started = perf_counter()
    try:
        result = await registry.invoke(invocation, context)
    except BaseException as exc:
        # 工具中断时，不能宣称有副作用的操作肯定未执行。
        from types import SimpleNamespace
        note = '取消，工具最终效果未知' if isinstance(exc, asyncio.CancelledError) else type(exc).__name__ + ': ' + str(exc)
        failed = SimpleNamespace(success=False, content='', error_message=note, structured_content=None)
        await observe_result(invocation, context, failed, evidence_ids, (perf_counter() - started) * 1000, note)
        raise
    await observe_result(invocation, context, result, evidence_ids, (perf_counter() - started) * 1000)
    return result
