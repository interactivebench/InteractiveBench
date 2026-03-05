import React, { useState, useRef, useCallback } from 'react';
import PokerTable, { PokerTableRef, TableStats } from './components/PokerTable';
import AggregatedStatsView from './components/AggregatedStatsView';
import { Play, Pause, BarChart2, Grid3X3, Maximize2, Layers } from 'lucide-react';
import clsx from 'clsx';

const NUM_TABLES = 10;

type ViewMode = 'grid' | 'single' | 'stats';

// Immutable chart data point - once added, never changes
export interface ChartDataPoint {
  sequence: number; // Global sequence number (1, 2, 3, ...)
  earnings: { [playerId: number]: number }; // Combined earnings across all tables at this moment
}

const MultiTableApp: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [selectedTable, setSelectedTable] = useState<number>(1);
  const [isGlobalRunning, setIsGlobalRunning] = useState(false);
  const [allTableStats, setAllTableStats] = useState<TableStats[]>([]);
  const [apiKeyOk] = useState<boolean>(() => Boolean(process.env.OPENROUTER_POKER_API || process.env.OPENROUTER_API_KEY));

  // Immutable chart history - only appends, never modifies past data
  const [chartHistory, setChartHistory] = useState<ChartDataPoint[]>([]);

  // Track handHistory length for each table to detect new hand completions
  const lastHandHistoryLengthRef = useRef<{ [tableId: number]: number }>({});

  const tableRefs = useRef<(PokerTableRef | null)[]>([]);

  const handleStatsUpdate = useCallback((stats: TableStats) => {
    setAllTableStats(prev => {
      const existing = prev.findIndex(s => s.tableId === stats.tableId);
      let newStats: TableStats[];
      if (existing >= 0) {
        newStats = [...prev];
        newStats[existing] = stats;
      } else {
        newStats = [...prev, stats];
      }

      // Check if this table has a new hand completion
      const prevLength = lastHandHistoryLengthRef.current[stats.tableId] || 0;
      const newLength = stats.handHistory.length;

      if (newLength > prevLength) {
        // New hand(s) completed - add immutable chart point(s)
        lastHandHistoryLengthRef.current[stats.tableId] = newLength;

        // Calculate combined earnings across all tables right now
        const combinedEarnings: { [playerId: number]: number } = {};
        for (let playerId = 1; playerId <= 6; playerId++) {
          let total = 0;
          for (const ts of newStats) {
            const player = ts.players.find(p => p.id === playerId);
            if (player) {
              total += player.totalWinnings;
            }
          }
          combinedEarnings[playerId] = total;
        }

        // Append new immutable chart point
        setChartHistory(prevChart => {
          const newPoint: ChartDataPoint = {
            sequence: prevChart.length + 1,
            earnings: { ...combinedEarnings } // Deep copy for immutability
          };
          return [...prevChart, newPoint];
        });
      }

      return newStats;
    });
  }, []);

  const handleToggleRunning = () => {
    setIsGlobalRunning(!isGlobalRunning);
  };

  const handleTableClick = (tableId: number) => {
    if (viewMode === 'grid') {
      setSelectedTable(tableId);
      setViewMode('single');
    }
  };

  return (
    <div className="w-full h-screen bg-slate-950 flex flex-col relative overflow-hidden">

      {/* Header / Nav */}
      <div className="h-16 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-6 z-50 shrink-0">
        <div className="flex items-center space-x-2">
          <Layers className="text-blue-500" />
          <h1 className="text-xl font-bold text-white tracking-wider">
            GEMINI POKER <span className="text-blue-500">PROS</span>
          </h1>
          <span className="text-xs text-slate-500 ml-2 bg-slate-800 px-2 py-0.5 rounded">
            {NUM_TABLES} Tables
          </span>
        </div>

        <div className="flex space-x-2">
          <button
            onClick={() => setViewMode('grid')}
            className={clsx(
              "flex items-center space-x-2 px-4 py-2 rounded-lg transition",
              viewMode === 'grid' ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
            )}
          >
            <Grid3X3 size={18} /> <span>All Tables</span>
          </button>
          <button
            onClick={() => setViewMode('single')}
            className={clsx(
              "flex items-center space-x-2 px-4 py-2 rounded-lg transition",
              viewMode === 'single' ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
            )}
          >
            <Maximize2 size={18} /> <span>Table {selectedTable}</span>
          </button>
          <button
            onClick={() => setViewMode('stats')}
            className={clsx(
              "flex items-center space-x-2 px-4 py-2 rounded-lg transition",
              viewMode === 'stats' ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
            )}
          >
            <BarChart2 size={18} /> <span>Analytics</span>
          </button>
        </div>

        <div className="flex items-center space-x-4">
          {viewMode === 'single' && (
            <select
              value={selectedTable}
              onChange={(e) => setSelectedTable(Number(e.target.value))}
              className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700"
            >
              {Array.from({ length: NUM_TABLES }, (_, i) => (
                <option key={i + 1} value={i + 1}>Table {i + 1}</option>
              ))}
            </select>
          )}

          <button
            onClick={handleToggleRunning}
            disabled={!apiKeyOk}
            className={clsx(
              "flex items-center space-x-2 px-4 py-2 rounded-lg font-bold shadow-lg transition hover:scale-105 active:scale-95",
              isGlobalRunning ? "bg-red-500 hover:bg-red-600" : "bg-green-500 hover:bg-green-600",
              !apiKeyOk && "opacity-60 cursor-not-allowed"
            )}
          >
            {isGlobalRunning ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
            <span>{isGlobalRunning ? "PAUSE ALL" : "START ALL"}</span>
          </button>
        </div>
      </div>

      {!apiKeyOk && (
        <div className="bg-red-900/70 text-red-100 text-sm px-6 py-2 border-b border-red-700 shrink-0">
          Missing OPENROUTER_POKER_API key. Set it in ~/.zshrc and restart the dev server; bots will auto-fold without it.
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 overflow-hidden relative">

        {/* Grid View - All 10 Tables in compact mode */}
        <div
          className={clsx(
            "w-full h-full p-4 overflow-auto",
            viewMode === 'grid' ? "block" : "hidden"
          )}
        >
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 auto-rows-fr min-h-full">
            {Array.from({ length: NUM_TABLES }, (_, i) => (
              <div
                key={i + 1}
                className="cursor-pointer hover:ring-2 hover:ring-blue-500 rounded-xl transition-all"
                onClick={() => handleTableClick(i + 1)}
              >
                <PokerTable
                  ref={(el) => { tableRefs.current[i] = el; }}
                  tableId={i + 1}
                  isGlobalRunning={isGlobalRunning}
                  onStatsUpdate={handleStatsUpdate}
                  compact={true}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Single Table View - Show selected table in full mode */}
        {/* We render a separate full-size view that overlays when in single mode */}
        <div
          className={clsx(
            "absolute inset-0 bg-slate-950",
            viewMode === 'single' ? "block" : "hidden"
          )}
        >
          {/* Render the selected table's full view */}
          <PokerTableFullView
            tableId={selectedTable}
            isGlobalRunning={isGlobalRunning}
            tableStats={allTableStats.find(s => s.tableId === selectedTable)}
          />
        </div>

        {/* Aggregated Stats View */}
        <div
          className={clsx(
            "absolute inset-0 bg-slate-950 overflow-auto",
            viewMode === 'stats' ? "block" : "hidden"
          )}
        >
          <AggregatedStatsView allTableStats={allTableStats} chartHistory={chartHistory} />
        </div>

      </div>

      {/* Footer Status Bar */}
      <div className="h-8 bg-slate-900 border-t border-slate-800 flex items-center justify-between px-6 text-xs text-slate-500 shrink-0">
        <div className="flex items-center space-x-4">
          <span className={clsx("flex items-center", isGlobalRunning ? "text-green-400" : "text-red-400")}>
            <span className={clsx("w-2 h-2 rounded-full mr-1", isGlobalRunning ? "bg-green-400 animate-pulse" : "bg-red-400")} />
            {isGlobalRunning ? 'Running' : 'Paused'}
          </span>
          <span>|</span>
          <span>Tables: {allTableStats.length}/{NUM_TABLES}</span>
          <span>|</span>
          <span>
            Total Hands: {allTableStats.reduce((sum, ts) => sum + ts.handNumber, 0)}
          </span>
        </div>
        <div>
          Logs: game-log-*.ndjson | Stats: stats-log-*.ndjson (1-{NUM_TABLES})
        </div>
      </div>

      {/* CSS Animations */}
      <style>{`
        @keyframes fadeInOut {
          0% { opacity: 0; transform: translateY(10px); }
          10% { opacity: 1; transform: translateY(0); }
          90% { opacity: 1; transform: translateY(0); }
          100% { opacity: 0; transform: translateY(-10px); }
        }
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(-20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .poker-table-felt {
          background-color: #14532d;
          background-image: radial-gradient(#166534 1px, transparent 1px);
          background-size: 20px 20px;
          box-shadow: inset 0 0 50px #052e16;
        }
      `}</style>
    </div>
  );
};

// Component to display a read-only full view of a table based on stats
// This doesn't run its own game loop - it just displays the current state from stats
interface PokerTableFullViewProps {
  tableId: number;
  isGlobalRunning: boolean;
  tableStats?: TableStats;
}

const PokerTableFullView: React.FC<PokerTableFullViewProps> = ({ tableId, isGlobalRunning, tableStats }) => {
  if (!tableStats) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <div className="text-slate-400">Loading Table {tableId}...</div>
      </div>
    );
  }

  const { players, handNumber, gameNumber, pot, communityCards, stage, dealerIndex, currentPlayerIndex, history } = tableStats;

  const getPositionClass = (index: number) => {
    const positions = [
      "top-[70%] left-1/2 -translate-x-1/2",
      "top-[60%] left-[5%]",
      "top-[15%] left-[5%]",
      "top-[-5%] left-1/2 -translate-x-1/2",
      "top-[15%] right-[5%]",
      "top-[60%] right-[5%]",
    ];
    return positions[index];
  };

  return (
    <div className="w-full h-full flex items-center justify-center p-4 relative">
      <div className="absolute top-4 left-4 bg-slate-800/80 px-3 py-1 rounded-lg">
        <span className="text-white font-bold">Table {tableId}</span>
        <span className="text-slate-400 ml-2">Game #{gameNumber} | Hand #{handNumber}</span>
      </div>

      <div className="relative w-full max-w-4xl aspect-[1.8/1] poker-table-felt rounded-[120px] border-[12px] border-amber-900 shadow-2xl flex items-center justify-center">
        <div className="absolute text-green-800/30 font-black text-4xl tracking-widest select-none pointer-events-none">
          TABLE {tableId}
        </div>

        <div className="z-10 flex flex-col items-center space-y-3">
          <div className="flex items-center justify-center space-x-2 h-20">
            {/* Community cards from stats */}
            {communityCards.map((card) => (
              <div key={card.id} className="w-12 h-16 bg-white rounded-md flex flex-col items-center justify-center shadow-lg border border-gray-300">
                <span className={clsx("text-lg font-bold", card.suit === 'H' || card.suit === 'D' ? 'text-red-600' : 'text-gray-900')}>
                  {card.rank}
                </span>
                <span className={clsx("text-lg", card.suit === 'H' || card.suit === 'D' ? 'text-red-600' : 'text-gray-900')}>
                  {card.suit === 'H' ? '♥' : card.suit === 'D' ? '♦' : card.suit === 'C' ? '♣' : '♠'}
                </span>
              </div>
            ))}
            {/* Placeholder for remaining cards */}
            {Array.from({ length: 5 - communityCards.length }).map((_, i) => (
              <div key={`empty-${i}`} className="w-12 h-16 border-2 border-green-800/50 rounded-md"></div>
            ))}
          </div>

          <div className="bg-black/60 px-5 py-1.5 rounded-full text-yellow-400 font-mono text-lg border border-yellow-600/50 shadow-lg">
            <span className="text-yellow-600">$</span>
            <span>{pot.toLocaleString()}</span>
          </div>

          <div className="text-green-200/60 font-medium text-xs uppercase tracking-widest">
            {stage}
          </div>
        </div>

        {/* Players */}
        {players.map((player, index) => {
          const isCurrentPlayer = currentPlayerIndex === index && player.status === 'thinking';
          return (
          <div
            key={player.id}
            className={clsx(
              "absolute flex flex-col items-center p-2 rounded-xl transition-all duration-300 w-48",
              getPositionClass(index),
              isCurrentPlayer ? "scale-105 z-20 bg-gray-900/90 ring-2 ring-yellow-400 shadow-[0_0_20px_rgba(250,204,21,0.5)]" : "bg-gray-900/60",
              player.isFolded ? "opacity-50 grayscale" : "opacity-100",
              player.status === 'winner' ? "ring-4 ring-green-500 shadow-[0_0_30px_rgba(34,197,94,0.6)] bg-green-900/80" : ""
            )}
          >
            <div className="flex flex-col items-center text-center w-full">
              <div className="flex items-center space-x-2 mb-1">
                <div className="bg-slate-700 p-1 rounded-full">
                  <div className="w-4 h-4 text-slate-300 flex items-center justify-center text-xs">P{player.id}</div>
                </div>
                <div className="flex flex-col items-start leading-tight">
                  <span className="font-bold text-white text-sm truncate max-w-[100px]">{player.name}</span>
                  <span className="text-[10px] text-slate-400 truncate max-w-[110px]">{player.model}</span>
                </div>
              </div>

              <div className="flex items-center text-yellow-400 font-mono text-sm bg-black/40 px-2 py-0.5 rounded-full mb-1">
                <span className="mr-1">$</span>
                {player.chips.toLocaleString()}
              </div>

              {/* Player Hand Cards */}
              {player.hand && player.hand.length > 0 && !player.isFolded && (
                <div className="flex space-x-1 mb-1">
                  {player.hand.map((card: any, cardIdx: number) => (
                    <div
                      key={cardIdx}
                      className="w-8 h-11 bg-white rounded text-center flex flex-col items-center justify-center shadow border border-gray-300"
                    >
                      <span className={clsx("text-xs font-bold", card.suit === 'H' || card.suit === 'D' ? 'text-red-600' : 'text-gray-900')}>
                        {card.rank}
                      </span>
                      <span className={clsx("text-xs", card.suit === 'H' || card.suit === 'D' ? 'text-red-600' : 'text-gray-900')}>
                        {card.suit === 'H' ? '♥' : card.suit === 'D' ? '♦' : card.suit === 'C' ? '♣' : '♠'}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Status */}
              <div className="h-6 flex items-center justify-center w-full">
                {player.status === 'thinking' ? (
                  <div className="flex items-center text-blue-300 text-xs animate-pulse">
                    Thinking...
                  </div>
                ) : player.lastAction ? (
                  <div className={clsx(
                    "text-xs font-bold px-2 py-0.5 rounded uppercase",
                    player.lastAction.type === 'FOLD' ? "bg-red-900/80 text-red-200" :
                    player.lastAction.type === 'RAISE' ? "bg-orange-600/80 text-white" :
                    player.lastAction.type === 'CHECK' ? "bg-gray-600/80 text-gray-200" :
                    player.lastAction.type === 'ALL_IN' ? "bg-purple-600 text-white" :
                    "bg-green-600/80 text-white"
                  )}>
                    {player.lastAction.type}
                  </div>
                ) : player.isFolded ? (
                  <div className="text-xs text-red-400">FOLDED</div>
                ) : null}
              </div>
            </div>
          </div>
        );
        })}
      </div>

      {/* Game Log */}
      <div className="absolute bottom-4 left-4 w-80 h-48 bg-slate-900/90 backdrop-blur border border-slate-700 rounded-xl p-3 overflow-hidden flex flex-col shadow-xl z-40">
        <h3 className="text-slate-400 text-xs font-bold uppercase mb-2 flex items-center justify-between">
          <span>Game Log</span>
          <span className="text-blue-500">T{tableId}</span>
        </h3>
        <div className="flex-1 overflow-y-auto space-y-1 text-[10px] font-mono">
          {(history || []).slice(-15).map((line, i) => (
            <div key={i} className="text-slate-300 border-b border-slate-800/50 pb-0.5 last:border-0">
              {line}
            </div>
          ))}
        </div>
      </div>

      {/* Mini leaderboard */}
      <div className="absolute bottom-4 right-4 w-64 bg-slate-900/90 backdrop-blur border border-slate-700 rounded-xl p-3 shadow-xl">
        <h3 className="text-slate-400 text-xs font-bold uppercase mb-2">Standings</h3>
        <div className="space-y-1">
          {[...players].sort((a, b) => b.chips - a.chips).map((p, idx) => (
            <div key={p.id} className="flex items-center justify-between text-xs">
              <span className="text-slate-400">{idx + 1}. {p.name}</span>
              <span className={clsx("font-mono", p.totalWinnings >= 0 ? "text-green-400" : "text-red-400")}>
                ${p.chips.toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default MultiTableApp;
