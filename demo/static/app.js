'use strict';
const $ = s => document.querySelector(s);
const promptBox = $('#prompt'), messages = $('#messages'), scrollArea = $('#scroll-area');
let ready = false, busy = false, externalBusy = false, attachments = [], activeJob = null, controller = null;
let compressing = false, restoring = false;
let ownerToken=localStorage.getItem('omni-owner-token'), historyEntries=[];
let presets = [], urls = new Set(), session = null, creatingSession = null;
const errors = {
  media_count: '每条消息最多 8 张图片和 1 段音频，请移除多余附件。',
  busy: '设备正在处理另一条消息或会话已满，请稍后再试。',
  unknown_session: '会话已过期，请点击新对话重新开始。', recent_context_too_large: '本次输入和最近两轮超过上下文容量，请缩短输入或开始新对话。',
  summary_context_too_large: '待整理的历史过长，请开始新对话。', summary_failed: '上下文整理失败，原对话仍然保留，请重试。', invalid_prompt: '请输入问题，内容不超过 8000 字符。',
  upload_size: '文件为空或超过 10 MB，请重新选择。', upload_capacity: '临时上传空间已满，请稍后再试。',
  unsupported_media: '请上传 JPG、PNG 图片，或 WAV 音频。', invalid_image: '图片文件无法读取，请更换一张图片。',
  image_dimensions: '图片尺寸过大，请先缩小到 4000 万像素以内。', invalid_wav: 'WAV 文件不完整或格式不受支持。',
  wav_format: '请使用 16 kHz、单声道 WAV，编码为 PCM16 或 Float32。', wav_duration: 'WAV 时长应为 0.025 至 20 秒，请先裁剪后上传。',
  upload_expired: '上传已过期，请重新选择文件。', invalid_model_input: '输入超出上下文容量，或包含不支持的格式。请缩短问题后重试。',
  inference_failed: '推理失败，请重试。若仍失败，请检查设备日志。', invalid_request: '请求格式有误，请刷新页面后重试。',
  restore_failed:'对话恢复失败，原对话仍然保留，请重试。',
  session_not_active:'请先从历史列表恢复此对话。', history_capacity:'历史对话数量已达到上限。',
  network: '连接中断，请检查设备连接后重试。', origin_rejected: '请求来源不匹配，请直接打开设备地址。'
};
function showContext(data) {
  if (!data || !data.capacity) return;
  const used=data.used_tokens || 0, cap=data.capacity;
  setUIText($('#context-label'),'上下文 '+used.toLocaleString()+' / '+cap.toLocaleString()+' · '+Math.round(used/cap*100)+'%');
  const percent=Math.min(100,Math.max(0,used/cap*100));
  $('#context-progress').setAttribute('stroke-dasharray',percent+' 100');
  $('#context-meter').dataset.level=percent>=85?'high':'normal';
  setUIAttribute($('#context-trigger'),'aria-label','上下文用量 '+Math.round(percent)+'%，'+used+' / '+cap+' tokens');
  setUIAttribute($('#context-trigger'),'title','上下文已使用 '+Math.round(percent)+'% · '+used.toLocaleString()+' / '+cap.toLocaleString()+' tokens');
  setUIText($('#context-details'),'有效 KV '+(data.effective_kv_tokens || 0)+' tokens（媒体 '+(data.media_tokens || 0)+'）；待写入 EOS '+(data.pending_eos_tokens || 0)+'；回答预留 '+(data.reserved_output_tokens || 1024)+' tokens。包含模板、prefix3 和媒体，不含 AR padding。已整理 '+(data.compressions || 0)+' 次。');
  if (data.new_prefill_tokens != null) setUIText($('#context-details'), (originalText.get($('#context-details').firstChild) || '')+' 本轮新增 '+data.new_prefill_tokens+'（媒体 '+data.media_tokens+'），输入后 '+data.next_input_tokens+'。');
  if (data.phase==='compressing') setCompression(true);
  else if (data.phase==='compressed') {
    setCompression(false);
    toast('上下文已整理：'+data.before_tokens+' → '+used+' tokens。保留最近两轮对话。');
  } else if (data.recovery_required) {
    setCompression(false); toast('会话恢复失败，请开始新对话。');
  }

}
function renderActivity() {
  const active=restoring || compressing, status=$('#context-status');
  status.hidden=!active;
  setUIText(status,restoring?'正在恢复对话，请稍候… 完成前暂时不能发送消息。':compressing?'正在整理上下文，请稍候… 完成后将继续回答，期间暂时不能发送消息。':'');
  $('.composer-area').classList.toggle('is-compressing',active);
  $('#composer').setAttribute('aria-busy',String(busy || active));
  if (active) $('#attach-menu').hidden=true;
  controls();
}
function setCompression(value) { compressing=Boolean(value); renderActivity(); }
function setRestoring(value) { restoring=Boolean(value); renderActivity(); }
async function ensureOwner() {
  if(!ownerToken) { ownerToken=(await jsonResponse(await fetch('/api/owner',{method:'POST'}))).owner_token; localStorage.setItem('omni-owner-token',ownerToken); }
}
async function refreshHistory() {
  if(!ownerToken)return;
  historyEntries=await jsonResponse(await fetch('/api/history',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({owner_token:ownerToken})}));
  const list=$('#history-list'); list.replaceChildren();
  for(const item of historyEntries) {
    const button=document.createElement('button');button.type='button';button.className='history-item'+(item.id===session?.session_id?' is-current':'');
    const title=document.createElement('span');title.className=item.title?'history-title':'history-empty-title';item.title ? title.textContent=item.title : setUIText(title,'新对话');button.append(title);
    button.addEventListener('click',()=>restoreConversation(item));list.append(button);
  }
  controls();
}
function clearView() {
  document.querySelectorAll('audio').forEach(audio=>audio.pause());discardAttachments();messages.replaceChildren();
  urls.forEach(url=>URL.revokeObjectURL(url));urls.clear();promptBox.value='';renderAttachment();resize();
}
async function restoreConversation(item) {
  if(microphone.active() || busy || restoring || compressing || externalBusy)return;
  microphone.close();
  busy=true;setRestoring(true);toast('');
  try {
    const data=await jsonResponse(await fetch('/api/sessions/'+item.id+'/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:item.token})}));
    clearView();session=data;localStorage.setItem('omni-active-session',session.session_id);
    for(const message of data.messages) {
      const media=[];
      const specs=message.media || (message.kind!=='text' ? [{kind:message.kind,preset:message.preset,media_id:message.media_id}] : []);
      for(const spec of specs){
        if(spec.preset)media.push({kind:spec.kind,url:'/api/presets/'+spec.preset+'/asset'});
        else if(spec.media_id){
          const response=await fetch('/api/sessions/'+item.id+'/media/'+spec.media_id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:item.token})});
          if(!response.ok)throw new Error('unknown_media');
          const url=URL.createObjectURL(await response.blob());urls.add(url);media.push({kind:spec.kind,url});
        }
      }
      addUser(message.user,media);const view=addAssistant();view.text=message.assistant;view.bubble.textContent=view.text;finishView(view,{finish_reason:'stop',statistics:message.statistics},null);
    }
    $('#welcome').hidden=Boolean(data.messages.length);showContext(data.context);await refreshHistory();down();
  } catch(e){toast(errors[e.message] || errors.network);}
  finally{busy=false;setRestoring(false);controls();pollHealth();}
}
async function newConversation() {
  if(microphone.active() || busy || restoring || compressing || externalBusy)return;
  microphone.close();
  busy=true;controls();
  try {
    await ensureOwner();session=await jsonResponse(await fetch('/api/sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({owner_token:ownerToken})}));
    clearView();localStorage.setItem('omni-active-session',session.session_id);$('#welcome').hidden=false;showContext(session.context);toast('');await refreshHistory();
  } catch(e){toast(errors[e.message] || errors.network);}
  finally{busy=false;controls();}
}
async function bootHistory() {
  busy=true;setRestoring(true);
  try {
    await ensureOwner();await refreshHistory();
    const id=localStorage.getItem('omni-active-session');const selected=historyEntries.find(x=>x.id===id) || historyEntries[0];
    busy=false;restoring=false;
    if(selected)await restoreConversation(selected);else await newConversation();
  } finally {busy=false;setRestoring(false);}
}
async function ensureSession() {
  if (session) return session;
  if (!ownerToken) await ensureOwner();
  if (!creatingSession) creatingSession=fetch('/api/sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({owner_token:ownerToken})}).then(jsonResponse);
  try {
    session = await creatingSession;
    localStorage.setItem('omni-active-session', session.session_id);
    showContext(session.context);
    return session;
  }
  finally { creatingSession=null; }
}
function icon(id) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  const use = document.createElementNS(svg.namespaceURI, 'use'); use.setAttribute('href', '#i-' + id); svg.append(use); return svg;
}
function toast(text) { setUIText($('#toast'),text); $('#toast').hidden = !text; }
function controls() {
  const recording = microphone.active();
  $('#microphone-button').disabled = !recording && (busy || restoring || compressing || externalBusy || !ready);
  $('#send').hidden = busy && !restoring; $('#stop').hidden = !busy || restoring;
  $('#send').disabled = recording || busy || restoring || compressing || !ready || externalBusy || !promptBox.value.trim();
  $('#new-chat').disabled = recording || busy || restoring || compressing || externalBusy; $('#attach-button').disabled = recording || busy || restoring || compressing || externalBusy || !ready;
  $('#choose-image').disabled=recording || busy || restoring || compressing || externalBusy; $('#choose-audio').disabled=recording || busy || restoring || compressing || externalBusy;
  promptBox.disabled = busy || restoring || compressing || externalBusy;
  document.querySelectorAll('[data-preset]').forEach(el => el.disabled = recording || busy || restoring || compressing || !ready || externalBusy || !presets.length);
  document.querySelectorAll('.history-item').forEach(el=>el.disabled=recording || busy || restoring || compressing || externalBusy);
  setUIText($('#composer-hint'),restoring ? '正在恢复对话，暂时无法对话' : compressing ? '正在整理上下文，暂时无法对话' : busy ? (activeJob ? '正在生成，可随时停止' : '正在准备输入…') : '文字 · 图片 · WAV 音频');
}
function resize() { promptBox.style.height = 'auto'; promptBox.style.height = Math.min(promptBox.scrollHeight, 145) + 'px'; }
function nearBottom() { return scrollArea.scrollHeight - scrollArea.scrollTop - scrollArea.clientHeight < 130; }
function down() { scrollArea.scrollTop = scrollArea.scrollHeight; }
async function jsonResponse(response) {
  const data = await response.json(); if (!response.ok) throw new Error(data.code || 'network'); return data;
}
function mediaElement(parent, item, composer = false) {
  if (item.kind === 'image') {
    const image = document.createElement('img'); image.src = item.url; setUIAttribute(image,'alt','上传的图片');
    image.className = composer ? '' : 'attachment-media'; parent.append(image);
  } else {
    const audio = document.createElement('audio'); audio.controls = true; audio.preload = 'metadata'; audio.src = item.url;
    setUIAttribute(audio,'aria-label','音频预览'); parent.append(audio);
  }
}
function renderAttachment() {
  const area=$('#attachment');area.replaceChildren();area.hidden=!attachments.length;
  attachments.forEach((item,index)=>{
    const card=document.createElement('div');card.className='attachment-card';
    mediaElement(card,item,true);
    const text=document.createElement('div');text.className='file-description';text.textContent=item.name;
    const small=document.createElement('small');setUIText(small,item.kind==='image'?'图片已就绪':'WAV 音频');text.append(small);card.append(text);
    const close=document.createElement('button');close.className='icon-button';close.type='button';setUIAttribute(close,'aria-label','移除附件');close.append(icon('close'));
    close.addEventListener('click',()=>{if(!busy&&!restoring&&!compressing&&!externalBusy){if(item.file&&!item.used){URL.revokeObjectURL(item.url);urls.delete(item.url);}attachments.splice(index,1);renderAttachment();}});
    card.append(close);area.append(card);
  });
}
function discardAttachments() {
  for(const item of attachments)if(item.file&&!item.used){URL.revokeObjectURL(item.url);urls.delete(item.url);}
  attachments=[];
}
function chooseFiles(files,expected=null) {
  if(microphone.active()||busy||restoring||compressing||externalBusy)return;
  return addFiles(files, expected);
}
function addFiles(files, expected) {
  if (!files.length) return;
  toast('');const next=[];
  for(const file of files){
    const kind=expected || (/\.wav$/i.test(file.name)?'audio':'image');
    if(file.size>10*1024*1024||!file.size)return toast(errors.upload_size);
    if(kind==='image'&&!/\.(png|jpe?g)$/i.test(file.name))return toast(errors.unsupported_media);
    if(kind==='audio'&&!/\.wav$/i.test(file.name))return toast(errors.unsupported_media);
    next.push({file,kind,name:file.name});
  }
  if(attachments.filter(x=>x.kind==='image').length+next.filter(x=>x.kind==='image').length>8 || attachments.filter(x=>x.kind==='audio').length+next.filter(x=>x.kind==='audio').length>1)return toast(errors.media_count);
  for(const item of next){item.url=URL.createObjectURL(item.file);urls.add(item.url);attachments.push(item);}
  attachments.sort((a,b)=>(a.kind!=='image')-(b.kind!=='image'));
  if(!promptBox.value.trim())promptBox.value=attachments.some(x=>x.kind==='image')?'请按顺序描述这些图片。':'请转写音频中的语音，只输出转写结果。';
  renderAttachment();resize();controls();promptBox.focus();
  return true;
}
function addUser(text,items=[]) {
  const row=document.createElement('article');row.className='message user';setUIAttribute(row,'aria-label','你的消息');
  const bubble=document.createElement('div');bubble.className='bubble';
  if(items.length){const gallery=document.createElement('div');gallery.className='message-media';for(const item of items){item.used=true;mediaElement(gallery,item);}bubble.append(gallery);}
  const content=document.createElement('div');content.textContent=text;bubble.append(content);row.append(bubble);messages.append(row);
}
function addAssistant() {
  const row = document.createElement('article'); row.className = 'message assistant'; setUIAttribute(row,'aria-label','模型回答');
  const avatar = document.createElement('div'); avatar.className = 'assistant-avatar';
  const image = document.createElement('img'); image.src = '/static/pandora-mark.svg'; image.alt = ''; avatar.append(image);
  const content = document.createElement('div'); content.className = 'assistant-content';
  const bubble = document.createElement('div'); bubble.className = 'bubble'; bubble.setAttribute('aria-busy', 'true');
  const waiting = document.createElement('div'); waiting.className = 'thinking'; setUIAttribute(waiting,'aria-label','正在思考');
  for (let i = 0; i < 3; i++) waiting.append(document.createElement('i')); bubble.append(waiting);
  const state = document.createElement('div'); state.className = 'message-state'; setUIText(state, '正在理解输入…');
  content.append(bubble, state); row.append(avatar, content); messages.append(row); return {row, bubble, state, content, text: ''};
}
async function copyText(text, button) {
  try {
    if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
    else { const area = document.createElement('textarea'); area.value = text; document.body.append(area); area.select(); document.execCommand('copy'); area.remove(); }
    setUIText(button,'已复制'); setTimeout(() => { button.replaceChildren(icon('copy'), uiTextNode('复制')); }, 1200);
  } catch (_) { toast('复制失败，请直接选中文本复制。'); }
}
function finishView(view, data, firstMs) {
  view.bubble.setAttribute('aria-busy', 'false');
  if (!view.text) setUIText(view.bubble, data.finish_reason === 'cancelled' ? '本次生成已停止。' : '模型未返回文字。');
  const stateParts=[{stop: '回答完成', cancelled: '已停止', length: '已达到输出长度上限'}[data.finish_reason] || '已结束'];
  if (data.history_committed===false) stateParts.push('本次达到长度上限，未加入记忆');
  setUIMessageParts(view.state,stateParts);
  const stats = data.statistics || {}, actions = document.createElement('div'); actions.className = 'message-actions';
  if (view.text) { const copy = document.createElement('button'); copy.className = 'copy-button'; copy.append(icon('copy'), uiTextNode('复制')); copy.addEventListener('click', () => copyText(view.text, copy)); actions.append(copy); }
  if (firstMs != null) { const latency = document.createElement('span'); setUIText(latency, '首字响应 ' + (firstMs / 1000).toFixed(2) + ' s'); actions.append(latency); }
  if (Number.isFinite(stats.decode_tokens_per_second)) { const speed = document.createElement('span'); speed.textContent = stats.decode_tokens_per_second.toFixed(1) + ' token/s'; actions.append(speed); }
  view.content.append(actions);
  const items = [ ['LM 首 token', stats.lm_ttft_ms, 'ms'], ['输入 token（含媒体）', stats.prompt_tokens, ''], ['媒体 token', stats.media_tokens, ''], ['媒体推理', stats.tower_invoke_ms, 'ms'], ['本轮新增 prefill',stats.new_prefill_tokens,''], ['有效 KV token',stats.cached_tokens_after,''] ];
  if (items.some(x => x[1] != null)) {
    const details = document.createElement('details'); details.className = 'metrics'; const summary = document.createElement('summary'); setUIText(summary, '查看运行统计'); details.append(summary);
    const grid = document.createElement('div'); grid.className = 'metric-grid';
    items.filter(x => x[1] != null).forEach(([label, value, unit]) => { const span = document.createElement('span'); setUIText(span, label); const b = document.createElement('b'); b.textContent = (unit ? value.toFixed(1) : value) + (unit ? ' ' + unit : ''); span.append(b); grid.append(span); }); details.append(grid); view.content.append(details);
  }
}
async function send(presetID = null) {
  if (microphone.active() || busy || restoring || compressing || !ready || externalBusy || !promptBox.value.trim()) return;
  microphone.close();
  const text = promptBox.value.trim(), items = [...attachments];
  let view = null, receivedTerminal = false, firstMs = null, uploaded = [];
  busy = true; activeJob = null; $('#stop').disabled = true; controls(); toast('');
  document.querySelectorAll('audio').forEach(audio => audio.pause());
  controller = new AbortController(); const started = performance.now();
  try {
    await ensureSession();
    const body = {prompt: text,session_id:session.session_id,session_token:session.session_token};
    if(presetID==='text')body.preset='text';
    else {
      body.attachments=[];
      for(const item of items){
        if(item.preset)body.attachments.push({preset:item.preset});
        else if(item.file){
          const entry=await jsonResponse(await fetch('/api/uploads',{method:'POST',body:item.file,signal:controller.signal}));uploaded.push(entry);
          if(entry.kind!==item.kind)throw new Error('unsupported_media');
          body.attachments.push({upload_id:entry.id,upload_token:entry.token});
        }
      }
    }
    addUser(text, items);view=addAssistant();$('#welcome').hidden=true;
    promptBox.value='';attachments=[];renderAttachment();resize();down();
    const response = await fetch('/api/generate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body), signal: controller.signal});
    if (!response.ok) await jsonResponse(response);
    uploaded = [];
    const reader = response.body.getReader(), decoder = new TextDecoder('utf-8', {fatal: true}); let buffer = '';
    while (true) {
      const {value, done} = await reader.read(); if (done) break;
      buffer += decoder.decode(value, {stream: true});
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
        const lines = frame.split('\n'), name = lines.find(x => x.startsWith('event: '))?.slice(7), raw = lines.find(x => x.startsWith('data: '))?.slice(6);
        if (!name || !raw) continue; const data = JSON.parse(raw), follow = nearBottom();
        if (name === 'start') { activeJob = data; $('#stop').disabled = false; controls(); }
        else if (name === 'context') { showContext(data); if (data.phase==='compressing') setUIText(view.state,'正在整理上下文…'); }
        else if (name === 'delta') { if (firstMs == null) firstMs = performance.now() - started; view.text += data.delta; view.bubble.textContent = view.text; setUIText(view.state, '正在生成…'); }
        else if (name === 'done') {
          if (typeof data.text === 'string' && data.text !== view.text) throw new Error('network');
          receivedTerminal = true; finishView(view, data, firstMs); showContext(data.context); await refreshHistory();
        } else if (name === 'error') { showContext(data.context); throw new Error(data.code); }
        if (follow) down();
      }
    }
    if (!receivedTerminal) throw new Error('network');
  } catch (error) {
    const message = errors[error.message] || errors.network;
    if (view) { view.bubble.setAttribute('aria-busy', 'false'); if (!view.text) setUIText(view.bubble,message); view.state.classList.add('error'); setUIText(view.state,message); }
    else toast(message);
    if (!receivedTerminal) { promptBox.value = text; attachments = items; renderAttachment(); resize(); }
  } finally {
    // An upload rejected before consumption is explicitly released when possible.
    for(const entry of uploaded)fetch('/api/uploads/'+entry.id,{method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:entry.token})}).catch(()=>{});
    busy = false; activeJob = null; controller = null; setCompression(false); controls(); pollHealth();
  }
}
async function stop() {
  if (!activeJob) return;
  $('#stop').disabled = true; setUIText($('#composer-hint'), '正在停止，请稍候…');
  try { await jsonResponse(await fetch('/api/jobs/' + activeJob.job_id + '/cancel', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({token: activeJob.token})})); }
  catch (_) { toast('正在等待设备结束当前调用，请勿重复提交。'); $('#stop').disabled = false; }
}
async function pollHealth() {
  let h;
  try {
    h = await jsonResponse(await fetch('/api/health', {cache: 'no-store'}));
  } catch (_) {
    ready = false;
    $('#connection').className = 'connection';
    $('#connection').replaceChildren(document.createElement('i'), uiTextNode('设备未连接'));
    controls();
    return;
  }

  ready = h.ready;
  externalBusy = h.busy && !busy;
  const soc = document.getElementById("device-soc"); if (soc && h.target) soc.textContent = "Qualcomm " + h.target.split("_")[0].toUpperCase();
  if (!busy) { setCompression(h.phase==='compressing'); setRestoring(h.phase==='restoring'); }
  $('#connection').className = 'connection ' + (h.busy ? 'busy' : 'ready');
  $('#connection').replaceChildren(document.createElement('i'), uiTextNode(h.phase==='restoring' ? '正在恢复对话' : h.busy ? '设备推理中' : '设备已连接'));

  const checkedSession = session;
  if (checkedSession && !busy && !h.busy) {
    try {
      const c = await jsonResponse(await fetch('/api/sessions/'+checkedSession.session_id+'/context',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:checkedSession.session_token})}));
      if (session === checkedSession && !busy) showContext(c);
    } catch (error) {
      if (error.message === 'unknown_session' && session === checkedSession && !busy) {
        session = null;
        // Storage is shared with other tabs.
        if (localStorage.getItem('omni-active-session') === checkedSession.session_id) {
          localStorage.removeItem('omni-active-session');
        }
        toast('会话已过期，发送消息即可开始新对话。');
      }
    }
  }
  if (!session) showContext({used_tokens:0,capacity:h.context_capacity,usable_tokens:h.context_usable_tokens,reserved_output_tokens:h.response_token_limit});
  controls();
}
document.addEventListener('keydown',event=>{if(event.key==='Escape') $('#context-meter').open=false;});
$('#composer').addEventListener('submit', event => { event.preventDefault(); send(); });
promptBox.addEventListener('input', () => { resize(); controls(); });
promptBox.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) { event.preventDefault(); send(); } });
$('#stop').addEventListener('click', stop);
$('#new-chat').addEventListener('click',newConversation);
const microphoneRecordings = new WeakSet();
function canRecord() {
  if (busy || restoring || compressing || externalBusy) {
    toast(errors.busy);
    return false;
  }
  if (attachments.some(item => item.kind === 'audio' && !microphoneRecordings.has(item.file))) {
    toast(errors.media_count);
    return false;
  }
  return true;
}

function attachRecording(file) {
  // Keep the completed local recording even if another tab is using the model.
  const previous = attachments.findIndex(item => microphoneRecordings.has(item.file));
  if (previous !== -1) {
    URL.revokeObjectURL(attachments[previous].url);
    urls.delete(attachments[previous].url);
    attachments.splice(previous, 1);
  }
  if (!addFiles([file], 'audio')) return false;
  microphoneRecordings.add(file);
  return true;
}

const microphone = mountMicrophone({attach: attachRecording, canRecord, onChange: controls});
$('#attach-button').addEventListener('click', () => { $('#attach-menu').hidden = !$('#attach-menu').hidden; $('#attach-button').setAttribute('aria-expanded', String(!$('#attach-menu').hidden)); });
document.addEventListener('click', event => { if (!event.target.closest('#context-meter')) $('#context-meter').open=false; if (!event.target.closest('.attach-wrap')) { $('#attach-menu').hidden = true; $('#attach-button').setAttribute('aria-expanded', 'false'); } });
$('#choose-image').addEventListener('click', () => { $('#attach-menu').hidden = true; $('#image-file').click(); });
$('#choose-audio').addEventListener('click', () => { $('#attach-menu').hidden = true; $('#audio-file').click(); });
$('#image-file').addEventListener('change', event => { chooseFiles([...event.target.files], 'image'); event.target.value = ''; });
$('#audio-file').addEventListener('change', event => { chooseFiles([...event.target.files], 'audio'); event.target.value = ''; });
document.querySelectorAll('[data-preset]').forEach(button => button.addEventListener('click', () => {
  if (microphone.active() || busy || restoring || compressing || externalBusy) return; const spec = presets.find(p => p.id === button.dataset.preset); if (!spec) return;
  microphone.close();
  discardAttachments(); promptBox.value = spec.prompt; if (spec.asset) attachments = [{kind: spec.kind, preset: spec.id, url: spec.asset, name: spec.filename}]; renderAttachment(); resize(); send(spec.id);
}));
['dragenter', 'dragover'].forEach(name => document.addEventListener(name, event => { event.preventDefault(); if (!busy) document.body.classList.add('drop-target'); }));
document.addEventListener('dragleave', event => { if (!event.relatedTarget) document.body.classList.remove('drop-target'); });
document.addEventListener('drop', event => { event.preventDefault(); document.body.classList.remove('drop-target'); chooseFiles([...event.dataTransfer.files]); });
window.addEventListener('pagehide', () => { if (activeJob) fetch('/api/jobs/' + activeJob.job_id + '/cancel', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({token: activeJob.token}), keepalive: true}).catch(() => {}); if (controller) controller.abort();  });
document.addEventListener('play', event => { if (event.target.tagName === 'AUDIO') document.querySelectorAll('audio').forEach(audio => { if (audio !== event.target) audio.pause(); }); }, true);
fetch('/api/presets').then(jsonResponse).then(data => { presets = data; controls(); }).catch(() => toast(errors.network));
pollHealth(); setInterval(pollHealth, 4000); controls();bootHistory().catch(()=>toast(errors.network));
