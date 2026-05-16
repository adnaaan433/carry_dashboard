import streamlit as st
import pandas as pd
from data_loader import load_competitions, load_competition_events_from_api, load_player_season_stats


st.set_page_config(page_title="Statsbomb Event Data Loader", layout="wide")

# ── Password Gate ──────────────────────────────────────────────────────────────
if not st.session_state.get("authenticated"):
    st.title("🔒 Access Required")
    pwd = st.text_input("Enter password", type="password")
    if st.button("Login"):
        if pwd == st.secrets["app_password"]:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()
# ──────────────────────────────────────────────────────────────────────────────

st.title("Statsbomb Event Data Loader")

# Load competitions data
try:
    comps_df = load_competitions()
except Exception as e:
    st.error(f"Failed to load competitions: {e}")
    st.stop()

if comps_df is not None and not comps_df.empty:
    with st.sidebar:
        st.header("Data Loading")
        # Get unique competitions
        competitions = comps_df[['competition_id', 'competition_name']].drop_duplicates().sort_values('competition_name')
        
        # User selects competition
        selected_comp_name = st.selectbox("Select Competition", competitions['competition_name'])
        
        if selected_comp_name:
            selected_comp_id = competitions[competitions['competition_name'] == selected_comp_name]['competition_id'].iloc[0]
            
            # Get seasons for the selected competition
            seasons = comps_df[comps_df['competition_id'] == selected_comp_id][['season_id', 'season_name']].drop_duplicates().sort_values('season_name', ascending=False)
            
            # User selects season
            selected_season_name = st.selectbox("Select Season", seasons['season_name'])
            
            if selected_season_name:
                selected_season_id = seasons[seasons['season_name'] == selected_season_name]['season_id'].iloc[0]
                
                # Load button
                if st.button("Load Data"):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    with st.spinner("Loading filtered event data..."):
                        events_df = load_competition_events_from_api(
                            selected_comp_id, 
                            selected_season_id, 
                            progress_bar=progress_bar, 
                            status_text=status_text
                        )
                        
                        player_stats_df = load_player_season_stats(selected_comp_id, selected_season_id)
                    
                    # Clear progress elements
                    progress_bar.empty()
                    status_text.empty()
                        
                    if events_df is not None and not events_df.empty:
                        st.session_state['events_df'] = events_df
                        st.session_state['player_stats_df'] = player_stats_df
                        st.success(f"Data loaded successfully! Total records: {len(events_df)}")
                    else:
                        if 'events_df' in st.session_state:
                            del st.session_state['events_df']
                        st.warning("No event data found for the selected competition and season.")
                        

    # ── Display loaded dataframe ───────────────────────────────────────────────────
    if 'events_df' in st.session_state:
        df = st.session_state['events_df'].copy()
        # st.subheader(f"Loaded DataFrame — {len(df):,} rows × {len(df.columns)} columns")
        # st.dataframe(df, use_container_width=True)
        # st.text(df.type_name.value_counts())
        
        # Calculate Player Statistics
        import numpy as np
        
        is_carry = df['type_name'] == 'Carry'
        
        dist_start = np.sqrt((120 - df['x'])**2 + (40 - df['y'])**2)
        dist_end = np.sqrt((120 - df['end_x'])**2 + (40 - df['end_y'])**2)
        dist_reduction = dist_start - dist_end
        
        carry_length = np.sqrt((df['end_x'] - df['x'])**2 + (df['end_y'] - df['y'])**2)
        
        prog_cond1 = (df['x'] > 80) & (dist_reduction >= 10)
        prog_cond2 = (df['x'] <= 80) & (df['x'] >= 40) & (dist_reduction >= 12.5)
        prog_cond3 = (df['x'] < 40) & (dist_reduction >= 15)
        df['is_carry'] = is_carry
        df['is_progressive_carry'] = is_carry & (prog_cond1 | prog_cond2 | prog_cond3)
        df['carry_length'] = np.where(is_carry, carry_length, np.nan)
        
        # Ensure obv_for_net exists and fillna
        if 'obv_for_net' in df.columns:
            df['carry_obv'] = np.where(is_carry, df['obv_for_net'].fillna(0), 0)
        else:
            df['carry_obv'] = 0
            
        next_type = df['type_name'].shift(-1)
        next_outcome = df['outcome_name'].shift(-1) if 'outcome_name' in df.columns else pd.Series([None]*len(df))
        next_pass_shot_assist = df['pass_shot_assist'].shift(-1) if 'pass_shot_assist' in df.columns else pd.Series([False]*len(df))
        next_pass_goal_assist = df['pass_goal_assist'].shift(-1) if 'pass_goal_assist' in df.columns else pd.Series([False]*len(df))
        next_player = df['player_name'].shift(-1)
        diff_player_unsuccessful = (next_player != df['player_name']) & ~(
            (next_type == 'Foul Committed') | 
            ((next_type == 'Duel') & next_outcome.isin(['Won', 'Successful In Play']))
        )
        same_player_unsuccessful = (next_player == df['player_name']) & (
            next_type.isin(['Dispossessed', 'Goal Keeper', 'Miscontrol']) |
            ((next_type == 'Duel') & next_outcome.isin(['Lost', 'Lost In Play']))
        )
        df['unsuccessful_carry'] = is_carry & (diff_player_unsuccessful | same_player_unsuccessful)
        
        df['shot_ending_carry'] = is_carry & ((next_type == 'Shot') | ((next_type == 'Pass') & (next_pass_shot_assist == True)))
        df['goal_ending_carry'] = is_carry & (((next_type == 'Shot') & (next_outcome == 'Goal')) | ((next_type == 'Pass') & (next_pass_goal_assist == True)))
        
        player_stats = df.groupby(['player_name', 'team_name']).agg(
            primary_position=('position_name', lambda x: x.value_counts().index[0] if not x.value_counts().empty else None),
            total_carries=('is_carry', 'sum'),
            unsuccessful_carries=('unsuccessful_carry', 'sum'),
            progressive_carries=('is_progressive_carry', 'sum'),
            avg_carry_length=('carry_length', 'median'),
            carry_obv=('carry_obv', 'sum'),
            shot_ending_carry=('shot_ending_carry', 'sum'),
            goal_ending_carry=('goal_ending_carry', 'sum')
        ).reset_index()
        
        player_stats['progressive_carry_%'] = (player_stats['progressive_carries'] / player_stats['total_carries'] * 100).fillna(0)
        player_stats['carry_success_rate_%'] = ((player_stats['total_carries'] - player_stats['unsuccessful_carries']) / player_stats['total_carries'] * 100).fillna(0)
        
        if 'player_stats_df' in st.session_state and not st.session_state['player_stats_df'].empty:
            import unicodedata
            def normalize_name(name):
                if not isinstance(name, str):
                    return name
                return unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
            
            player_stats['_merge_name'] = player_stats['player_name'].apply(normalize_name)
            ps_df = st.session_state['player_stats_df'].copy()
            ps_df['_merge_name'] = ps_df['player_name'].apply(normalize_name)
            
            player_stats = pd.merge(player_stats, ps_df.drop(columns=['player_name']),
                                 on=['_merge_name', 'team_name'], how='left')
            player_stats.drop(columns=['_merge_name'], inplace=True)
            
        if 'player_season_minutes' in player_stats.columns:
            nineties = player_stats['player_season_minutes'] / 90
            player_stats['total_carries_per90'] = (player_stats['total_carries'] / nineties).fillna(0)
            player_stats['progressive_carries_per90'] = (player_stats['progressive_carries'] / nineties).fillna(0)
            player_stats['carry_obv_per90'] = (player_stats['carry_obv'] / nineties).fillna(0)
            player_stats['shot_ending_carry_per90'] = (player_stats['shot_ending_carry'] / nineties).fillna(0)
            player_stats['goal_ending_carry_per90'] = (player_stats['goal_ending_carry'] / nineties).fillna(0)
            
            st.markdown("---")
            min_mins, max_mins = st.slider(
                "Filter by Minutes Played",
                min_value=100,
                max_value=5000,
                value=(1200, 5000),
                step=100
            )
            player_stats = player_stats[
                (player_stats['player_season_minutes'] >= min_mins) & 
                (player_stats['player_season_minutes'] <= max_mins)
            ].reset_index(drop=True)
            
            position_filter = st.selectbox("Filter by Position", ['All', 'CF', 'Winger/AM', 'Mid', 'FB', 'CB'])
            if position_filter != 'All':
                if position_filter == 'CF':
                    pf = ['Center Forward', 'Left Center Forward', 'Right Center Forward', 'Secondary Striker']
                elif position_filter == 'Winger/AM':
                    pf = ['Left Wing', 'Right Wing', 'Right Attacking Midfield', 'Left Attacking Midfield', 'Left Midfield', 'Right Midfield', 'Center Attacking Midfield']
                elif position_filter == 'Mid':
                    pf = ['Center Midfield', 'Left Center Midfield', 'Right Center Midfield', 'Center Defensive Midfield', 'Left Defensive Midfield', 'Right Defensive Midfield']
                elif position_filter == 'FB':
                    pf = ['Left Back', 'Right Back', 'Left Wing Back', 'Right Wing Back']
                elif position_filter == 'CB':
                    pf = ['Left Center Back', 'Right Center Back', 'Center Back']
                player_stats = player_stats[player_stats['primary_position'].isin(pf)].reset_index(drop=True)
        
        if not player_stats.empty:
            plot_metrics = ['total_carries_per90', 'progressive_carries_per90', 'progressive_carry_%', 'carry_success_rate_%', 'avg_carry_length', 'carry_obv_per90', 'shot_ending_carry_per90', 'goal_ending_carry_per90']
            player_stats['overall_percentile'] = player_stats[plot_metrics].rank(pct=True).mean(axis=1).mul(100).round(2)

        st.subheader(f"Player Statistics — {len(player_stats):,} rows")
        st.dataframe(player_stats.sort_values(by='overall_percentile', ascending=False), use_container_width=True)
        # st.text(sorted(player_stats.primary_position.unique()))
        
        if not player_stats.empty:
            st.markdown("---")
            st.subheader("Player Dashboard")
            
            display_options = []
            for _, row in player_stats.iterrows():
                name = row['player_known_name'] if 'player_known_name' in player_stats.columns and pd.notnull(row['player_known_name']) else row['player_name']
                display_options.append(f"{name} ({row['team_name']})")
                
            player_stats['display_option'] = display_options
            
            selected_display = st.selectbox("Select Player", sorted(display_options))
            
            selected_row = player_stats[player_stats['display_option'] == selected_display].iloc[0]
            selected_player_name = selected_row['player_name']
            selected_team_name = selected_row['team_name']
            selected_display_name = selected_row['player_known_name'] if 'player_known_name' in player_stats.columns and pd.notnull(selected_row['player_known_name']) else selected_player_name
            
            st.markdown("**Select Carry Types to Plot:**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                show_other = st.checkbox("Other Carries", value=False)
            with col2:
                show_prog = st.checkbox("Progressive Carries", value=True)
            with col3:
                show_shot = st.checkbox("Shot Ending Carries", value=True)
            with col4:
                show_goal = st.checkbox("Goal Ending Carries", value=True)
            
            from visuals import plot_player_dashboard
            
            fig = plot_player_dashboard(
                selected_display_name=selected_display_name,
                selected_team_name=selected_team_name,
                min_mins=min_mins,
                max_mins=max_mins,
                selected_comp_name=selected_comp_name,
                selected_season_name=selected_season_name,
                position_filter=position_filter,
                df=df,
                selected_player_name=selected_player_name,
                player_stats=player_stats,
                show_other=show_other,
                show_prog=show_prog,
                show_shot=show_shot,
                show_goal=show_goal
            )
            
            st.pyplot(fig)
    else:
        st.info("👈 Select a competition and season from the sidebar, then click **Load Data** to view the dataframe.")

else:
    st.warning("No competitions available.")
