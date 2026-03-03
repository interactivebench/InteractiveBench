import React from 'react';
import { Player, HandHistory } from '../types';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Trophy, TrendingUp, Timer, Slash, ArrowUpCircle, ArrowDownCircle } from 'lucide-react';

interface StatsViewProps {
  players: Player[];
  history: HandHistory[];
}

const tabs = [
  { id: 'leaderboard', label: 'Leaderboard' },
  { id: 'think', label: 'Avg Thinking Time' },
  { id: 'folds', label: 'Fold Rate' },
  { id: 'vpip', label: 'VPIP' },
  { id: 'win', label: 'Biggest Win' },
  { id: 'loss', label: 'Biggest Loss' },
];

const StatsView: React.FC<StatsViewProps> = ({ players, history }) => {
  const [tab, setTab] = React.useState('leaderboard');
  const sortedPlayers = [...players].sort((a, b) => (b.totalWinnings ?? b.chips) - (a.totalWinnings ?? a.chips));

  const chartData = history.map((h) => {
    const point: any = { name: `H${h.handNumber}` };
    for (const [pid, earnings] of Object.entries(h.earnings)) {
      point[`Player ${pid}`] = earnings;
    }
    return point;
  });

  const colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'];

  return (
    <div className="w-full h-full p-6 overflow-y-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-3xl font-bold text-white flex items-center">
          <Trophy className="mr-3 text-yellow-400" /> Statistics
        </h2>
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
            <h3 className="text-xl font-semibold text-slate-200 mb-4 flex items-center">
               Current Standings
            </h3>
            <div className="space-y-4">
              {sortedPlayers.map((p, idx) => (
                <div key={p.id} className="flex items-center justify-between bg-slate-700/50 p-4 rounded-xl">
                  <div className="flex items-center space-x-4">
                    <div className={`w-8 h-8 flex items-center justify-center rounded-full font-bold ${idx === 0 ? 'bg-yellow-500 text-black' : idx === 1 ? 'bg-gray-400 text-black' : idx === 2 ? 'bg-orange-700 text-white' : 'bg-slate-600 text-slate-300'}`}>
                      {idx + 1}
                    </div>
                    <div>
                      <div className="font-bold text-white">{p.name}</div>
                      <div className="text-xs text-slate-400">Bot ID: {p.id}</div>
                      <div className="text-[11px] text-slate-500">{p.model}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xl font-mono text-green-400 font-bold">${p.chips.toLocaleString()}</div>
                    <div className={`text-xs ${p.totalWinnings >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      {p.totalWinnings >= 0 ? '+' : ''}{p.totalWinnings} lifetime
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700 flex flex-col">
            <h3 className="text-xl font-semibold text-slate-200 mb-4 flex items-center">
              <TrendingUp className="mr-2 text-blue-400" /> Earnings Trend
            </h3>
            <div className="flex-grow min-h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="name" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px' }}
                    itemStyle={{ color: '#e2e8f0' }}
                  />
                  <Legend />
                  {players.map((p, i) => (
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
            <Timer className="mr-2 text-blue-300" /> Average Thinking Time
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {players.map(p => {
              const avg = (p.thinkCount || 0) > 0 ? (p.thinkTotalMs || 0) / (p.thinkCount || 1) : 0;
              return (
                <div key={p.id} className="bg-slate-700/50 border border-slate-600 rounded-xl p-4">
                  <div className="text-white font-semibold">{p.name}</div>
                  <div className="text-xs text-slate-400 mb-1">{p.model}</div>
                  <div className="text-lg text-blue-300 font-mono">{avg.toFixed(1)} ms</div>
                  <div className="text-xs text-slate-400">Samples: {p.thinkCount || 0}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {tab === 'folds' && (
        <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
          <h3 className="text-xl font-semibold text-slate-200 mb-4 flex items-center">
            <Slash className="mr-2 text-red-300" /> Fold Rate
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {players.map(p => {
              const hands = p.handsPlayed || 0;
              const folds = p.folds || 0;
              const rate = hands > 0 ? (folds / hands) * 100 : 0;
              return (
                <div key={p.id} className="bg-slate-700/50 border border-slate-600 rounded-xl p-4">
                  <div className="text-white font-semibold">{p.name}</div>
                  <div className="text-xs text-slate-400 mb-1">{p.model}</div>
                  <div className="text-lg text-red-300 font-mono">{rate.toFixed(1)}%</div>
                  <div className="text-xs text-slate-400">Folds: {folds} / Hands: {hands}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {tab === 'vpip' && (
        <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
          <h3 className="text-xl font-semibold text-slate-200 mb-4 flex items-center">
            <TrendingUp className="mr-2 text-emerald-300" /> VPIP (Voluntarily Put $ In Pot)
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {players.map(p => {
              const hands = p.handsPlayed || 0;
              const vpip = p.vpipCount || 0;
              const rate = hands > 0 ? (vpip / hands) * 100 : 0;
              return (
                <div key={p.id} className="bg-slate-700/50 border border-slate-600 rounded-xl p-4">
                  <div className="text-white font-semibold">{p.name}</div>
                  <div className="text-xs text-slate-400 mb-1">{p.model}</div>
                  <div className="text-lg text-emerald-300 font-mono">{rate.toFixed(1)}%</div>
                  <div className="text-xs text-slate-400">VPIP Hands: {vpip} / Hands: {hands}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {tab === 'win' && (
        <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
          <h3 className="text-xl font-semibold text-slate-200 mb-4 flex items-center">
            <ArrowUpCircle className="mr-2 text-green-300" /> Biggest Single Win
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {players.map(p => (
              <div key={p.id} className="bg-slate-700/50 border border-slate-600 rounded-xl p-4">
                <div className="text-white font-semibold">{p.name}</div>
                <div className="text-xs text-slate-400 mb-1">{p.model}</div>
                <div className="text-lg text-green-300 font-mono">${(p.biggestWin || 0).toLocaleString()}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'loss' && (
        <div className="bg-slate-800 rounded-2xl p-6 shadow-xl border border-slate-700">
          <h3 className="text-xl font-semibold text-slate-200 mb-4 flex items-center">
            <ArrowDownCircle className="mr-2 text-orange-300" /> Biggest Single Loss
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {players.map(p => (
              <div key={p.id} className="bg-slate-700/50 border border-slate-600 rounded-xl p-4">
                <div className="text-white font-semibold">{p.name}</div>
                <div className="text-xs text-slate-400 mb-1">{p.model}</div>
                <div className="text-lg text-orange-300 font-mono">${Math.abs(p.biggestLoss || 0).toLocaleString()}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default StatsView;
