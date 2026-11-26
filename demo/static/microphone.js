'use strict';

const MIC_MAX_SECONDS = 20;
const MIC_FLUSH_TIMEOUT_MS = 1000;
const MIC_WAV_RATE = 16000;
const MIC_SIGNAL_RMS = 0.004;

function micRms(samples) {
  let sum = 0, square = 0;
  for (const sample of samples) {
    sum += sample;
    square += sample * sample;
  }
  const mean = sum / samples.length;
  return Math.sqrt(Math.max(0, square / samples.length - mean * mean));
}

async function micWav(samples, rate) {
  const length = Math.min(MIC_WAV_RATE * MIC_MAX_SECONDS, Math.round(samples.length * MIC_WAV_RATE / rate));
  if (length < 400) throw new Error('short');
  if (rate !== MIC_WAV_RATE) {
    const context = new OfflineAudioContext(1, length, MIC_WAV_RATE);
    const buffer = context.createBuffer(1, samples.length, rate);
    buffer.copyToChannel(samples, 0);
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    source.start();
    samples = (await context.startRendering()).getChannelData(0);
  }
  const bytes = new ArrayBuffer(44 + length * 2);
  const view = new DataView(bytes);
  function label(offset, value) {
    for (const [index, character] of [...value].entries()) view.setUint8(offset + index, character.charCodeAt(0));
  }
  label(0, 'RIFF');
  view.setUint32(4, bytes.byteLength - 8, true);
  label(8, 'WAVE');
  label(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, MIC_WAV_RATE, true);
  view.setUint32(28, MIC_WAV_RATE * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  label(36, 'data');
  view.setUint32(40, length * 2, true);
  for (let i = 0; i < length; i++) {
    const sample = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, Math.round(sample * (sample < 0 ? 32768 : 32767)), true);
  }
  return new File([bytes], 'recording.wav', {type: 'audio/wav'});
}

function mountMicrophone({attach, canRecord, onChange}) {
  const button = document.querySelector('#microphone-button');
  const panel = document.querySelector('#microphone-panel');
  const status = document.querySelector('#microphone-status');
  const check = document.querySelector('#microphone-check');
  const start = document.querySelector('#microphone-start');
  const stop = document.querySelector('#microphone-stop');
  const closeButton = document.querySelector('#microphone-close');
  const level = document.querySelector('#microphone-level');
  const time = document.querySelector('#microphone-time');
  const devices = navigator.mediaDevices;
  const supported = window.isSecureContext && devices?.getUserMedia && window.AudioContext && window.AudioWorkletNode;
  let phase = 'idle', checkedDevice = null, capture = null, revision = 0;

  const active = () => ['opening', 'checking', 'recording', 'finishing', 'encoding'].includes(phase);

  function show(next, message) {
    phase = next;
    panel.dataset.phase = phase;
    check.disabled = !supported || active();
    start.disabled = !supported || phase !== 'ready';
    start.hidden = phase === 'recording' || phase === 'finishing';
    stop.hidden = phase !== 'recording' && phase !== 'finishing';
    stop.disabled = phase !== 'recording';
    level.hidden = !['checking', 'recording', 'finishing'].includes(phase);
    time.hidden = phase !== 'recording' && phase !== 'finishing';
    if (level.hidden) level.value = 0;
    setUIText(status, message);
    onChange();
  }

  function release(current) {
    if (!current) return;
    if (capture === current) capture = null;
    clearTimeout(current.timer);
    if (current.node) {
      current.node.port.onmessage = null;
      current.node.port.close();
      current.node.disconnect();
    }
    current.source?.disconnect();
    current.stream?.getTracks().forEach(track => track.stop());
    current.context?.close().catch(() => {});
  }

  function fail(message) {
    checkedDevice = null;
    release(capture);
    show('idle', message);
  }

  function close(restoreFocus = false) {
    if (panel.hidden) return;
    revision++;
    release(capture);
    panel.hidden = true;
    button.setAttribute('aria-expanded', 'false');
    show('idle', '');
    if (restoreFocus) button.focus();
  }

  async function encode(current) {
    if (capture !== current) return;
    release(current);
    const epoch = revision;
    show('encoding', '正在准备录音…');
    try {
      if (current.frames * MIC_WAV_RATE < current.rate * 400) throw new Error('short');
      if (!current.audible) throw new Error('silent');
      const samples = new Float32Array(current.frames);
      let offset = 0;
      for (const chunk of current.chunks) {
        samples.set(chunk, offset);
        offset += chunk.length;
      }
      const wav = await micWav(samples, current.rate);
      if (epoch !== revision) return;
      // Attachment insertion shares the normal composer path.
      const next = checkedDevice === null ? 'idle' : 'ready';
      show(next, next === 'ready' ? '麦克风检查通过，可以开始录音。' : '先检查麦克风，再开始录音。');
      if (attach(wav)) show(next, '录音已添加，可以试听、删除或重新录音。');
    } catch (error) {
      if (epoch !== revision) return;
      const message = error.message === 'short' ? '录音太短，请重新录音。' :
        error.message === 'silent' ? '录音没有声音，请检查输入音量后重试。' : '录音转换失败，请重新录音。';
      show(checkedDevice === null ? 'idle' : 'ready', message);
    }
  }

  function receive(current, data) {
    if (capture !== current) return;
    if (data.flushed && phase === 'finishing') {
      void encode(current);
      return;
    }
    const samples = data.samples;
    if (!samples?.length) return;
    const rms = micRms(samples);
    level.value = Math.min(1, Math.sqrt(rms * 3));
    const audible = rms >= MIC_SIGNAL_RMS;
    if (phase === 'checking') {
      if (audible) current.voiced += samples.length;
      if (current.voiced >= current.rate * 0.12) {
        checkedDevice = current.device;
        release(current);
        show('ready', '麦克风检查通过，可以开始录音。');
      }
      return;
    }
    if (phase !== 'recording' && phase !== 'finishing') return;
    const count = Math.min(samples.length, current.limit - current.frames);
    if (count) {
      current.chunks.push(samples.subarray(0, count));
      current.frames += count;
      current.audible ||= audible;
      time.textContent = (current.frames / current.rate).toFixed(1) + ' / 20 s';
    }
    if (phase === 'recording' && current.frames === current.limit) void encode(current);
  }

  async function openCapture(testing) {
    if (!supported || active() || (!testing && (checkedDevice === null || !canRecord()))) return;
    if (testing) checkedDevice = null;
    const current = {chunks: [], frames: 0, voiced: 0, audible: false};
    capture = current;
    show('opening', '正在打开麦克风…');
    try {
      current.context = new AudioContext();
      const resumed = current.context.resume().then(() => true, () => false);
      const audio = {channelCount: {ideal: 1}, echoCancellation: false, noiseSuppression: false, autoGainControl: false};
      if (!testing && checkedDevice) audio.deviceId = {exact: checkedDevice};
      const stream = await devices.getUserMedia({audio});
      if (capture !== current) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      current.stream = stream;
      const [track] = stream.getAudioTracks();
      if (!track || track.readyState !== 'live' || !await resumed) throw new Error('unavailable');
      current.device = track.getSettings().deviceId || '';
      track.addEventListener('ended', () => {
        if (capture === current) fail('麦克风已断开，请重新检查。');
      });
      await current.context.audioWorklet.addModule('/static/mic-worklet.js');
      if (capture !== current) return;
      if (track.readyState !== 'live') throw new Error('unavailable');
      current.rate = current.context.sampleRate;
      current.limit = current.rate * MIC_MAX_SECONDS;
      current.source = current.context.createMediaStreamSource(stream);
      current.node = new AudioWorkletNode(current.context, 'omni-mic-input', {
        channelCount: 1, channelCountMode: 'explicit'
      });
      current.node.port.onmessage = event => receive(current, event.data);
      current.node.onprocessorerror = () => {
        if (capture === current) fail('麦克风不可用，请检查设备后重试。');
      };
      current.source.connect(current.node);
      current.node.connect(current.context.destination);
      time.textContent = '0.0 / 20 s';
      if (testing) {
        show('checking', '请说一句话，检查麦克风是否收得到声音。');
        current.timer = setTimeout(() => fail('没有检测到声音，请检查静音或输入音量后重试。'), 6000);
      } else {
        show('recording', '正在录音，最长 20 秒。');
        current.timer = setTimeout(stopRecording, MIC_MAX_SECONDS * 1000);
      }
    } catch (error) {
      if (capture !== current) return;
      const message = error.name === 'NotAllowedError' || error.name === 'SecurityError' ?
        '麦克风权限未授权，请在浏览器中允许后重试。' :
        error.name === 'NotFoundError' || error.name === 'OverconstrainedError' ?
          '找不到麦克风，请连接设备后重试。' : '麦克风不可用，请检查设备后重试。';
      fail(message);
    }
  }

  function stopRecording() {
    if (phase !== 'recording') return;
    const current = capture;
    clearTimeout(current.timer);
    show('finishing', '正在准备录音…');
    current.timer = setTimeout(() => {
      if (capture === current) fail('录音采集未完成，请重新录音。');
    }, MIC_FLUSH_TIMEOUT_MS);
    current.node.port.postMessage('flush');
  }

  button.addEventListener('click', () => {
    if (!panel.hidden) {
      close(true);
      return;
    }
    panel.hidden = false;
    button.setAttribute('aria-expanded', 'true');
    if (!window.isSecureContext) show('idle', '请通过 HTTPS 打开页面以使用麦克风。');
    else if (!supported) show('idle', '当前浏览器不支持麦克风录音。');
    else if (checkedDevice === null) show('idle', '先检查麦克风，再开始录音。');
    else show('ready', '麦克风检查通过，可以开始录音。');
    (phase === 'ready' ? start : check.disabled ? closeButton : check).focus();
  });
  closeButton.addEventListener('click', () => close(true));
  check.addEventListener('click', () => { void openCapture(true); });
  start.addEventListener('click', () => { void openCapture(false); });
  stop.addEventListener('click', stopRecording);
  panel.addEventListener('keydown', event => {
    if (event.key === 'Escape') close(true);
  });
  devices?.addEventListener('devicechange', () => {
    if (checkedDevice === null) return;
    checkedDevice = null;
    // Only the active track's ended event tells us that this input disconnected.
    if (!panel.hidden && !active()) show('idle', '麦克风设备已变化，请重新检查。');
  });
  window.addEventListener('pagehide', () => close());

  return {active, close};
}
