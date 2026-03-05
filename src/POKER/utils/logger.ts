export interface LogEvent {
  type: string;
  data: any;
  timestamp: number;
  tableId?: number;
}

export interface StatsLogEntry {
  timestamp: number;
  tableId: number;
  gameNumber: number;
  handNumber: number;
  players: {
    id: number;
    name: string;
    model: string;
    chips: number;
    handWinnings: number; // Winnings for THIS hand only (delta), can be summed across sessions
    handsPlayed: number;
    folds: number;
    vpipCount: number;
    avgThinkMs: number;
    biggestWin: number;
    biggestLoss: number;
  }[];
}

// Track previous totalWinnings per table per player to calculate hand delta
const prevWinnings: { [tableId: number]: { [playerId: number]: number } } = {};

// Track last logged hand per table to prevent duplicate logging
const lastLoggedHand: { [tableId: number]: number } = {};

const getCacheKey = (tableId?: number) => tableId ? `poker-log-cache-${tableId}` : 'poker-log-cache';

const send = (entry: LogEvent, tableId?: number) => {
  const payload = JSON.stringify(entry);
  const endpoint = tableId ? `/__pokerlog/${tableId}` : '/__pokerlog';

  try {
    if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
      const blob = new Blob([payload], { type: 'application/json' });
      navigator.sendBeacon(endpoint, blob);
      return;
    }
  } catch (err) {
    console.error('Beacon log failed', err);
  }
  try {
    fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload,
      keepalive: true,
    }).catch(() => {});
  } catch (err) {
    console.error('Fetch log failed', err);
  }
};

export const logEvent = (type: string, data: any, tableId?: number) => {
  const entry: LogEvent = { type, data, timestamp: Date.now(), tableId };
  try {
    const cacheKey = getCacheKey(tableId);
    const existing = JSON.parse(localStorage.getItem(cacheKey) || '[]');
    existing.push(entry);
    if (existing.length > 500) existing.shift();
    localStorage.setItem(cacheKey, JSON.stringify(existing));
  } catch {
    // Ignore localStorage issues
  }
  send(entry, tableId);
};

export const getLogCache = (tableId?: number): LogEvent[] => {
  try {
    const cacheKey = getCacheKey(tableId);
    return JSON.parse(localStorage.getItem(cacheKey) || '[]');
  } catch {
    return [];
  }
};

export const clearLogCache = (tableId?: number) => {
  try {
    const cacheKey = getCacheKey(tableId);
    localStorage.removeItem(cacheKey);
  } catch {
    // Ignore
  }
};

// Stats logging - writes to stats-log-{tableId}.ndjson
const sendStats = (entry: StatsLogEntry, tableId: number) => {
  const payload = JSON.stringify(entry);
  const endpoint = `/__pokerstats/${tableId}`;

  try {
    if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
      const blob = new Blob([payload], { type: 'application/json' });
      navigator.sendBeacon(endpoint, blob);
      return;
    }
  } catch (err) {
    console.error('Beacon stats log failed', err);
  }
  try {
    fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload,
      keepalive: true,
    }).catch(() => {});
  } catch (err) {
    console.error('Fetch stats log failed', err);
  }
};

export const logStats = (
  tableId: number,
  gameNumber: number,
  handNumber: number,
  players: {
    id: number;
    name: string;
    model: string;
    chips: number;
    totalWinnings: number;
    handsPlayed?: number;
    folds?: number;
    vpipCount?: number;
    thinkTotalMs?: number;
    thinkCount?: number;
    biggestWin?: number;
    biggestLoss?: number;
  }[]
) => {
  // Prevent duplicate logging for the same hand
  if (lastLoggedHand[tableId] === handNumber) {
    return;
  }
  lastLoggedHand[tableId] = handNumber;

  // Initialize table tracking if needed
  if (!prevWinnings[tableId]) {
    prevWinnings[tableId] = {};
  }

  const entry: StatsLogEntry = {
    timestamp: Date.now(),
    tableId,
    gameNumber,
    handNumber,
    players: players.map(p => {
      // Calculate delta (this hand's winnings)
      const prev = prevWinnings[tableId][p.id] || 0;
      const handWinnings = p.totalWinnings - prev;
      // Update tracking for next hand
      prevWinnings[tableId][p.id] = p.totalWinnings;

      return {
        id: p.id,
        name: p.name,
        model: p.model,
        chips: p.chips,
        handWinnings,
        handsPlayed: p.handsPlayed || 0,
        folds: p.folds || 0,
        vpipCount: p.vpipCount || 0,
        avgThinkMs: p.thinkCount && p.thinkCount > 0 ? (p.thinkTotalMs || 0) / p.thinkCount : 0,
        biggestWin: p.biggestWin || 0,
        biggestLoss: p.biggestLoss || 0,
      };
    })
  };
  sendStats(entry, tableId);
};
