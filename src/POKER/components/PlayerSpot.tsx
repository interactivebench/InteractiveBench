import React from 'react';
import { Player, PlayerActionType } from '../types';
import Card from './Card';
import clsx from 'clsx';
import { User, DollarSign, BrainCircuit } from 'lucide-react';

interface PlayerSpotProps {
  player: Player;
  isActive: boolean;
  isDealer: boolean;
  positionClass: string; // CSS class for positioning around the table
  winner?: boolean;
}

const PlayerSpot: React.FC<PlayerSpotProps> = ({ player, isActive, isDealer, positionClass, winner }) => {
  
  // Determine border/glow based on status
  const containerClasses = clsx(
    "absolute flex flex-col items-center p-2 rounded-xl transition-all duration-300 w-48",
    positionClass,
    isActive ? "scale-105 z-20 bg-gray-900/90 ring-2 ring-yellow-400 shadow-[0_0_20px_rgba(250,204,21,0.5)]" : "bg-gray-900/60",
    player.isFolded ? "opacity-50 grayscale" : "opacity-100",
    winner ? "ring-4 ring-green-500 shadow-[0_0_30px_rgba(34,197,94,0.6)] bg-green-900/80" : ""
  );

  return (
    <div className={containerClasses}>
      {/* Dealer Button */}
      {isDealer && (
        <div className="absolute -top-3 -right-3 w-8 h-8 bg-white text-black font-bold rounded-full flex items-center justify-center border-2 border-gray-300 shadow-lg z-30">
          D
        </div>
      )}

      {/* Cards */}
      <div className="flex -space-x-4 mb-2">
        {player.hand.map((card, idx) => (
          <div key={idx} className={clsx("transition-transform", idx === 1 ? "rotate-6 translate-y-1" : "-rotate-6")}>
            {/* Show cards if it's a showdown or if it's the player (for this demo we show all or hide all based on debug, but let's hide faces unless showdown) */}
             <Card card={player.isFolded ? null : (winner || player.status === 'winner' || player.status === 'acted' ? card : null)} /> 
             {/* Note: For this demo, to see what AIs have, I'll reveal cards if they are active for the viewer to enjoy, or flip them. 
                 Let's reveal them all the time for the "Specator Mode" feel requested by user? 
                 Actually, standard poker view hides hole cards until showdown usually. 
                 But for an "AI Battle" viewer, seeing cards is more fun. I will show them.
             */}
          </div>
        ))}
        {/* If we want to reveal all cards for the spectator view: */}
        <div className="absolute inset-0 flex justify-center -space-x-4 pointer-events-none">
             {player.hand.map((card, idx) => (
               <div key={`reveal-${idx}`} className={clsx("transition-transform", idx === 1 ? "rotate-6 translate-y-1" : "-rotate-6")}>
                  <Card card={card} />
               </div>
             ))}
        </div>
      </div>

      {/* Avatar & Info */}
      <div className="flex flex-col items-center text-center w-full">
        <div className="flex items-center space-x-2 mb-1">
          <div className="bg-slate-700 p-1 rounded-full">
            <User size={16} className="text-slate-300" />
          </div>
          <div className="flex flex-col items-start leading-tight">
            <span className="font-bold text-white text-sm truncate max-w-[100px]">{player.name}</span>
            <span className="text-[10px] text-slate-400 truncate max-w-[110px]">{player.model}</span>
          </div>
        </div>
        
        <div className="flex items-center text-yellow-400 font-mono text-sm bg-black/40 px-2 py-0.5 rounded-full mb-1">
          <DollarSign size={12} className="mr-1" />
          {player.chips.toLocaleString()}
        </div>

        {/* Status / Action Bubble */}
        <div className="h-6 flex items-center justify-center w-full">
          {player.status === 'thinking' ? (
            <div className="flex items-center text-blue-300 text-xs animate-pulse">
              <BrainCircuit size={12} className="mr-1" /> Thinking...
            </div>
          ) : player.lastAction ? (
            <div className={clsx(
              "text-xs font-bold px-2 py-0.5 rounded uppercase",
              player.lastAction.type === PlayerActionType.FOLD ? "bg-red-900/80 text-red-200" :
              player.lastAction.type === PlayerActionType.RAISE ? "bg-orange-600/80 text-white" :
              player.lastAction.type === PlayerActionType.CHECK ? "bg-gray-600/80 text-gray-200" :
              player.lastAction.type === PlayerActionType.ALL_IN ? "bg-purple-600 text-white animate-bounce" :
              "bg-green-600/80 text-white"
            )}>
              {player.lastAction.type} {player.lastAction.amount > 0 && player.lastAction.type !== 'ALL_IN' && player.lastAction.type !== 'CALL' ? `to ${player.lastAction.amount}` : ''}
            </div>
          ) : null}
        </div>
        
        {/* Reasoning Bubble (Transient) */}
        {player.lastAction?.reasoning && player.status === 'acted' && (
           <div className="absolute top-full mt-2 w-64 bg-white/90 text-black text-[10px] p-2 rounded shadow-lg z-50 pointer-events-none opacity-0 animate-[fadeInOut_4s_ease-in-out_forwards]">
             "{player.lastAction.reasoning}"
           </div>
        )}
      </div>
    </div>
  );
};

export default PlayerSpot;
