import React from 'react';
import { Player, HandHistory } from '../types';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { Trophy, TrendingUp, Timer, Slash, ArrowUpCircle, ArrowDownCircle, Layers } from 'lucide-react';
import { TableStats } from './PokerTable';
import { ChartDataPoint } from '../MultiTableApp';

interface AggregatedStatsViewProps {
  allTableStats: TableStats[];
  chartHistory: ChartDataPoint[]; // Immutable chart data from parent
}

interface AggregatedPlayer {
  id: number;
  name: string;
  model: string;
  totalChips: number;
  totalWinnings: number;
  avgChips: number;
  avgWinnings: number;
  totalThinkMs: number;
  totalThinkCount: number;
  avgThinkMs: number;
  totalHandsPlayed: number;
  totalFolds: number;
  foldRate: number;
  totalVpip: number;
  vpipRate: number;
  biggestWin: number;
  biggestLoss: number;
  tablesPlayed: number;
}

const PLAYER_PROFILES = [
  { name: 'Grok 4.1 Fast', model: 'x-ai/grok-4.1-fast' },
  { name: 'Gemini 3 Flash', model: 'google/gemini-3-flash-preview' },
  { name: 'GPT-5 Mini', model: 'openai/gpt-5-mini' },
  { name: 'Moonshot Kimi K2', model: 'moonshotai/kimi-k2-thinking' },
  { name: 'DeepSeek V3.2', model: 'deepseek/deepseek-v3.2' },
  { name: 'Qwen3 Max', model: 'qwen/qwen3-max' },
];

const tabs = [
  { id: 'leaderboard', label: 'Leaderboard' },
  { id: 'think', label: 'Avg Think Time' },
  { id: 'folds', label: 'Fold Rate' },
  { id: 'vpip', label: 'VPIP' },
  { id: 'win', label: 'Biggest Win' },
  { id: 'loss', label: 'Biggest Loss' },
  { id: 'tables', label: 'Per Table' },
];

const colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'];

const AggregatedStatsView: React.FC<AggregatedStatsViewProps> = ({ allTableStats, chartHistory }) => {
  const [tab, setTab] = React.useState('leaderboard');

  // Aggregate player stats across all tables
  const aggregatedPlayers: AggregatedPlayer[] = React.useMemo(() => {
    const playerMap = new Map<number, AggregatedPlayer>();

    // Initialize with player profiles
    for (let i = 0; i < 6; i++) {
      playerMap.set(i + 1, {
        id: i + 1,
        name: PLAYER_PROFILES[i]?.name || `Bot ${i + 1}`,
        model: PLAYER_PROFILES[i]?.model || 'unknown',
        totalChips: 0,
        totalWinnings: 0,
        avgChips: 0,
        avgWinnings: 0,
        totalThinkMs: 0,
        totalThinkCount: 0,
        avgThinkMs: 0,
        totalHandsPlayed: 0,
        totalFolds: 0,
        foldRate: 0,
        totalVpip: 0,
        vpipRate: 0,
        biggestWin: 0,
        biggestLoss: 0,
        tablesPlayed: 0,
      });
    }

    // Aggregate from all tables
    for (const tableStats of allTableStats) {
      for (const player of tableStats.players) {
        const agg = playerMap.get(player.id);
        if (!agg) continue;

        agg.totalChips += player.chips;
        agg.totalWinnings += player.totalWinnings;
        agg.totalThinkMs += player.thinkTotalMs || 0;
        agg.totalThinkCount += player.thinkCount || 0;
        agg.totalHandsPlayed += player.handsPlayed || 0;
        agg.totalFolds += player.folds || 0;
        agg.totalVpip += player.vpipCount || 0;
        agg.biggestWin = Math.max(agg.biggestWin, player.biggestWin || 0);
        agg.biggestLoss = Math.min(agg.biggestLoss, player.biggestLoss || 0);
        agg.tablesPlayed++;
      }
    }

    // Calculate averages
    for (const agg of playerMap.values()) {
      const tableCount = Math.max(1, agg.tablesPlayed);
      agg.avgChips = agg.totalChips / tableCount;
      agg.avgWinnings = agg.totalWinnings / tableCount;
      agg.avgThinkMs = agg.totalThinkCount > 0 ? agg.totalThinkMs / agg.totalThinkCount : 0;
      agg.foldRate = agg.totalHandsPlayed > 0 ? (agg.totalFolds / agg.totalHandsPlayed) * 100 : 0;
      agg.vpipRate = agg.totalHandsPlayed > 0 ? (agg.totalVpip / agg.totalHandsPlayed) * 100 : 0;
    }

    return Array.from(playerMap.values()).sort((a, b) => b.totalWinnings - a.totalWinnings);
  }, [allTableStats]);

  // Chart data from immutable chartHistory - each point is captured when a hand ENDS
  // Past points NEVER change - they are snapshots frozen at the moment of hand completion
  const combinedChartData = React.useMemo(() => {
    return chartHistory.map(point => {
      const dataPoint: any = { name: `${point.sequence}` };
      for (let playerId = 1; playerId <= 6; playerId++) {
        dataPoint[`Player ${playerId}`] = point.earnings[playerId] || 0;
      }
      return dataPoint;
    });
  }, [chartHistory]);

  // Per-table summary data for bar chart
  const perTableData = React.useMemo(() => {
    return allTableStats.map(ts => {
      const data: any = { name: `T${ts.tableId}`, hands: ts.handNumber };
      ts.players.forEach(p => {
        data[p.name] = p.totalWinnings;
      });
      return data;
    });
  }, [allTableStats]);

  // Use chartHistory.length for total hands - this matches the chart exactly
  const totalHands = chartHistory.length;
  const totalGames = allTableStats.reduce((sum, ts) => sum + ts.gameNumber, 0);

  return (
    <div className="w-full h-full p-6 overflow-y-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-3xl font-bold text-white flex items-center">
            <Trophy className="mr-3 text-yellow-400" /> Aggregated Statistics
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            <Layers className="inline w-4 h-4 mr-1" />
            {allTableStats.length} Tables | {totalHands} Total Hands | {totalGames} Games
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-3 py-1.5 rounded-full text-sm font-semibold border ${tab === t.id ? 'bg-blue-600 text-white border-blue-500' : 'bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-700'}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'leaderboard' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
            <h3 className="text-xl font-semibold text-slate-200 mb-4">
              Combined Standings (All Tables)
            </h3>
            <div className="space-y-4">
              {aggregatedPlayers.map((p, idx) => (
                <div key={p.id} className="flex items-center justify-between bg-slate-700/50 p-4 rounded-xl">
                  <div className="flex items-center space-x-4">
                    <div className={`w-8 h-8 flex items-center justify-center rounded-full font-bold ${idx === 0 ? 'bg-yellow-500 text-black' : idx === 1 ? 'bg-gray-400 text-black' : idx === 2 ? 'bg-orange-700 text-white' : 'bg-slate-600 text-slate-300'}`}>
                      {idx + 1}
                    </div>
                    <div>
                      <div className="font-bold text-white">{p.name}</div>
                      <div className="text-xs text-slate-400">{p.model}</div>
                      <div className="text-[10px] text-slate-500">{p.tablesPlayed} tables active</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xl font-mono text-green-400 font-bold">
                      ${p.totalChips.toLocaleString()}
                    </div>
                    <div className={`text-sm ${p.totalWinnings >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      {p.totalWinnings >= 0 ? '+' : ''}{p.totalWinnings.toLocaleString()} total
                    </div>
                    <div className="text-xs text-slate-400">
                      Avg: ${p.avgChips.toFixed(0)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700 flex flex-col">
            <h3 className="text-xl font-semibold text-slate-200 mb-4 flex items-center">
              <TrendingUp className="mr-2 text-blue-400" /> Combined Earnings Trend
            </h3>
            <div className="flex-grow min-h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={combinedChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="name" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px' }}
                    itemStyle={{ color: '#e2e8f0' }}
                  />
                  <Legend />
                  {aggregatedPlayers.map((p, i) => (
                    <Line
                      key={p.id}
                      type="monotone"
                      dataKey={`Player ${p.id}`}
                      name={p.name}
                      stroke={colors[i % colors.length]}
                      strokeWidth={2}
                      dot={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {tab === 'think' && (
        <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
          <h3 className="text-xl font-semibold text-slate-200 mb-4 flex items-center">
            <Timer className="mr-2 text-blue-300" /> Average Thinking Time (All Tables)
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {aggregatedPlayers.map(p => (
              <div key={p.id} className="bg-slate-700/50 border border-slate-600 rounded-xl p-4">
                <div className="text-white font-semibold">{p.name}</div>
                <div className="text-xs text-slate-400 mb-1">{p.model}</div>
                <div className="text-lg text-blue-300 font-mono">{p.avgThinkMs.toFixed(1)} ms</div>
                <div className="text-xs text-slate-400">Total samples: {p.totalThinkCount}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'folds' && (
        <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
          <h3 className="text-xl font-semibold text-slate-200 mb-4 flex items-center">
            <Slash className="mr-2 text-red-300" /> Fold Rate (All Tables)
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {aggregatedPlayers.map(p => (
              <div key={p.id} className="bg-slate-700/50 border border-slate-600 rounded-xl p-4">
                <div className="text-white font-semibold">{p.name}</div>
                <div className="text-xs text-slate-400 mb-1">{p.model}</div>
                <div className="text-lg text-red-300 font-mono">{p.foldRate.toFixed(1)}%</div>
                <div className="text-xs text-slate-400">
                  Folds: {p.totalFolds} / Hands: {p.totalHandsPlayed}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'vpip' && (
        <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
          <h3 className="text-xl font-semibold text-slate-200 mb-4 flex items-center">
            <TrendingUp className="mr-2 text-emerald-300" /> VPIP (All Tables)
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {aggregatedPlayers.map(p => (
              <div key={p.id} className="bg-slate-700/50 border border-slate-600 rounded-xl p-4">
                <div className="text-white font-semibold">{p.name}</div>
                <div className="text-xs text-slate-400 mb-1">{p.model}</div>
                <div className="text-lg text-emerald-300 font-mono">{p.vpipRate.toFixed(1)}%</div>
                <div className="text-xs text-slate-400">
                  VPIP Hands: {p.totalVpip} / Hands: {p.totalHandsPlayed}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'win' && (
        <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
          <h3 className="text-xl font-semibold text-slate-200 mb-4 flex items-center">
            <ArrowUpCircle className="mr-2 text-green-300" /> Biggest Single Win (Across All Tables)
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {aggregatedPlayers.map(p => (
              <div key={p.id} className="bg-slate-700/50 border border-slate-600 rounded-xl p-4">
                <div className="text-white font-semibold">{p.name}</div>
                <div className="text-xs text-slate-400 mb-1">{p.model}</div>
                <div className="text-lg text-green-300 font-mono">${p.biggestWin.toLocaleString()}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'loss' && (
        <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
          <h3 className="text-xl font-semibold text-slate-200 mb-4 flex items-center">
            <ArrowDownCircle className="mr-2 text-orange-300" /> Biggest Single Loss (Across All Tables)
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {aggregatedPlayers.map(p => (
              <div key={p.id} className="bg-slate-700/50 border border-slate-600 rounded-xl p-4">
                <div className="text-white font-semibold">{p.name}</div>
                <div className="text-xs text-slate-400 mb-1">{p.model}</div>
                <div className="text-lg text-orange-300 font-mono">${Math.abs(p.biggestLoss).toLocaleString()}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'tables' && (
        <div className="space-y-6">
          <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
            <h3 className="text-xl font-semibold text-slate-200 mb-4 flex items-center">
              <Layers className="mr-2 text-purple-300" /> Per-Table Winnings
            </h3>
            <div className="h-[400px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={perTableData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="name" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px' }}
                    itemStyle={{ color: '#e2e8f0' }}
                  />
                  <Legend />
                  {PLAYER_PROFILES.map((p, i) => (
                    <Bar
                      key={i}
                      dataKey={p.name}
                      fill={colors[i % colors.length]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            {allTableStats.map(ts => (
              <div key={ts.tableId} className="bg-slate-800 rounded-xl p-4 border border-slate-700">
                <div className="text-white font-bold mb-2">Table {ts.tableId}</div>
                <div className="text-xs text-slate-400 mb-2">
                  Game #{ts.gameNumber} | Hand #{ts.handNumber}
                </div>
                <div className="space-y-1">
                  {[...ts.players].sort((a, b) => b.totalWinnings - a.totalWinnings).map((p, idx) => (
                    <div key={p.id} className="flex justify-between text-[10px]">
                      <span className="text-slate-400">{idx + 1}. {p.name.split(' ')[0]}</span>
                      <span className={p.totalWinnings >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {p.totalWinnings >= 0 ? '+' : ''}{p.totalWinnings}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default AggregatedStatsView;
