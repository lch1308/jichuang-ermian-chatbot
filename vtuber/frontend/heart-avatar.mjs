import {HeartController} from './heart-controller.mjs';

const client = crypto.randomUUID();
const acknowledged = new Set();
async function report(state, status) {
  if(state.restore_only) return; // 首访未关联会话，取消后恢复中性，不假造服务端指令。
  const key = state.command_id + ':' + status;
  if(state.generation) {
    if(acknowledged.has(key)) return;
    await new Promise(resolve=>requestAnimationFrame(resolve));
    const result=await fetch('/heart/dialogue-events',{
      method:'POST',headers:{'Content-Type':'application/json','X-Heart-Client':state.csrf},
      body:JSON.stringify({turn_id:state.generation.turn_id,phase:'generation_avatar',
        expression:state.generation.expression,avatar_status:status,source:state.generation.source,
        browser_elapsed_ms:performance.now()-state.generation.started}),signal:AbortSignal.timeout(3000)});
    if(!result.ok) throw Error('生成动作回执未保存，下一次轮询重试');
    acknowledged.add(key);
    if(acknowledged.size>256) acknowledged.delete(acknowledged.values().next().value);
    return;
  }
  if (acknowledged.has(key)) return;
  const result = await fetch('/heart/avatar-events', {
    method: 'POST', headers: {'Content-Type':'application/json', 'X-Heart-Client':state.csrf},
    body: JSON.stringify({command_id:state.command_id, client_id:client, status}),
    signal: AbortSignal.timeout(3000),
  });
  if (!result.ok) throw Error('动作日志回执未保存');
  acknowledged.add(key);
  if (acknowledged.size > 256) acknowledged.delete(acknowledged.values().next().value);
}
const controller = new HeartController(report);
window.heartController = controller;
window.yubaoHeartController = controller; // compatibility with the older timing shim
window.addEventListener('heart-generation',event=>{
  const {action,turn_id}=event.detail;
  const adapter=window.getLAppAdapter?.();
  const operation=action==='begin'?controller.beginGeneration(turn_id,adapter):controller.endGeneration(turn_id,adapter);
  void operation.catch(error=>console.warn('生成表情或回执未完成',error.message));
});
let pendingTextPose=null;
let textPoseRevision=0;
async function recordTextPose(detail,result) {
    const {started,trace}=detail;
    const state=controller.current;
    if(!trace?.turn_id || !state?.ready || !['applied','failed','unavailable'].includes(result)) return;
    const target=started && controller.canTalk(state)?state.talk_expression:state.expression;
    const expression=typeof target==='number'?window.getLAppAdapter?.()?.getExpressionName?.(target):target;
    const response=await fetch('/heart/dialogue-events',{
      method:'POST',headers:{'Content-Type':'application/json','X-Heart-Client':state.csrf},
      body:JSON.stringify({turn_id:trace.turn_id,segment:trace.segment??null,
        phase:started?'text_pose_started':'text_pose_ended',expression,
        avatar_status:result}),signal:AbortSignal.timeout(3000)});
    if(!response.ok) throw Error('无声展示动作回执未保存');
}
// 文字展示不是声音播放：不发 heart-speech，不假造语音回执。
window.addEventListener('heart-text-speech',async event=>{
  const revision=++textPoseRevision;
  pendingTextPose=null;
  try {
    const result=await controller.textSpeech(event.detail.started,window.getLAppAdapter?.());
    if(revision!==textPoseRevision) return; // 迟到的旧回执不能关联到新的展示。
    if(event.detail.started && ['pending','unavailable'].includes(result)) pendingTextPose=event.detail;
    await recordTextPose(event.detail,result);
  } catch(error) { console.warn('无声展示动作或回执未完成',error.message); }
});
// 播放器在真正开始/结束音频时发事件；不根据“收到音频”假装已经在说话。
window.addEventListener('heart-speech', async event => {
  const adapter = window.getLAppAdapter?.();
  const state = controller.current;
  const started = event.detail === 'playing';
  if (started === controller.speaking) return; // ended和pause可能都到达，只记录一次。
  try {
    await controller.speech(started, adapter);
    if (state?.ready) await fetch('/heart/speech-events', {
      method:'POST', headers:{'Content-Type':'application/json','X-Heart-Client':state.csrf},
      body:JSON.stringify({command_id:state.command_id, phase:started ? 'playing' : 'ended',
        client_id:client, event_id:crypto.randomUUID(),
        turn_id:window.heartActiveSpeechTrace?.turn_id, segment:window.heartActiveSpeechTrace?.segment,
        talking:started && controller.canTalk(state)}), signal:AbortSignal.timeout(3000),
    });
  } catch (error) { console.warn('语音动作记录未完成', error); }
});
const panel = document.createElement('section');
panel.id = 'heart-mood-panel';
panel.setAttribute('aria-label', '当前形象的心情与话题情绪');
panel.style.cssText = 'position:fixed;right:18px;top:16px;z-index:1000;width:260px;max-width:calc(100vw - 36px);padding:14px 18px;color:#fff;background:rgba(15,23,42,.9);border:1px solid #64748b;border-radius:14px;font:14px/1.6 system-ui;pointer-events:none;box-shadow:0 4px 20px #0004';
const heading = document.createElement('div'); heading.style.cssText='color:#cbd5e1;font-size:12px';
const score = document.createElement('div'); score.style.cssText='font-size:23px;font-weight:600';
const emotion = document.createElement('div');
const topic = document.createElement('div'); topic.style.cssText='font-size:12px;color:#cbd5e1;overflow-wrap:anywhere';
const manual = document.createElement('div'); manual.style.cssText='font-size:12px;color:#fde68a';
const status = document.createElement('div'); status.style.cssText='font-size:11px;color:#a5b4fc;margin-top:5px';
heading.textContent='Heart · 当前网页会话'; score.textContent='心情 -- / 100'; status.textContent='正在连接心情插件…';
panel.append(heading,score,emotion,topic,manual,status);
document.body.appendChild(panel);

async function poll() {
  try {
    const response = await fetch('/heart/state', {cache:'no-store', signal:AbortSignal.timeout(3000)});
    if (!response.ok) throw Error('心情接口未连接');
    const state = await response.json();
    if (state.ready) {
      heading.textContent='Heart · ' + (state.model_name || '当前形象') + ' · ' + state.session_name;
      score.textContent='心情 ' + (typeof state.value === 'number' ? state.value.toFixed(1).replace(/\.0$/,'') : '--') + ' / 100 · ' + state.band;
      emotion.textContent=state.active ? '当前情绪：' + state.label + ' · 强度 ' + Math.round(state.intensity*100) + '%' : '当前情绪：无额外的小情绪';
      topic.textContent=state.active ? '话题：' + state.topic : '临时情绪结束后，恢复心情对应的常态';
      manual.textContent=state.manual ? '手动表情：' + state.manual_expression + '（暂时展示，不改变心情）' : state.performance ? '应请求表演：' + state.performance_expression + '（与真实情绪分开）' : '';
      status.textContent=state.enabled ? state.notice + ' · ' + state.updated : '心情插件已关闭 · 保留上次记录';
    } else {
      status.textContent=state.notice;
    }
    const result=await controller.update(state, window.getLAppAdapter?.());
    if(pendingTextPose && controller.textSpeaking && result==='applied') {
      const detail=pendingTextPose; pendingTextPose=null;
      await recordTextPose(detail,result); // 首条回复早于首次心情轮询，也要补记真正显示的动作。
    }
  } catch (error) {
    status.textContent='同步或动作回执未成功 · 保留上次已确认显示，稍后重试';
  } finally {
    setTimeout(poll,1000);
  }
}
poll();
