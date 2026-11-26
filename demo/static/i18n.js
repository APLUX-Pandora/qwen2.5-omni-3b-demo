'use strict';
// Interface text only. Conversation content and user-provided filenames are excluded.
const uiTranslations={
 '麦克风录音':'Microphone recording','关闭麦克风面板':'Close microphone panel','麦克风音量':'Microphone level',
 '检查麦克风':'Check microphone','开始录音':'Start recording','停止录音':'Stop recording',
 '先检查麦克风，再开始录音。':'Check your microphone before recording.',
 '正在打开麦克风…':'Opening microphone…','请说一句话，检查麦克风是否收得到声音。':'Say a few words to check the microphone.',
 '没有检测到声音，请检查静音或输入音量后重试。':'No sound detected. Check mute and input volume, then try again.',
 '麦克风检查通过，可以开始录音。':'Microphone check passed. You can start recording.',
 '正在录音，最长 20 秒。':'Recording, up to 20 seconds.','正在准备录音…':'Preparing recording…',
 '录音已添加，可以试听、删除或重新录音。':'Recording attached. You can preview, remove or record again.',
 '录音太短，请重新录音。':'The recording is too short. Record again.',
 '录音没有声音，请检查输入音量后重试。':'The recording has no sound. Check the input volume and retry.',
 '录音转换失败，请重新录音。':'Could not prepare the recording. Record again.',
 '录音采集未完成，请重新录音。':'Audio capture did not finish. Record again.',
 '麦克风权限未授权，请在浏览器中允许后重试。':'Microphone permission denied. Allow access in your browser and try again.',
 '找不到麦克风，请连接设备后重试。':'Microphone not found. Connect one and try again.',
 '麦克风不可用，请检查设备后重试。':'Microphone unavailable. Check the device and try again.',
 '麦克风已断开，请重新检查。':'Microphone disconnected. Run the check again.',
 '麦克风设备已变化，请重新检查。':'Microphone device changed. Run the check again.',
 '请通过 HTTPS 打开页面以使用麦克风。':'Open the page over HTTPS to use the microphone.',
 '当前浏览器不支持麦克风录音。':'This browser does not support microphone recording.',
 '每条消息最多 8 张图片和 1 段音频，请移除多余附件。':'Each message supports up to 8 images and 1 audio clip. Remove extra attachments.',
 '输入问题，或添加图片 / WAV 音频…':'Message, or attach images / a WAV file…',
 '连续对话 · 自动整理历史并保留最近两轮 · 最多 8 张图片和 1 段音频':'Continuous chat · Automatic memory · Up to 8 images and 1 audio clip per message',

 '对话恢复失败，原对话仍然保留，请重试。':'Conversation restoration failed. The previous conversation is preserved. Please retry.',
 '界面语言':'Interface language','历史对话':'Chat history','当前体验':'Current experience','新对话':'New chat',
 'Omni 多模态对话':'Omni multimodal chat','运行于本地设备':'Running on this device',
 '你好，有什么可以帮你？':'Hello, how can I help?', '文字、图片与声音，在一个窗口里探索。':'Explore text, images and audio in one conversation.',
 '聊聊端侧 AI':'Explore on-device AI','用几句话，了解身边的 AI。':'Discover AI running on your device.',
 '体验文字':'Try text','看图说颜色':'Explore an image','给模型一张图，听听它的发现。':'Share an image and ask about it.',
 '体验图片':'Try an image','听一段短音频':'Listen to a short clip','上传一段声音，把语音变成文字。':'Upload audio and turn speech into text.',
 '体验音频':'Try audio','预设 WAV 试听':'Preview sample WAV','试听预设音频':'Play the sample audio',
 '输入问题':'Message','输入问题，或添加一张图片 / WAV 音频…':'Message, or attach an image / WAV file…',
 '添加图片或音频':'Attach an image or audio','上传图片':'Upload an image','JPG / PNG · 最大 10 MB':'JPG / PNG · Up to 10 MB',
 '上传 WAV 音频':'Upload WAV audio','16 kHz · 单声道 · 最长 20 秒':'16 kHz · Mono · Up to 20 seconds',
 '文字 · 图片 · WAV 音频':'Text · Images · WAV audio','发送消息':'Send message','停止生成':'Stop generation',
 '连续对话 · 自动整理历史并保留最近两轮 · 一次可附一个文件':'Continuous chat · Automatic memory · One attachment per message',
 'Enter 发送 · Shift + Enter 换行':'Enter to send · Shift + Enter for a new line',
 '设备正在处理另一条消息或会话已满，请稍后再试。':'The device is busy. Please try again shortly.',
 '会话已过期，请点击新对话重新开始。':'This conversation is unavailable. Start a new chat.',
 '会话已过期，发送消息即可开始新对话。':'This conversation has expired. Send a message to start a new chat.',
 '本次输入和最近两轮超过上下文容量，请缩短输入或开始新对话。':'This input and the two recent turns exceed the context limit. Shorten the input or start a new chat.',
 '待整理的历史过长，请开始新对话。':'The history is too long to summarize. Please start a new chat.',
 '上下文整理失败，原对话仍然保留，请重试。':'Context compaction failed. Your previous conversation is preserved. Please retry.',
 '请输入问题，内容不超过 8000 字符。':'Enter a message of up to 8,000 characters.',
 '文件为空或超过 10 MB，请重新选择。':'The file is empty or exceeds 10 MB. Choose another file.',
 '临时上传空间已满，请稍后再试。':'Temporary upload storage is full. Please try again later.',
 '请上传 JPG、PNG 图片，或 WAV 音频。':'Upload a JPG/PNG image or a WAV audio file.',
 '图片文件无法读取，请更换一张图片。':'The image could not be read. Choose another image.',
 '图片尺寸过大，请先缩小到 4000 万像素以内。':'Resize the image to at most 40 megapixels.',
 'WAV 文件不完整或格式不受支持。':'The WAV file is incomplete or unsupported.',
 '请使用 16 kHz、单声道 WAV，编码为 PCM16 或 Float32。':'Use 16 kHz mono WAV, encoded as PCM16 or Float32.',
 'WAV 时长应为 0.025 至 20 秒，请先裁剪后上传。':'Trim the WAV file to between 0.025 and 20 seconds.',
 '上传已过期，请重新选择文件。':'The upload expired. Select the file again.',
 '输入超出上下文容量，或包含不支持的格式。请缩短问题后重试。':'The input exceeds capacity or uses an unsupported format. Shorten it and retry.',
 '推理失败，请重试。若仍失败，请检查设备日志。':'Inference failed. Retry, or check the device logs if it persists.',
 '请求格式有误，请刷新页面后重试。':'Invalid request. Refresh the page and retry.',
 '连接中断，请检查设备连接后重试。':'Connection interrupted. Check the device connection and retry.',
 '请求来源不匹配，请直接打开设备地址。':'Request origin mismatch. Open the device address directly.',
 '请先从历史列表恢复此对话。':'Restore this conversation from the history list first.',
 '历史对话数量已达到上限。':'The conversation history limit has been reached.',
 '正在恢复对话，请稍候… 完成前暂时不能发送消息。':'Restoring conversation… Messaging is disabled until restoration completes.',
 '正在整理上下文，请稍候… 完成后将继续回答，期间暂时不能发送消息。':'Compacting context… Your response will resume when finished. Messaging is temporarily disabled.',
 '会话恢复失败，请开始新对话。':'Conversation restoration failed. Start a new chat.',
 '正在恢复对话，暂时无法对话':'Restoring conversation; messaging is disabled',
 '正在整理上下文，暂时无法对话':'Compacting context; messaging is disabled',
 '正在生成，可随时停止':'Generating; you can stop at any time','正在准备输入…':'Preparing input…',
 '上传的图片':'Uploaded image','音频预览':'Audio preview','图片已就绪':'Image ready','WAV 音频':'WAV audio','移除附件':'Remove attachment',
 '你的消息':'Your message','模型回答':'Model response','正在思考':'Thinking','正在理解输入…':'Processing input…',
 '已复制':'Copied','复制':'Copy','复制失败，请直接选中文本复制。':'Copy failed. Select and copy the text directly.',
 '本次生成已停止。':'Generation stopped.','模型未返回文字。':'The model returned no text.',
 '回答完成':'Response complete','已停止':'Stopped','已达到输出长度上限':'Output limit reached','已结束':'Finished',
 '本次达到长度上限，未加入记忆':'Output limit reached; this turn was not committed to memory',
 '查看运行统计':'View statistics','LM 首 token':'LM first token','输入 token（含媒体）':'Input tokens (including media)',
 '媒体 token':'Media tokens','媒体推理':'Media inference','本轮新增 prefill':'New prefill tokens','有效 KV token':'Valid KV tokens',
 '正在整理上下文…':'Compacting context…','正在生成…':'Generating…','正在停止，请稍候…':'Stopping… Please wait.',
 '正在等待设备结束当前调用，请勿重复提交。':'Waiting for the device to finish. Please do not submit again.',
 '设备推理中':'Device busy','设备已连接':'Device connected','设备未连接':'Device disconnected','连接中':'Connecting',
 '正在恢复对话':'Restoring conversation','一次请选择一个文件。':'Choose one file at a time.',
};
const uiFragments=[
 ['已整理上下文：','Context compacted: '],['上下文已整理：','Context compacted: '],['保留最近两轮对话。','The two latest turns are preserved.'],
 ['较早媒体仅保留文字摘要，细节请重新上传。','Older media is summarized as text. Re-upload for additional details.'],
 ['回答预留','Response reservation: '],['；达到容量前自动整理较早对话。','; older turns are compacted before capacity is reached.'],
 ['上下文已使用','Context used: '],['上下文用量','Context usage: '],['上下文','Context'],['有效 KV ','Valid KV '],
 ['（媒体 ',' (media '],['）；待写入 EOS ','); pending EOS '],['；待写入 EOS ','; pending EOS '],['；回答预留 ','; response reservation '],
 ['。包含模板、prefix3 和媒体，不含 AR padding。已整理 ',' Includes template, prefix3 and media; excludes AR padding. Compactions: '],
 [' 次。','.'],[' 本轮新增 ',' New prefill: '],['），输入后 ','); after input: '],['首字响应 ','First response '],
 [' · 本次达到长度上限，未加入记忆',' · Output limit reached; this turn was not committed to memory']
];
let uiLanguage=localStorage.getItem('omni-ui-language')==='en'?'en':'zh';
const originalText=new WeakMap(), originalAttributes=new WeakMap();
function englishUI(raw){
 const trimmed=raw.trim();if(uiTranslations[trimmed])return raw.replace(trimmed,uiTranslations[trimmed]);
 let result=raw;for(const [from,to] of uiFragments)result=result.split(from).join(to);return result;
}
// Dynamic renderers must translate synchronously, even in background tabs where
// animation frames may be delayed. Keep the source text for language switches.
function uiTextNode(raw) {
 const original=String(raw), node=document.createTextNode(uiLanguage==='en'?englishUI(original):original);
 originalText.set(node,original);return node;
}
function setUIText(element, raw) {
 const original=String(raw);
 element.textContent=uiLanguage==='en'?englishUI(original):original;
 if(element.firstChild)originalText.set(element.firstChild,original);
}
// Translate each interface component before joining it; retain each source for toggles.
function setUIMessageParts(element, parts) {
 element.replaceChildren();
 parts.forEach((part,index)=>{
  if(index)element.append(uiTextNode(' · '));
  element.append(uiTextNode(part));
 });
}
function setUIAttribute(element, attribute, raw) {
 const original=String(raw), old=originalAttributes.get(element)||{};
 old[attribute]=original;originalAttributes.set(element,old);
 element.setAttribute(attribute,uiLanguage==='en'?englishUI(original):original);
}
function translateInterface(){
 document.documentElement.lang=uiLanguage==='en'?'en':'zh-CN';
 const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let node;
 while((node=walker.nextNode())){
  if(node.parentElement?.closest('.history-title,option,script,style'))continue;
  if(node.parentElement?.closest('.bubble') && !originalText.has(node))continue;
  if(node.parentElement?.closest('.file-description') && node.parentElement.tagName!=='SMALL')continue;
  let original=originalText.get(node);
  if(original==null || (node.nodeValue!==original && node.nodeValue!==englishUI(original))) {original=node.nodeValue;originalText.set(node,original);}
  const next=uiLanguage==='en'?englishUI(original):original;if(node.nodeValue!==next)node.nodeValue=next;
 }
 for(const element of document.querySelectorAll('[placeholder],[title],[aria-label],[alt]')){
  const old=originalAttributes.get(element)||{};
  for(const attribute of ['placeholder','title','aria-label','alt']){
   const value=element.getAttribute(attribute);if(value==null)continue;
   if(old[attribute]==null || (value!==old[attribute] && value!==englishUI(old[attribute])))old[attribute]=value;
   const next=uiLanguage==='en'?englishUI(old[attribute]):old[attribute];if(next!==value)element.setAttribute(attribute,next);
  }
  originalAttributes.set(element,old);
 }
}
document.addEventListener('DOMContentLoaded',()=>{
 const selector=document.querySelector('#language-select');selector.value=uiLanguage;
 selector.addEventListener('change',()=>{uiLanguage=selector.value;localStorage.setItem('omni-ui-language',uiLanguage);translateInterface();});
 translateInterface();let scheduled=false;
 new MutationObserver(()=>{if(!scheduled){scheduled=true;requestAnimationFrame(()=>{scheduled=false;translateInterface();});}}).observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['placeholder','title','aria-label','alt']});
});
