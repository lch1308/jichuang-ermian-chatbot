// 纯逻辑层便于离线测试；稳定心情与话题情绪的来源只有 Heart 插件。
export class HeartController {
  constructor(report, clock=()=>performance.now()) {
    this.report=report; this.clock=clock; this.current=null; this.lastModel=null;
    this.lastCommand=null; this.speaking=false; this.textSpeaking=false; this.generation=null; this.lastMotionAt=0;
  }
  owns() { return Boolean((this.current?.ready && (this.current.enabled || this.current.manual)) ||
    (this.generation && this.generationState(this.current)?.generation)); }
  async beginGeneration(turn_id,adapter) {
    this.textSpeaking=false; // 新输入结束旧的无声展示，不等于停止真实音频。
    if(this.generation?.turn_id!==turn_id) this.generation={turn_id,started:this.clock()};
    if(this.current) await this.update(this.current,adapter);
  }
  async endGeneration(turn_id,adapter) {
    if(this.generation?.turn_id!==turn_id) return; // 旧回复迟到不能结束新一轮。
    this.generation=null;
    if(this.current?.ready) await this.update(this.current,adapter);
    else if(this.current?.neutral_expression!==undefined && this.current.neutral_expression!==null)
      await this.apply({...this.current,ready:true,valid_expression:true,restore_only:true,
        expression:this.current.neutral_expression,motion:null,command_id:`generation-rest:${turn_id}`},adapter);
  }
  generationState(state) {
    if(!state || !this.generation || state.manual || state.performance || state.enabled===false) return state;
    const emotion=state.ready && state.valid_expression && state.active && state.expression!==state.neutral_expression;
    const expression=emotion?state.expression:state.thinking_expression;
    if(expression===null || expression===undefined) return state;
    return {...state,ready:true,valid_expression:true,
      command_id:`generation:${this.generation.turn_id}:${expression}`,
      expression,motion:emotion?state.motion:state.thinking_motion,
      generation:{...this.generation,source:emotion?'confirmed_emotion':'thinking'}};
  }
  canTalk(state = this.current) {
    return Boolean(state?.ready && state.enabled && !state.manual && !state.performance && !state.active &&
      state.expression === state.neutral_expression && state.talk_expression != null &&
      state.talk_expression !== state.neutral_expression);
  }
  async speech(started, adapter) {
    this.speaking = started;
    if (this.current) await this.update(this.current, adapter);
  }
  async textSpeech(started, adapter) {
    this.textSpeaking = started; // 与实际音频播放分开，静音也能有说话动作。
    if (this.current) return this.update(this.current, adapter);
    return 'pending';
  }
  async update(state, adapter) {
    this.current = state;
    return this.apply(this.generationState(state),adapter);
  }
  async apply(state,adapter) {
    if (!state.ready) return 'pending';
    if (!state.valid_expression) { await this.report(state, 'failed'); return 'failed'; }
    const model = adapter?.getModel?.();
    const talking = !state.generation && (this.speaking || this.textSpeaking) && this.canTalk(state);
    const target = talking ? state.talk_expression : state.expression;
    const command = state.command_id + (talking ? ':speech' : ':rest');
    const motion = talking ? state.talk_motion : state.motion;
    const expression = typeof target === 'number' ? adapter?.getExpressionName?.(target) : target;
    if(state.generation) state={...state,generation:{...state.generation,expression:expression??null}};
    // Open-LLM-VTuber models can expose either names or numeric indexes in
    // emotionMap. Never assume a particular model directory or expression set.
    if (!model || typeof expression !== 'string' || !expression ||
        (model._expressions?.getValue && model._expressions.getValue(expression) == null)) {
      await this.report(state, 'unavailable');
      return 'unavailable';
    }
    if (this.lastCommand === command && this.lastModel === model) {
      // 长回复等待期间偶尔续一个模型配置的动作，不随每秒轮询强制重播。
      if(state.generation && motion && this.clock()-this.lastMotionAt>=8000 && model.startMotion) {
        model.startMotion(motion.group,motion.index,3);
        this.lastMotionAt=this.clock();
      }
      // 动作已完成但回执可能丢失：只重发回执，不重复播放动作。
      await this.report(state, 'applied');
      return 'applied';
    }
    try {
      // 模型可自行配置配套动作。仅在新指令或换模型时播放，不随轮询反复重播。
      if (motion) {
        const {group, index} = motion;
        if (typeof group !== 'string' || !Number.isInteger(index) || index < 0 ||
            !model.startMotion || (adapter.getMotionCount && adapter.getMotionCount(group) <= index)) {
          await this.report(state, 'unavailable');
          return 'unavailable';
        }
        model.startMotion(group, index, 3); // Cubism 的强制优先级，允许手动表情立即响应。
        this.lastMotionAt=this.clock();
      }
      model.setExpression(expression);
      this.lastModel = model;
      this.lastCommand = command;
    } catch (error) {
      await this.report(state, 'failed');
      throw error;
    }
    // 网络失败不等于表情执行失败，不能把两种情况混为一谈。
    await this.report(state, 'applied');
    return 'applied';
  }
}
