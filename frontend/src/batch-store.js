export class BatchStore {
  constructor(api) { this.api = api; this.batches = new Map(); this.listeners = new Set(); this.timers = new Map(); }
  subscribe(listener) { this.listeners.add(listener); return () => this.listeners.delete(listener); }
  emit(error) { this.listeners.forEach(listener => listener(Array.from(this.batches.values()), error)); }
  async restore() {
    const batches = await this.api.listBatches();
    batches.forEach(batch => this.batches.set(batch.id, batch));
    this.emit();
    await Promise.all(batches.filter(batch => batch.status === 'running').map(batch => this.watch(batch.id)));
  }
  async create(payload) {
    const batch = await this.api.createBatch(payload);
    this.batches.set(batch.id, batch); this.emit(); this.watch(batch.id); return batch;
  }
  async watch(id) {
    if (this.timers.has(id)) return;
    const tick = async () => {
      try {
        const batch = await this.api.batch(id);
        this.batches.set(id, batch); this.emit();
        if (batch.status === 'completed' || batch.status === 'stopped') {
          clearInterval(this.timers.get(id)); this.timers.delete(id);
        }
      } catch (error) {
        clearInterval(this.timers.get(id)); this.timers.delete(id); this.emit(error);
      }
    };
    await tick();
    if (!this.timers.has(id)) this.timers.set(id, setInterval(tick, 500));
  }
  async stop(id) { const batch = await this.api.stopBatch(id); this.batches.set(id, batch); this.emit(); }
}
