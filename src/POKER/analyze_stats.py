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

# Professional color palette (colorblind-friendly, academic paper style)
# Based on Tableau 10 / ColorBrewer qualitative palettes
COLORS = ['#4E79A7', '#E15759', '#59A14F', '#F28E2B', '#B07AA1', '#76B7B2']

# Hatching patterns for print-friendly distinction
HATCHES = ['', '//', '\\\\', 'xx', '..', '++']


def setup_academic_style():
    """Configure matplotlib for professional academic paper style."""
    plt.style.use('seaborn-v0_8-whitegrid')

    # Font settings - use serif for academic feel
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif', 'Georgia', 'serif'],
        'font.size': 11,
        'axes.titlesize': 13,
        'axes.labelsize': 11,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10,
        'figure.titlesize': 14,

        # Clean white background
        'figure.facecolor': 'white',
        'axes.facecolor': 'white',
        'savefig.facecolor': 'white',

        # Text colors
        'text.color': '#333333',
        'axes.labelcolor': '#333333',
        'xtick.color': '#333333',
        'ytick.color': '#333333',

        # Subtle grid
        'axes.grid': True,
        'grid.alpha': 0.3,
        'grid.linestyle': '-',
        'grid.linewidth': 0.5,
        'grid.color': '#CCCCCC',

        # Clean spines
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.linewidth': 1.0,
        'axes.edgecolor': '#333333',

        # High quality output
        'figure.dpi': 150,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.1,

        # Legend
        'legend.frameon': True,
        'legend.framealpha': 0.95,
        'legend.edgecolor': '#CCCCCC',
        'legend.fancybox': False,
    })


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
    Collect total winnings and hands played per table for each player.
    Sums handWinnings across all entries in each table.
    Returns dict: {player_id: [(winnings, hands) for table 1, table 2, ..., table 10]}
    """
    data_by_player = defaultdict(list)

    for table_id in range(1, num_tables + 1):
        filepath = os.path.join(base_dir, f'stats-log-{table_id}.ndjson')
        entries = read_stats_file(filepath)

        if not entries:
            # Fill with (0, 0) if no data for this table
            for pid in range(1, 7):
                data_by_player[pid].append((0, 0))
            continue

        # Sum handWinnings across all entries
        table_winnings = defaultdict(int)
        table_hands = defaultdict(int)
        last_hand = -1
        for entry in entries:
            hand_num = entry.get('handNumber', 0)
            if hand_num <= last_hand:
                continue
            last_hand = hand_num

            for player in entry.get('players', []):
                pid = player['id']
                hand_winnings = player.get('handWinnings', player.get('totalWinnings', 0))
                table_winnings[pid] += hand_winnings
                table_hands[pid] = player.get('handsPlayed', 0)

        for pid in range(1, 7):
            data_by_player[pid].append((table_winnings.get(pid, 0), table_hands.get(pid, 0)))

    return dict(data_by_player)


def collect_hand_by_hand_winnings(base_dir: str, num_tables: int = 10) -> dict:
    """
    Collect hand-by-hand winnings across all tables sequentially.
    Uses handWinnings (per-hand delta) and sums them up for cumulative total.
    Table 2 continues from table 1's final, table 3 from table 2's final, etc.
    Returns dict: {player_id: [cumulative earnings at each hand across all tables]}
    """
    # Track running total for each player
    running_total = {pid: 0 for pid in range(1, 7)}
    # Store the continuous earnings timeline
    earnings_timeline = {pid: [] for pid in range(1, 7)}

    for table_id in range(1, num_tables + 1):
        filepath = os.path.join(base_dir, f'stats-log-{table_id}.ndjson')
        entries = read_stats_file(filepath)

        if not entries:
            continue

        # Track last seen hand to avoid duplicates
        last_hand = -1

        for entry in entries:
            hand_num = entry.get('handNumber', 0)
            # Skip if same hand (multiple logs per hand)
            if hand_num <= last_hand:
                continue
            last_hand = hand_num

            for player in entry.get('players', []):
                pid = player['id']
                # Use handWinnings (delta for this hand) - sum them up for cumulative
                hand_winnings = player.get('handWinnings', player.get('totalWinnings', 0))
                running_total[pid] += hand_winnings
                earnings_timeline[pid].append(running_total[pid])

    return earnings_timeline


def collect_all_stats(base_dir: str, num_tables: int = 10) -> dict:
    """
    Collect final stats from all tables.
    Sums handWinnings across all entries in each table to get total winnings.
    Returns dict: {player_id: {metric: [values across tables]}}
    """
    stats_by_player = defaultdict(lambda: defaultdict(list))

    for table_id in range(1, num_tables + 1):
        filepath = os.path.join(base_dir, f'stats-log-{table_id}.ndjson')
        entries = read_stats_file(filepath)

        if not entries:
            print(f"No stats found for table {table_id}")
            continue

        # Sum handWinnings across all entries in this table
        table_winnings = defaultdict(int)
        last_entry_by_player = {}

        last_hand = -1
        for entry in entries:
            hand_num = entry.get('handNumber', 0)
            if hand_num <= last_hand:
                continue
            last_hand = hand_num

            for player in entry.get('players', []):
                pid = player['id']
                # Sum up handWinnings (delta) for total
                hand_winnings = player.get('handWinnings', player.get('totalWinnings', 0))
                table_winnings[pid] += hand_winnings
                last_entry_by_player[pid] = player

        # Use final entry for other stats, but use summed winnings
        for pid, player in last_entry_by_player.items():
            total_winnings = table_winnings[pid]
            hands = player.get('handsPlayed', 0)
            avg_winnings = total_winnings / hands if hands > 0 else 0

            stats_by_player[pid]['avgWinnings'].append(avg_winnings)
            stats_by_player[pid]['totalWinnings'].append(total_winnings)
            stats_by_player[pid]['chips'].append(player.get('chips', 0))
            stats_by_player[pid]['handsPlayed'].append(player.get('handsPlayed', 0))
            stats_by_player[pid]['folds'].append(player.get('folds', 0))
            stats_by_player[pid]['vpipCount'].append(player.get('vpipCount', 0))
            stats_by_player[pid]['avgThinkMs'].append(player.get('avgThinkMs', 0))
            stats_by_player[pid]['biggestWin'].append(player.get('biggestWin', 0))
            stats_by_player[pid]['biggestLoss'].append(player.get('biggestLoss', 0))

            # Calculate rates
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


def calculate_trimmed_stats(table_data: dict) -> dict:
    """
    Calculate trimmed mean and std for per-hand average winnings,
    excluding 2 highest and 2 lowest tables (uses 6 out of 10 tables).
    table_data: dict from collect_table_winnings() {player_id: [(winnings, hands) per table]}
    Returns dict: {player_id: {'mean': x, 'std': y, 'excluded': [(winnings, hands), ...]}}
    """
    result = {}
    for pid, data in table_data.items():
        # Calculate per-hand average for each table
        avg_per_hand = []
        for winnings, hands in data:
            if hands > 0:
                avg_per_hand.append(winnings / hands)
            else:
                avg_per_hand.append(0)

        if len(avg_per_hand) >= 5:
            # Sort to exclude 2 lowest and 2 highest
            sorted_vals = sorted(avg_per_hand)
            # Exclude 2 lowest and 2 highest (keep middle 6)
            trimmed = sorted_vals[2:-2]
            excluded_low = sorted_vals[:2]
            excluded_high = sorted_vals[-2:]
            result[pid] = {
                'mean': np.mean(trimmed),
                'std': np.std(trimmed),
                'excluded_low': excluded_low,
                'excluded_high': excluded_high,
                'values': trimmed
            }
        elif len(avg_per_hand) > 0:
            # Not enough data to trim, use all
            result[pid] = {
                'mean': np.mean(avg_per_hand),
                'std': np.std(avg_per_hand),
                'excluded_low': [],
                'excluded_high': [],
                'values': avg_per_hand
            }
        else:
            result[pid] = {
                'mean': 0,
                'std': 0,
                'excluded_low': [],
                'excluded_high': [],
                'values': []
            }
    return result


def create_bar_plot(ax, stats: dict, metric: str, title: str, ylabel: str,
                    show_negative: bool = False):
    """Create a professional bar plot with error bars for a given metric."""
    x = np.arange(len(SHORT_NAMES))
    width = 0.65

    means = []
    stds = []

    for pid in range(1, 7):
        if pid in stats and metric in stats[pid]:
            means.append(stats[pid][metric]['mean'])
            stds.append(stats[pid][metric]['std'])
        else:
            means.append(0)
            stds.append(0)

    # Create bars with error bars - professional style
    bars = ax.bar(x, means, width, yerr=stds, capsize=3, color=COLORS,
                  edgecolor='#333333', linewidth=0.8, alpha=0.85,
                  error_kw={'elinewidth': 1.2, 'capthick': 1.2, 'ecolor': '#555555'})

    # Add hatching for print-friendliness
    for bar, hatch in zip(bars, HATCHES):
        bar.set_hatch(hatch)

    ax.set_ylabel(ylabel)
    ax.set_title(title, pad=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(SHORT_NAMES, rotation=0, ha='center')

    # Add value labels on bars
    for bar, mean, std in zip(bars, means, stds):
        height = bar.get_height()
        if abs(height) > 0:
            label = f'{mean:.1f}'
            if metric in ['chips', 'biggestWin', 'biggestLoss']:
                label = f'{mean:,.0f}'
            elif metric == 'avgWinnings':
                label = f'{mean:,.1f}'
            elif metric in ['foldRate', 'vpipRate']:
                label = f'{mean:.1f}%'
            elif metric == 'avgThinkMs':
                label = f'{mean:.0f}'

            va = 'bottom' if height >= 0 else 'top'
            offset = 4 if height >= 0 else -4
            ax.annotate(label, xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, offset), textcoords='offset points',
                       ha='center', va=va, fontsize=8, color='#333333')

    # Only y-axis grid
    ax.yaxis.grid(True)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)

    # Zero line for negative values
    if show_negative or min(means) < 0:
        ax.axhline(y=0, color='#333333', linewidth=0.8, zorder=1)

    # Add VPIP reference lines and region labels for poker strategy thresholds
    if metric == 'vpipRate':
        # Get y-axis limits for region positioning
        _, y_max = ax.get_ylim()

        # Draw threshold lines
        ax.axhline(y=14, color='#888888', linewidth=1.0, linestyle='--', alpha=0.6, zorder=1)
        ax.axhline(y=20, color='#888888', linewidth=1.0, linestyle='--', alpha=0.6, zorder=1)

        # Label the regions on the right side
        # Nitty region (below 14%)
        ax.text(len(SHORT_NAMES) - 0.3, 7, 'Nitty', fontsize=8,
                va='center', ha='right', color='#E15759', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='#E15759', alpha=0.8))

        # TAG region (14-20%)
        ax.text(len(SHORT_NAMES) - 0.3, 17, 'TAG', fontsize=8,
                va='center', ha='right', color='#4E79A7', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='#4E79A7', alpha=0.8))

        # Balanced/LAG region (above 20%)
        ax.text(len(SHORT_NAMES) - 0.3, min(26, y_max - 2), 'Balanced', fontsize=8,
                va='center', ha='right', color='#59A14F', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='#59A14F', alpha=0.8))


def create_trimmed_avg_plot(trimmed_stats: dict, output_dir: str = '.'):
    """Create a professional bar plot for trimmed per-hand average winnings."""
    setup_academic_style()

    fig, ax = plt.subplots(figsize=(8, 5))

    x = np.arange(len(SHORT_NAMES))
    width = 0.65

    means = []
    stds = []

    for pid in range(1, 7):
        if pid in trimmed_stats:
            means.append(trimmed_stats[pid]['mean'])
            stds.append(trimmed_stats[pid]['std'])
        else:
            means.append(0)
            stds.append(0)

    # Create bars with error bars - professional style
    bars = ax.bar(x, means, width, yerr=stds, capsize=3, color=COLORS,
                  edgecolor='#333333', linewidth=0.8, alpha=0.85,
                  error_kw={'elinewidth': 1.2, 'capthick': 1.2, 'ecolor': '#555555'})

    # Add hatching for print-friendliness
    for bar, hatch in zip(bars, HATCHES):
        bar.set_hatch(hatch)

    ax.set_ylabel('Average Winnings per Hand ($)')
    ax.set_title('Trimmed Mean Performance\n(Excluding 2 Best & 2 Worst Tables per Model)',
                 fontweight='bold', pad=12)
    ax.set_xticks(x)
    ax.set_xticklabels(SHORT_NAMES, rotation=0, ha='center')

    # Add value labels on bars
    for bar, mean, std in zip(bars, means, stds):
        height = bar.get_height()
        if abs(height) > 0.01:
            label = f'{mean:,.1f}'
            va = 'bottom' if height >= 0 else 'top'
            offset = 4 if height >= 0 else -4
            ax.annotate(label, xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, offset), textcoords='offset points',
                       ha='center', va=va, fontsize=9, color='#333333')

    # Only y-axis grid
    ax.yaxis.grid(True)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)

    # Add zero line
    if min(means) < 0:
        ax.axhline(y=0, color='#333333', linewidth=0.8, zorder=1)

    plt.tight_layout()

    # Save figure at high resolution
    output_path = os.path.join(output_dir, 'poker_stats_trimmed_winnings.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved: {output_path}")

    # Also save as PDF for vector graphics
    pdf_path = os.path.join(output_dir, 'poker_stats_trimmed_winnings.pdf')
    plt.savefig(pdf_path, format='pdf', bbox_inches='tight', facecolor='white')
    print(f"Saved: {pdf_path}")

    plt.close(fig)


def create_trend_plot(earnings_timeline: dict, output_dir: str = '.'):
    """Create a professional trend line plot showing total earnings vs hands."""
    setup_academic_style()

    fig, ax = plt.subplots(figsize=(10, 5))

    # Line styles for print-friendliness
    line_styles = ['-', '--', '-.', ':', '-', '--']
    markers = ['o', 's', '^', 'D', 'v', 'p']

    for pid in range(1, 7):
        earnings = earnings_timeline[pid]
        if earnings:
            hands = list(range(1, len(earnings) + 1))
            # Subsample markers for clarity (every N points)
            marker_every = max(1, len(hands) // 15)
            ax.plot(hands, earnings, linewidth=1.8, color=COLORS[pid-1],
                   label=SHORT_NAMES[pid-1], alpha=0.9,
                   linestyle=line_styles[pid-1],
                   marker=markers[pid-1], markersize=4,
                   markevery=marker_every, markeredgecolor='white',
                   markeredgewidth=0.5)

    ax.set_xlabel('Hand Number (Sequential: Tables 1→10)')
    ax.set_ylabel('Cumulative Earnings ($)')
    ax.set_title('Cumulative Earnings Trajectory Across All Tables',
                 fontweight='bold', pad=12)

    # Add zero line
    ax.axhline(y=0, color='#666666', linewidth=0.8, linestyle='-', alpha=0.5, zorder=1)

    # Grid settings
    ax.yaxis.grid(True)
    ax.xaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)

    # Format y-axis with dollar amounts
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x:,.0f}'))

    # Professional legend - outside plot or upper left
    ax.legend(loc='upper left', ncol=2, frameon=True,
              fancybox=False, edgecolor='#CCCCCC')

    plt.tight_layout()

    # Save figure at high resolution
    output_path = os.path.join(output_dir, 'poker_stats_trend.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved: {output_path}")

    # Also save as PDF for vector graphics
    pdf_path = os.path.join(output_dir, 'poker_stats_trend.pdf')
    plt.savefig(pdf_path, format='pdf', bbox_inches='tight', facecolor='white')
    print(f"Saved: {pdf_path}")

    plt.close(fig)


def create_avg_trend_plot(earnings_timeline: dict, output_dir: str = '.'):
    """Create a plot showing average earnings per hand over time (cumulative earnings / hands)."""
    setup_academic_style()

    fig, ax = plt.subplots(figsize=(10, 5))

    # Line styles for print-friendliness
    line_styles = ['-', '--', '-.', ':', '-', '--']
    markers = ['o', 's', '^', 'D', 'v', 'p']

    for pid in range(1, 7):
        earnings = earnings_timeline[pid]
        if earnings:
            hands = list(range(1, len(earnings) + 1))
            # Calculate running average: cumulative earnings / hand number
            avg_earnings = [e / h for e, h in zip(earnings, hands)]

            # Subsample markers for clarity (every N points)
            marker_every = max(1, len(hands) // 15)
            ax.plot(hands, avg_earnings, linewidth=1.8, color=COLORS[pid-1],
                   label=SHORT_NAMES[pid-1], alpha=0.9,
                   linestyle=line_styles[pid-1],
                   marker=markers[pid-1], markersize=4,
                   markevery=marker_every, markeredgecolor='white',
                   markeredgewidth=0.5)

    ax.set_xlabel('Hand Number (Sequential: Tables 1→10)')
    ax.set_ylabel('Average Earnings per Hand ($)')
    ax.set_title('Running Average Earnings per Hand Over Time',
                 fontweight='bold', pad=12)

    # Add zero line
    ax.axhline(y=0, color='#666666', linewidth=0.8, linestyle='-', alpha=0.5, zorder=1)

    # Grid settings
    ax.yaxis.grid(True)
    ax.xaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)

    # Set y-axis range to ±100
    ax.set_ylim(-100, 100)

    # Format y-axis with dollar amounts
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x:,.1f}'))

    # Professional legend
    ax.legend(loc='upper right', ncol=2, frameon=True,
              fancybox=False, edgecolor='#CCCCCC')

    plt.tight_layout()

    # Save figure at high resolution
    output_path = os.path.join(output_dir, 'poker_stats_avg_trend.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved: {output_path}")

    # Also save as PDF for vector graphics
    pdf_path = os.path.join(output_dir, 'poker_stats_avg_trend.pdf')
    plt.savefig(pdf_path, format='pdf', bbox_inches='tight', facecolor='white')
    print(f"Saved: {pdf_path}")

    plt.close(fig)


def create_all_plots(stats: dict, output_dir: str = '.'):
    """Create all bar plots with professional academic paper style."""
    setup_academic_style()

    # Create figure with subplots - academic paper proportions
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    fig.suptitle('LLM Poker Agent Performance Comparison\n(Mean ± Std across 10 Independent Tables)',
                 fontsize=13, fontweight='bold', y=0.98)

    # Plot each metric with academic-style labels
    metrics = [
        ('avgWinnings', 'Average Winnings/Hand', 'Winnings ($)', True),
        ('vpipRate', 'VPIP Rate', 'Rate (%)', False),
        ('foldRate', 'Fold Rate', 'Rate (%)', False),
        ('avgThinkMs', 'Response Latency', 'Time (ms)', False),
        ('biggestWin', 'Maximum Single Win', 'Amount ($)', False),
        ('biggestLoss', 'Maximum Single Loss', 'Amount ($)', True),
    ]

    for ax, (metric, title, ylabel, show_neg) in zip(axes.flat, metrics):
        create_bar_plot(ax, stats, metric, title, ylabel, show_neg)

    plt.tight_layout(rect=[0, 0.02, 1, 0.94])

    # Save figure at high resolution for publication
    output_path = os.path.join(output_dir, 'poker_stats_comparison.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved: {output_path}")

    # Also save as PDF for vector graphics (common in academic papers)
    pdf_path = os.path.join(output_dir, 'poker_stats_comparison.pdf')
    plt.savefig(pdf_path, format='pdf', bbox_inches='tight', facecolor='white')
    print(f"Saved: {pdf_path}")

    # Also save individual plots
    for metric, title, ylabel, show_neg in metrics:
        setup_academic_style()  # Reset style for each plot
        fig_single, ax_single = plt.subplots(figsize=(6, 4))
        create_bar_plot(ax_single, stats, metric, title, ylabel, show_neg)
        plt.tight_layout()
        single_path = os.path.join(output_dir, f'poker_stats_{metric}.png')
        plt.savefig(single_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close(fig_single)
        print(f"Saved: {single_path}")

    plt.close(fig)


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

    # Collect table winnings for trimmed stats
    table_winnings = collect_table_winnings(str(script_dir), num_tables=10)

    # Collect hand-by-hand winnings for trend plot (continuous across tables)
    earnings_timeline = collect_hand_by_hand_winnings(str(script_dir), num_tables=10)

    # Calculate mean and std
    stats = calculate_mean_std(stats_by_player)

    # Calculate trimmed stats (excluding best and worst table)
    trimmed_stats = calculate_trimmed_stats(table_winnings)

    # Print summary
    print_summary(stats)

    # Print trimmed stats summary
    print("\n" + "-"*60)
    print("TRIMMED AVG WINNINGS/HAND (Excluding 2 Best & 2 Worst Tables)")
    print("-"*60)
    for pid in range(1, 7):
        if pid in trimmed_stats:
            ts = trimmed_stats[pid]
            excl_low = ", ".join([f"${v:,.1f}" for v in ts['excluded_low']]) if ts['excluded_low'] else "N/A"
            excl_high = ", ".join([f"${v:,.1f}" for v in ts['excluded_high']]) if ts['excluded_high'] else "N/A"
            print(f"  {SHORT_NAMES[pid-1]:12s}: ${ts['mean']:>8,.1f} ± {ts['std']:>6,.1f}  (excl low: {excl_low} | high: {excl_high})")

    # Create plots
    print("\nGenerating plots...")
    create_all_plots(stats, str(script_dir))

    # Create trimmed average winnings plot
    print("\nGenerating trimmed winnings plot...")
    create_trimmed_avg_plot(trimmed_stats, str(script_dir))

    # Create trend plot
    print("\nGenerating trend plot...")
    create_trend_plot(earnings_timeline, str(script_dir))

    # Create average trend plot (running average per hand)
    print("\nGenerating average trend plot...")
    create_avg_trend_plot(earnings_timeline, str(script_dir))

    print("\nDone!")


if __name__ == '__main__':
    main()
