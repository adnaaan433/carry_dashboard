import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mplsoccer import VerticalPitch, add_image
from scipy import stats
import os
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyArrowPatch
from matplotlib.lines import Line2D
from urllib.request import urlopen
from PIL import Image

def plot_player_dashboard(
    selected_display_name,
    selected_team_name,
    min_mins,
    max_mins,
    selected_comp_name,
    selected_season_name,
    position_filter,
    df,
    selected_player_name,
    player_stats,
    show_other=True,
    show_prog=True,
    show_shot=True,
    show_goal=True
):
    # Try loading custom fonts
    try:
        font_bold = font_manager.FontProperties(fname=os.path.abspath('MontserratAlternates-Bold.ttf'))
        font_regular = font_manager.FontProperties(fname=os.path.abspath('NotoSans-Regular.ttf'))
        font_con_bold = font_manager.FontProperties(fname=os.path.abspath('NotoSans_Condensed-Regular.ttf'))
    except Exception:
        font_bold = None
        font_regular = None
        font_con_bold = None
        
    fig, (ax_pitch, ax_bars) = plt.subplots(1, 2, figsize=(16, 10), gridspec_kw={'width_ratios': [1, 1], 'wspace': -0.1})
    
    # --- Title Text ---
    fig.text(0.26, 1.09, selected_display_name, fontsize=28, fontproperties=font_bold)
    team_name_str = selected_team_name
    fig.text(0.26, 1.05, f'Carry Map and Stats Percentiles, for {team_name_str} | Data: Statsbomb | Made by: @adnaaan433', color='#0f0f0f', fontsize=12.5, fontproperties=font_regular)
    minute_range_str = f"{min_mins}+" if max_mins == 5000 else f"{min_mins}-{max_mins}"
    pos_label = position_filter if position_filter != 'All' else 'All Position'
    subtitle_text = f'Percentile among {selected_comp_name} {pos_label}s with {minute_range_str} minutes played in {selected_season_name} season'
    fig.text(0.26, 1.02, subtitle_text, color='#202020', fontsize=12.5, fontproperties=font_regular)
    
    # --- Team Logo ---
    try:
        df_teamNameId = pd.read_csv("teams_name_and_id_Statsbomb_Names.csv")
        ftmb_tid_list = df_teamNameId[df_teamNameId['teamName'] == team_name_str]['teamId'].to_list()
        if ftmb_tid_list:
            ftmb_tid = ftmb_tid_list[0]
            himage = urlopen(f"https://images.fotmob.com/image_resources/logo/teamlogo/{ftmb_tid}.png")
            himage = Image.open(himage)
            add_image(himage, fig, left=0.14, bottom=1.01, width=0.12, height=0.12)
    except Exception as e:
        pass
    
    # --- Carry Map (ax_pitch) ---
    ax_pitch.set_title("Carry Map", y=1.05, fontproperties=font_bold, fontsize=18)
    pitch = VerticalPitch(pitch_type='statsbomb', pitch_color='white', line_color='#c7d5cc')
    pitch.draw(ax=ax_pitch)
    
    player_events = df[(df['player_name'] == selected_player_name) & (df['team_name'] == selected_team_name) & (df['type_name'] == 'Carry')].copy()
    
    def add_fancy_arrows(carries_df, color, label, linewidth, zorder, m_scale, alpha=1.0):
        first = True
        for _, row in carries_df.iterrows():
            arrow = FancyArrowPatch(
                posA=(row['y'], row['x']),
                posB=(row['end_y'], row['end_x']),
                color=color,
                arrowstyle='-|>',
                mutation_scale= m_scale,
                linestyle='dashed',
                linewidth=linewidth,
                alpha=alpha,
                label=label if first else None,
                zorder=zorder
            )
            ax_pitch.add_patch(arrow)
            first = False
    
    custom_lines = []
    legend_labels = []

    if show_other:
        other_carries = player_events[(player_events['is_progressive_carry'] == False) & (player_events['shot_ending_carry'] == False) & (player_events['goal_ending_carry'] == False)]
        if not other_carries.empty:
            add_fancy_arrows(other_carries, 'grey', 'Other', linewidth=1, alpha=0.25, zorder=2, m_scale=10)
        custom_lines.append(Line2D([0], [0], color='grey', lw=2.5))
        legend_labels.append('Other')
            
    if show_prog:
        prog_carries = player_events[(player_events['is_progressive_carry'] == True) & (player_events['shot_ending_carry'] == False) & (player_events['goal_ending_carry'] == False)]
        if not prog_carries.empty:
            add_fancy_arrows(prog_carries, '#00A0DE', 'Progressive', linewidth=1.25, alpha=0.33, zorder=3, m_scale=12)
        custom_lines.append(Line2D([0], [0], color='#00A0DE', lw=2.5))
        legend_labels.append('Progressive')
            
    if show_shot:
        shot_carries = player_events[(player_events['shot_ending_carry'] == True) & (player_events['goal_ending_carry'] == False)]
        if not shot_carries.empty:
            add_fancy_arrows(shot_carries, '#ff7300', 'Shot Ending', linewidth=1.75, zorder=4, m_scale=12)
        custom_lines.append(Line2D([0], [0], color='#ff7300', lw=2.5))
        legend_labels.append('Shot Ending')
            
    if show_goal:
        goal_carries = player_events[player_events['goal_ending_carry'] == True]
        if not goal_carries.empty:
            add_fancy_arrows(goal_carries, '#2bb32b', 'Goal Ending', linewidth=2.5, zorder=5, m_scale=15)
        custom_lines.append(Line2D([0], [0], color='#2bb32b', lw=2.5))
        legend_labels.append('Goal Ending')
    
    if custom_lines:
        ax_pitch.legend(custom_lines, legend_labels, loc='lower center', bbox_to_anchor=(0.5, 0.98), ncol=len(custom_lines), frameon=False, prop=font_regular if font_regular else None, fontsize=12)
    
    # --- Stats Percentiles (ax_bars) ---
    ax_bars.set_title("Stats Percentiles", pad=0, y=1.05, fontproperties=font_bold, fontsize=18)
    metrics = ['total_carries_per90', 'progressive_carries_per90', 'progressive_carry_%', 'carry_success_rate_%', 'avg_carry_length', 'carry_obv_per90', 'shot_ending_carry_per90', 'goal_ending_carry_per90']
    metric_names = ['Total Carries (p90)', 'Progressive Carries (p90)', 'Progressive Carry %', 'Carry Success Rate %', 'Average Carry Length', 'Carry OBV (p90)', 'Shot Ending Carries (p90)', 'Goal Ending Carries (p90)']
    
    player_data = player_stats[(player_stats['player_name'] == selected_player_name) & (player_stats['team_name'] == selected_team_name)].iloc[0]
    
    fig.patch.set_facecolor('white')
    ax_bars.set_facecolor('white')
    
    percentile_colors = ['#fb4b44', 'orange', 'green']
    percentile_cmap = LinearSegmentedColormap.from_list('percentile', percentile_colors, N=100)
    
    y_pos = range(len(metrics))
    
    percentiles = []
    actual_values = []
    for m in metrics:
        val = player_data[m]
        pct = stats.percentileofscore(player_stats[m].dropna(), val)
        percentiles.append(pct)
        actual_values.append(val)
        
    # Gray background bars
    ax_bars.barh(y_pos, [100] * len(metrics), color='#808080', height=0.15, alpha=0.3, zorder=1)
    
    # Colored filled bars
    base_metric_map = {
        'total_carries_per90': 'total_carries',
        'progressive_carries_per90': 'progressive_carries',
        'carry_obv_per90': 'carry_obv',
        'shot_ending_carry_per90': 'shot_ending_carry',
        'goal_ending_carry_per90': 'goal_ending_carry'
    }

    for i, (y, val, pct, label) in enumerate(zip(y_pos, actual_values, percentiles, metric_names)):
        color = percentile_cmap(pct / 100.0)
        ax_bars.barh(y, pct, color=color, height=0.15, alpha=0.7, zorder=2)
        
        # Scatter circle for percentile text
        ax_bars.scatter(pct, y, s=750, color=color, edgecolor='None', linewidth=2, zorder=3)
        ax_bars.text(pct, y, f'{int(pct)}', color='white', va='center', ha='center', fontsize=15, zorder=4, fontproperties=font_bold)
        
        # Metric label above bar
        m = metrics[i]
        if m in base_metric_map:
            base_val = player_data[base_metric_map[m]]
            if m == 'carry_obv_per90':
                label_text = f'{label}: {base_val:.2f} ({val:.2f})'
            else:
                label_text = f'{label}: {int(base_val)} ({val:.2f})'
        else:
            label_text = f'{label}: {val:.2f}'
            
        ax_bars.text(0, y - 0.35, label_text, va='center', ha='left', fontsize=15, fontproperties=font_regular)
        
    ax_bars.set_xlim(-5, 105)
    ax_bars.set_ylim(len(metrics) - 0.5, -0.6)
    
    # Remove spines and axes
    for spine in ax_bars.spines.values():
        spine.set_visible(False)
    ax_bars.grid(False)
    ax_bars.set_yticks([])
    ax_bars.set_xticks([])

    plt.tight_layout()
    return fig
