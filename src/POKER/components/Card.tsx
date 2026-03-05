import React from 'react';
import { Card as CardType, Suit } from '../types';
import clsx from 'clsx';

interface CardProps {
  card: CardType | null; // Null means face down
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

const suitSymbols: Record<Suit, string> = {
  'H': '♥',
  'D': '♦',
  'C': '♣',
  'S': '♠',
};

const suitColors: Record<Suit, string> = {
  'H': 'text-red-500',
  'D': 'text-red-500',
  'C': 'text-gray-800',
  'S': 'text-gray-800',
};

const Card: React.FC<CardProps> = ({ card, className, size = 'md' }) => {
  const sizeClasses = {
    sm: 'w-8 h-12 text-xs rounded',
    md: 'w-14 h-20 text-base rounded-md',
    lg: 'w-20 h-28 text-xl rounded-lg',
  };

  if (!card) {
    // Face down card back
    return (
      <div className={clsx(
        "bg-blue-800 border-2 border-white shadow-md flex items-center justify-center relative overflow-hidden",
        sizeClasses[size],
        className
      )}>
        <div className="absolute inset-0 opacity-20 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')]"></div>
        <div className="w-full h-full bg-gradient-to-br from-blue-700 to-blue-900"></div>
      </div>
    );
  }

  return (
    <div className={clsx(
      "bg-white border border-gray-300 shadow-md flex flex-col items-center justify-between py-1 select-none",
      sizeClasses[size],
      className
    )}>
      <div className={clsx("self-start px-1 font-bold leading-none", suitColors[card.suit])}>
        {card.rank}
        <div className="text-[0.6em]">{suitSymbols[card.suit]}</div>
      </div>
      <div className={clsx("text-2xl", suitColors[card.suit])}>
        {suitSymbols[card.suit]}
      </div>
      <div className={clsx("self-end px-1 font-bold leading-none rotate-180", suitColors[card.suit])}>
        {card.rank}
        <div className="text-[0.6em]">{suitSymbols[card.suit]}</div>
      </div>
    </div>
  );
};

export default Card;