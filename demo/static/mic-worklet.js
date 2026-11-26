class OmniMicInput extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(1024);
    this.offset = 0;
    this.port.onmessage = ({data}) => {
      if (data !== 'flush') return;
      if (this.offset) this.send(this.buffer.slice(0, this.offset));
      this.offset = 0;
      this.port.postMessage({flushed: true});
    };
  }

  send(samples) {
    this.port.postMessage({samples}, [samples.buffer]);
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    for (let start = 0; start < channel.length;) {
      const count = Math.min(channel.length - start, this.buffer.length - this.offset);
      this.buffer.set(channel.subarray(start, start + count), this.offset);
      this.offset += count;
      start += count;
      if (this.offset === this.buffer.length) {
        this.send(this.buffer);
        this.buffer = new Float32Array(1024);
        this.offset = 0;
      }
    }
    // The output is silent. Keep the graph running without playing back the microphone.
    return true;
  }
}

registerProcessor('omni-mic-input', OmniMicInput);
