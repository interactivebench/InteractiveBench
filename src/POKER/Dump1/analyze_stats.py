#!/usr/bin/env python3
"""
Analyze poker stats from 10 tables and create bar plots with error bars.
Reads stats-log-1.ndjson through stats-log-10.ndjson files.
"""

import json
import os
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from collections import defaultdict

# Player names (must match the order in the game)
PLAYER_NAMES = [
    'Grok 4.1 Fast',
    'Gemini 3 Flash',
    'GPT-5 Mini',
    'Moonshot Kimi K2',
    'DeepSeek V3.2',
    'Qwen3 Max',
]

# Short names for plotting
SHORT_NAMES = [
    'Grok',
    'Gemini',
    'GPT-5',
    'Kimi',
    'DeepSeek',
    'Qwen3',
]

# Colors for each player
COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899']


def read_stats_file(filepath: str) -> list[dict]:
    """Read NDJSON stats file and return list of entries."""
    entries = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except FileNotFoundError:
        print(f"Warning: {filepath} not found")
    except json.JSONDecodeError as e:
        print(f"Warning: JSON decode error in {filepath}: {e}")
    return entries


def get_final_stats(entries: list[dict]) -> dict | None:
    """Get the final stats entry (last one in the file)."""
    if not entries:
        return None
    return entries[-1]


def collect_table_winnings(base_dir: str, num_tables: int = 10) -> dict:
    """
    Collect total winnings per table for each player.
    Returns dict: {player_id: [winnings for table 1, table 2, ..., table 10]}
    """
    winnings_by_player = defaultdict(list)

    for table_id in range(1, num_tables + 1):
        filepath = os.path.join(base_dir, f'stats-log-{table_id}.ndjson')
        entries = read_stats_file(filepath)
        final_stats = get_final_stats(entries)

        if final_stats is None:
            # Fill with 0 if no data for this table
            for pid in range(1, 7):
                winnings_by_player[pid].append(0)
            continue

        for player in final_stats.get('players', []):
            pid = player['id']
            winnings_by_player[pid].append(player.get('totalWinnings', 0))

    return dict(winnings_by_player)


def collect_hand_by_hand_winnings(base_dir: str, num_tables: int = 10) -> dict:
    """
    Collect hand-by-hand winnings across all tables sequentially.
    Table 2 continues from table 1's final, table 3 from table 2's final, etc.
    Returns dict: {player_id: [cumulative earnings at each hand across all tables]}
    """
    # Track cumulative offset for each player (final earnings from previous tables)
    cumulative_offset = {pid: 0 for pid in range(1, 7)}
    # Store the continuous earnings timeline
    earnings_timeline = {pid: [] for pid in range(1, 7)}

    for table_id in range(1, num_tables + 1):
        filepath = os.path.join(base_dir, f'stats-log-{table_id}.ndjson')
        entries = read_stats_file(filepath)

        if not entries:
            continue

        # Track last seen earnings for this table to avoid duplicates
        last_hand = -1
        table_final_earnings = {pid: 0 for pid in range(1, 7)}

        for entry in entries:
            hand_num = entry.get('handNumber', 0)
            # Skip if same hand (multiple logs per hand)
            if hand_num <= last_hand:
                continue
            last_hand = hand_num

            for player in entry.get('players', []):
                pid = player['id']
                table_earnings = player.get('totalWinnings', 0)
                # Add offset from previous tables
                total = cumulative_offset[pid] + table_earnings
                earnings_timeline[pid].append(total)
                table_final_earnings[pid] = table_earnings

        # Update offset for next table
        for pid in range(1, 7):
            cumulative_offset[pid] += table_final_earnings[pid]

    return earnings_timeline


def collect_all_stats(base_dir: str, num_tables: int = 10) -> dict:
    """
    Collect final stats from all tables.
    Returns dict: {player_id: {metric: [values across tables]}}
    """
    stats_by_player = defaultdict(lambda: defaultdict(list))

    for table_id in range(1, num_tables + 1):
        filepath = os.path.join(base_dir, f'stats-log-{table_id}.ndjson')
        entries = read_stats_file(filepath)
        final_stats = get_final_stats(entries)

        if final_stats is None:
            print(f"No stats found for table {table_id}")
            continue

        for player in final_stats.get('players', []):
            pid = player['id']
            # Calculate average winnings per hand
            hands = player.get('handsPlayed', 0)
            total_winnings = player.get('totalWinnings', 0)
            avg_winnings = total_winnings / hands if hands > 0 else 0
            stats_by_player[pid]['avgWinnings'].append(avg_winnings)
            stats_by_player[pid]['chips'].append(player.get('chips', 0))
            stats_by_player[pid]['handsPlayed'].append(player.get('handsPlayed', 0))
            stats_by_player[pid]['folds'].append(player.get('folds', 0))
            stats_by_player[pid]['vpipCount'].append(player.get('vpipCount', 0))
            stats_by_player[pid]['avgThinkMs'].append(player.get('avgThinkMs', 0))
            stats_by_player[pid]['biggestWin'].append(player.get('biggestWin', 0))
            stats_by_player[pid]['biggestLoss'].append(player.get('biggestLoss', 0))

            # Calculate rates
            hands = player.get('handsPlayed', 0)
            if hands > 0:
                fold_rate = (player.get('folds', 0) / hands) * 100
                vpip_rate = (player.get('vpipCount', 0) / hands) * 100
            else:
                fold_rate = 0
                vpip_rate = 0
            stats_by_player[pid]['foldRate'].append(fold_rate)
            stats_by_player[pid]['vpipRate'].append(vpip_rate)

    return dict(stats_by_player)


def calculate_mean_std(stats_by_player: dict) -> dict:
    """
    Calculate mean and std for each metric across tables.
    Returns dict: {player_id: {metric: {'mean': x, 'std': y}}}
    """
    result = {}
    for pid, metrics in stats_by_player.items():
        result[pid] = {}
        for metric, values in metrics.items():
            if values:
                result[pid][metric] = {
                    'mean': np.mean(values),
                    'std': np.std(values),
                    'values': values
                }
            else:
                result[pid][metric] = {'mean': 0, 'std': 0, 'values': []}
    return result


def create_bar_plot(ax, stats: dict, metric: str, title: str, ylabel: str,
                    show_negative: bool = False):
    """Create a bar plot with error bars for a given metric."""
    x = np.arange(len(SHORT_NAMES))
    width = 0.6

    means = []
    stds = []

    for pid in range(1, 7):
        if pid in stats and metric in stats[pid]:
            means.append(stats[pid][metric]['mean'])
            stds.append(stats[pid][metric]['std'])
        else:
            means.append(0)
            stds.append(0)

    # Create bars with error bars
    bars = ax.bar(x, means, width, yerr=stds, capsize=5, color=COLORS,
                  edgecolor='white', linewidth=1.5, alpha=0.9,
                  error_kw={'elinewidth': 2, 'capthick': 2, 'ecolor': 'black'})

    ax.set_ylabel(ylabel, fontsize=11, fontweight='bold')
    ax.set_title(title, fontsize=13, fontweight='bold', pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(SHORT_NAMES, fontsize=10, rotation=15, ha='right')

    # Add value labels on bars
    for bar, mean, std in zip(bars, means, stds):
        height = bar.get_height()
        if abs(height) > 0:
            label = f'{mean:.1f}'
            if metric in ['chips', 'biggestWin', 'biggestLoss']:
                label = f'${mean:,.0f}'
            elif metric == 'avgWinnings':
                label = f'${mean:,.1f}'
            elif metric in ['foldRate', 'vpipRate']:
                label = f'{mean:.1f}%'
            elif metric == 'avgThinkMs':
                label = f'{mean:.0f}ms'

            va = 'bottom' if height >= 0 else 'top'
            offset = 3 if height >= 0 else -3
            ax.annotate(label, xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, offset), textcoords='offset points',
                       ha='center', va=va, fontsize=9, fontweight='bold')

    # Add grid
    ax.yaxis.grid(True, linestyle='--', alpha=0.3)
    ax.set_axisbelow(True)

    # Adjust y-axis for negative values
    if show_negative or min(means) < 0:
        ax.axhline(y=0, color='black', linewidth=0.5)


def create_trend_plot(earnings_timeline: dict, output_dir: str = '.'):
    """Create a trend line plot showing total earnings vs hands (continuous across all tables)."""
    plt.style.use('seaborn-v0_8-darkgrid')
    plt.rcParams['figure.facecolor'] = '#1e293b'
    plt.rcParams['axes.facecolor'] = '#334155'
    plt.rcParams['text.color'] = 'white'
    plt.rcParams['axes.labelcolor'] = 'white'
    plt.rcParams['xtick.color'] = 'white'
    plt.rcParams['ytick.color'] = 'white'
    plt.rcParams['axes.edgecolor'] = '#64748b'
    plt.rcParams['grid.color'] = '#64748b'

    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor('#1e293b')

    for pid in range(1, 7):
        earnings = earnings_timeline[pid]
        if earnings:
            hands = list(range(1, len(earnings) + 1))
            ax.plot(hands, earnings, linewidth=2, color=COLORS[pid-1],
                   label=SHORT_NAMES[pid-1], alpha=0.9)

    ax.set_xlabel('Hand Number (Continuous: Table 1 → 2 → ... → 10)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Total Earnings ($)', fontsize=12, fontweight='bold')
    ax.set_title('Total Earnings vs Hands (Tables 1-10 Sequential)',
                 fontsize=14, fontweight='bold', pad=15)

    # Add zero line
    ax.axhline(y=0, color='white', linewidth=0.8, linestyle='--', alpha=0.5)

    # Add grid
    ax.yaxis.grid(True, linestyle='--', alpha=0.3)
    ax.xaxis.grid(True, linestyle='--', alpha=0.3)
    ax.set_axisbelow(True)

    # Format y-axis with dollar amounts
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x:,.0f}'))

    # Legend
    ax.legend(loc='upper left', fontsize=10, framealpha=0.9,
              facecolor='#334155', edgecolor='#64748b')

    plt.tight_layout()

    # Save figure
    output_path = os.path.join(output_dir, 'poker_stats_trend.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor(), edgecolor='none')
    print(f"Saved: {output_path}")
    plt.close(fig)


def create_all_plots(stats: dict, output_dir: str = '.'):
    """Create all bar plots and save to files."""

    # Set up the style
    plt.style.use('seaborn-v0_8-darkgrid')
    plt.rcParams['figure.facecolor'] = '#1e293b'
    plt.rcParams['axes.facecolor'] = '#334155'
    plt.rcParams['text.color'] = 'white'
    plt.rcParams['axes.labelcolor'] = 'white'
    plt.rcParams['xtick.color'] = 'white'
    plt.rcParams['ytick.color'] = 'white'
    plt.rcParams['axes.edgecolor'] = '#64748b'
    plt.rcParams['grid.color'] = '#64748b'

    # Create figure with subplots
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle('Poker AI Performance Comparison (Mean ± Std over 10 Tables)',
                 fontsize=16, fontweight='bold', color='white', y=0.98)

    # Plot each metric
    metrics = [
        ('avgWinnings', 'Avg Winnings per Hand', 'Winnings ($)', True),
        ('vpipRate', 'VPIP Rate', 'VPIP (%)', False),
        ('foldRate', 'Fold Rate', 'Fold Rate (%)', False),
        ('avgThinkMs', 'Average Think Time', 'Time (ms)', False),
        ('biggestWin', 'Biggest Single Win', 'Win Amount ($)', False),
        ('biggestLoss', 'Biggest Single Loss', 'Loss Amount ($)', True),
    ]

    for ax, (metric, title, ylabel, show_neg) in zip(axes.flat, metrics):
        create_bar_plot(ax, stats, metric, title, ylabel, show_neg)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])

    # Save figure
    output_path = os.path.join(output_dir, 'poker_stats_comparison.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor(), edgecolor='none')
    print(f"Saved: {output_path}")

    # Also save individual plots
    for metric, title, ylabel, show_neg in metrics:
        fig_single, ax_single = plt.subplots(figsize=(10, 6))
        fig_single.patch.set_facecolor('#1e293b')
        create_bar_plot(ax_single, stats, metric, title, ylabel, show_neg)
        plt.tight_layout()
        single_path = os.path.join(output_dir, f'poker_stats_{metric}.png')
        plt.savefig(single_path, dpi=150, bbox_inches='tight',
                   facecolor=fig_single.get_facecolor(), edgecolor='none')
        plt.close(fig_single)
        print(f"Saved: {single_path}")

    plt.show()


def print_summary(stats: dict):
    """Print a text summary of the stats."""
    print("\n" + "="*80)
    print("POKER AI PERFORMANCE SUMMARY (Mean ± Std over 10 Tables)")
    print("="*80)

    metrics_to_print = [
        ('avgWinnings', 'Avg Winnings/Hand', '$'),
        ('chips', 'Final Chips', '$'),
        ('handsPlayed', 'Hands Played', ''),
        ('foldRate', 'Fold Rate', '%'),
        ('vpipRate', 'VPIP Rate', '%'),
        ('avgThinkMs', 'Avg Think Time', 'ms'),
        ('biggestWin', 'Biggest Win', '$'),
        ('biggestLoss', 'Biggest Loss', '$'),
    ]

    for metric, label, unit in metrics_to_print:
        print(f"\n{label}:")
        print("-" * 50)

        # Collect and sort by mean
        player_stats = []
        for pid in range(1, 7):
            if pid in stats and metric in stats[pid]:
                mean = stats[pid][metric]['mean']
                std = stats[pid][metric]['std']
                player_stats.append((SHORT_NAMES[pid-1], mean, std))

        # Sort by mean (descending for most metrics, ascending for losses)
        reverse = metric != 'biggestLoss'
        player_stats.sort(key=lambda x: x[1], reverse=reverse)

        for rank, (name, mean, std) in enumerate(player_stats, 1):
            if unit == '$':
                print(f"  {rank}. {name:12s}: {unit}{mean:>10,.1f} ± {std:>8,.1f}")
            elif unit == '%':
                print(f"  {rank}. {name:12s}: {mean:>10.1f}{unit} ± {std:>6.1f}{unit}")
            elif unit == 'ms':
                print(f"  {rank}. {name:12s}: {mean:>10.1f}{unit} ± {std:>8.1f}{unit}")
            else:
                print(f"  {rank}. {name:12s}: {mean:>10.1f} ± {std:>8.1f}")


def main():
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.resolve()

    print("Reading stats from 10 tables...")
    stats_by_player = collect_all_stats(str(script_dir), num_tables=10)

    if not stats_by_player:
        print("No stats files found! Make sure stats-log-*.ndjson files exist.")
        print(f"Looking in: {script_dir}")
        return

    print(f"Found stats for {len(stats_by_player)} players")

    # Collect hand-by-hand winnings for trend plot (continuous across tables)
    earnings_timeline = collect_hand_by_hand_winnings(str(script_dir), num_tables=10)

    # Calculate mean and std
    stats = calculate_mean_std(stats_by_player)

    # Print summary
    print_summary(stats)

    # Create plots
    print("\nGenerating plots...")
    create_all_plots(stats, str(script_dir))

    # Create trend plot
    print("\nGenerating trend plot...")
    create_trend_plot(earnings_timeline, str(script_dir))

    print("\nDone!")


if __name__ == '__main__':
    main()
